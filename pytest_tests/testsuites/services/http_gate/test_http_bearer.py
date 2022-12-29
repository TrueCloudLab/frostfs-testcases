import logging

import allure
import pytest
from container import create_container
from file_helper import generate_file
from http_gate import get_object_and_verify_hashes, upload_via_http_gate_curl
from python_keywords.acl import (
    EACLAccess,
    EACLOperation,
    EACLRole,
    EACLRule,
    bearer_token_base64_from_file,
    create_eacl,
    form_bearertoken_file,
    set_eacl,
    sign_bearer,
    wait_for_cache_expired,
)
from wellknown_acl import PUBLIC_ACL

from steps.cluster_test_base import ClusterTestBase

logger = logging.getLogger("NeoLogger")


@pytest.mark.sanity
@pytest.mark.http_gate
class Test_http_bearer(ClusterTestBase):
    PLACEMENT_RULE = "REP 2 IN X CBF 1 SELECT 2 FROM * AS X"

    @pytest.fixture(scope="class", autouse=True)
    @allure.title("[Class/Autouse]: Prepare wallet and deposit")
    def prepare_wallet(self, default_wallet):
        Test_http_bearer.wallet = default_wallet

    @pytest.fixture(scope="class")
    def user_container(self) -> str:
        return create_container(
            wallet=self.wallet,
            shell=self.shell,
            endpoint=self.cluster.default_rpc_endpoint,
            rule=self.PLACEMENT_RULE,
            basic_acl=PUBLIC_ACL,
        )

    @pytest.fixture(scope="class")
    def eacl_deny_for_others(self, user_container: str) -> None:
        with allure.step(f"Set deny all operations for {EACLRole.OTHERS} via eACL"):
            eacl = EACLRule(
                access=EACLAccess.DENY, role=EACLRole.OTHERS, operation=EACLOperation.PUT
            )
            set_eacl(
                self.wallet,
                user_container,
                create_eacl(user_container, eacl, shell=self.shell),
                shell=self.shell,
                endpoint=self.cluster.default_rpc_endpoint,
            )
            wait_for_cache_expired()

    @pytest.fixture(scope="class")
    def bearer_token_no_limit_for_others(self, user_container: str) -> str:
        with allure.step(f"Create bearer token for {EACLRole.OTHERS} with all operations allowed"):
            bearer = form_bearertoken_file(
                self.wallet,
                user_container,
                [
                    EACLRule(operation=op, access=EACLAccess.ALLOW, role=EACLRole.OTHERS)
                    for op in EACLOperation
                ],
                shell=self.shell,
                endpoint=self.cluster.default_rpc_endpoint,
                sign=False,
            )
            bearer_signed = f"{bearer}_signed"
            sign_bearer(
                shell=self.shell,
                wallet_path=self.wallet,
                eacl_rules_file_from=bearer,
                eacl_rules_file_to=bearer_signed,
                json=False,
            )
            return bearer_token_base64_from_file(bearer_signed)

    @allure.title(f"[negative] Put object without bearer token for {EACLRole.OTHERS}")
    def test_unable_put_without_bearer_token(
        self, simple_object_size: int, user_container: str, eacl_deny_for_others
    ):
        eacl_deny_for_others
        upload_via_http_gate_curl(
            cid=user_container,
            filepath=generate_file(simple_object_size),
            endpoint=self.cluster.default_http_gate_endpoint,
            error_pattern="access to object operation denied",
        )

    @pytest.mark.parametrize(
        "object_size",
        [pytest.lazy_fixture("simple_object_size"), pytest.lazy_fixture("complex_object_size")],
        ids=["simple object", "complex object"],
    )
    def test_put_with_bearer_when_eacl_restrict(
        self,
        object_size: int,
        user_container: str,
        eacl_deny_for_others,
        bearer_token_no_limit_for_others: str,
    ):
        eacl_deny_for_others
        bearer = bearer_token_no_limit_for_others
        file_path = generate_file(object_size)
        with allure.step(
            f"Put object with bearer token for {EACLRole.OTHERS}, then get and verify hashes"
        ):
            headers = [f" -H 'Authorization: Bearer {bearer}'"]
            oid = upload_via_http_gate_curl(
                cid=user_container,
                filepath=file_path,
                endpoint=self.cluster.default_http_gate_endpoint,
                headers=headers,
            )
            get_object_and_verify_hashes(
                oid=oid,
                file_name=file_path,
                wallet=self.wallet,
                cid=user_container,
                shell=self.shell,
                nodes=self.cluster.storage_nodes,
                endpoint=self.cluster.default_http_gate_endpoint,
            )
