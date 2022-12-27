import allure
import pytest
from file_helper import generate_file
from neofs_testlib.shell import Shell
from python_keywords.acl import (
    EACLAccess,
    EACLOperation,
    EACLRole,
    EACLRule,
    create_eacl,
    set_eacl,
    wait_for_cache_expired,
)
from python_keywords.container import (
    create_container,
    delete_container,
    get_container,
    list_containers,
)
from python_keywords.object_access import can_put_object
from wallet import WalletFile
from wellknown_acl import PUBLIC_ACL

from steps.cluster_test_base import ClusterTestBase
from steps.session_token import ContainerVerb, get_container_signed_token


@pytest.mark.static_session_container
class TestSessionTokenContainer(ClusterTestBase):
    @pytest.fixture(scope="module")
    def static_sessions(
        self,
        owner_wallet: WalletFile,
        user_wallet: WalletFile,
        client_shell: Shell,
        temp_directory: str,
    ) -> dict[ContainerVerb, str]:
        """
        Returns dict with static session token file paths for all verbs with default lifetime
        """
        return {
            verb: get_container_signed_token(
                owner_wallet, user_wallet, verb, client_shell, temp_directory
            )
            for verb in ContainerVerb
        }

    def test_static_session_token_container_create(
        self,
        owner_wallet: WalletFile,
        user_wallet: WalletFile,
        static_sessions: dict[ContainerVerb, str],
    ):
        """
        Validate static session with create operation
        """
        with allure.step("Create container with static session token"):
            cid = create_container(
                user_wallet.path,
                session_token=static_sessions[ContainerVerb.CREATE],
                shell=self.shell,
                endpoint=self.cluster.default_rpc_endpoint,
                wait_for_creation=False,
            )

        container_info: dict[str, str] = get_container(
            owner_wallet.path, cid, shell=self.shell, endpoint=self.cluster.default_rpc_endpoint
        )
        assert container_info["ownerID"] == owner_wallet.get_address()

        assert cid not in list_containers(
            user_wallet.path, shell=self.shell, endpoint=self.cluster.default_rpc_endpoint
        )
        assert cid in list_containers(
            owner_wallet.path, shell=self.shell, endpoint=self.cluster.default_rpc_endpoint
        )

    def test_static_session_token_container_create_with_other_verb(
        self,
        user_wallet: WalletFile,
        static_sessions: dict[ContainerVerb, str],
    ):
        """
        Validate static session without create operation
        """
        with allure.step("Try create container with static session token without PUT rule"):
            for verb in [verb for verb in ContainerVerb if verb != ContainerVerb.CREATE]:
                with pytest.raises(Exception):
                    create_container(
                        user_wallet.path,
                        session_token=static_sessions[verb],
                        shell=self.shell,
                        endpoint=self.cluster.default_rpc_endpoint,
                        wait_for_creation=False,
                    )

    def test_static_session_token_container_create_with_other_wallet(
        self,
        stranger_wallet: WalletFile,
        static_sessions: dict[ContainerVerb, str],
    ):
        """
        Validate static session with create operation for other wallet
        """
        with allure.step("Try create container with static session token without PUT rule"):
            with pytest.raises(Exception):
                create_container(
                    stranger_wallet.path,
                    session_token=static_sessions[ContainerVerb.CREATE],
                    shell=self.shell,
                    endpoint=self.cluster.default_rpc_endpoint,
                    wait_for_creation=False,
                )

    def test_static_session_token_container_delete(
        self,
        owner_wallet: WalletFile,
        user_wallet: WalletFile,
        static_sessions: dict[ContainerVerb, str],
    ):
        """
        Validate static session with delete operation
        """
        with allure.step("Create container"):
            cid = create_container(
                owner_wallet.path,
                shell=self.shell,
                endpoint=self.cluster.default_rpc_endpoint,
                wait_for_creation=False,
            )
        with allure.step("Delete container with static session token"):
            delete_container(
                wallet=user_wallet.path,
                cid=cid,
                session_token=static_sessions[ContainerVerb.DELETE],
                shell=self.shell,
                endpoint=self.cluster.default_rpc_endpoint,
                await_mode=True,
            )

        assert cid not in list_containers(
            owner_wallet.path, shell=self.shell, endpoint=self.cluster.default_rpc_endpoint
        )

    def test_static_session_token_container_set_eacl(
        self,
        owner_wallet: WalletFile,
        user_wallet: WalletFile,
        stranger_wallet: WalletFile,
        static_sessions: dict[ContainerVerb, str],
        simple_object_size,
    ):
        """
        Validate static session with set eacl operation
        """
        with allure.step("Create container"):
            cid = create_container(
                owner_wallet.path,
                basic_acl=PUBLIC_ACL,
                shell=self.shell,
                endpoint=self.cluster.default_rpc_endpoint,
            )
        file_path = generate_file(simple_object_size)
        assert can_put_object(stranger_wallet.path, cid, file_path, self.shell, self.cluster)

        with allure.step(f"Deny all operations for other via eACL"):
            eacl_deny = [
                EACLRule(access=EACLAccess.DENY, role=EACLRole.OTHERS, operation=op)
                for op in EACLOperation
            ]
            set_eacl(
                user_wallet.path,
                cid,
                create_eacl(cid, eacl_deny, shell=self.shell),
                shell=self.shell,
                endpoint=self.cluster.default_rpc_endpoint,
                session_token=static_sessions[ContainerVerb.SETEACL],
            )
            wait_for_cache_expired()

        assert not can_put_object(stranger_wallet.path, cid, file_path, self.shell, self.cluster)
