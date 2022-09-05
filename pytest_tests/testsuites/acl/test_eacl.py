import allure
import pytest

from common import NEOFS_NETMAP_DICT
from failover_utils import wait_object_replication_on_nodes
from python_keywords.acl import (
    EACLAccess,
    EACLOperation,
    EACLRole,
    EACLRule,
    create_eacl,
    set_eacl,
    wait_for_cache_expired,
)
from python_keywords.container import create_container
from python_keywords.container_access import (
    check_full_access_to_container,
    check_no_access_to_container,
)
from python_keywords.neofs_verbs import put_object
from python_keywords.node_management import drop_object
from wellknown_acl import PUBLIC_ACL


@pytest.mark.sanity
@pytest.mark.acl
@pytest.mark.acl_extended
class TestEACLContainer:
    NODE_COUNT = len(NEOFS_NETMAP_DICT.keys())

    @pytest.fixture(scope="function")
    def eacl_full_placement_container_with_object(self, wallets, file_path):
        user_wallet = wallets.get_wallet()
        with allure.step("Create eACL public container with full placement rule"):
            full_placement_rule = (
                f"REP {self.NODE_COUNT} IN X CBF 1 SELECT {self.NODE_COUNT} FROM * AS X"
            )
            cid = create_container(
                user_wallet.wallet_path, full_placement_rule, basic_acl=PUBLIC_ACL
            )

        with allure.step("Add test object to container"):
            oid = put_object(user_wallet.wallet_path, file_path, cid)
            wait_object_replication_on_nodes(
                user_wallet.wallet_path, cid, oid, self.NODE_COUNT
            )

        yield cid, oid, file_path

    @pytest.mark.parametrize("deny_role", [EACLRole.USER, EACLRole.OTHERS])
    def test_extended_acl_deny_all_operations(
        self, wallets, eacl_container_with_objects, deny_role
    ):
        user_wallet = wallets.get_wallet()
        other_wallet = wallets.get_wallet(EACLRole.OTHERS)
        deny_role_wallet = other_wallet if deny_role == EACLRole.OTHERS else user_wallet
        not_deny_role_wallet = (
            user_wallet if deny_role == EACLRole.OTHERS else other_wallet
        )
        deny_role_str = "all others" if deny_role == EACLRole.OTHERS else "user"
        not_deny_role_str = "user" if deny_role == EACLRole.OTHERS else "all others"
        allure.dynamic.title(f"Testcase to deny NeoFS operations for {deny_role_str}.")
        cid, object_oids, file_path = eacl_container_with_objects

        with allure.step(f"Deny all operations for {deny_role_str} via eACL"):
            eacl_deny = [
                EACLRule(access=EACLAccess.DENY, role=deny_role, operation=op)
                for op in EACLOperation
            ]
            set_eacl(user_wallet.wallet_path, cid, create_eacl(cid, eacl_deny))
            wait_for_cache_expired()

        with allure.step(
            f"Check only {not_deny_role_str} has full access to container"
        ):
            with allure.step(
                f"Check {deny_role_str} has not access to any operations with container"
            ):
                check_no_access_to_container(
                    deny_role_wallet.wallet_path, cid, object_oids[0], file_path
                )

            with allure.step(
                f"Check {not_deny_role_wallet} has full access to eACL public container"
            ):
                check_full_access_to_container(
                    not_deny_role_wallet.wallet_path, cid, object_oids.pop(), file_path
                )

        with allure.step(f"Allow all operations for {deny_role_str} via eACL"):
            eacl_deny = [
                EACLRule(access=EACLAccess.ALLOW, role=deny_role, operation=op)
                for op in EACLOperation
            ]
            set_eacl(user_wallet.wallet_path, cid, create_eacl(cid, eacl_deny))
            wait_for_cache_expired()

        with allure.step(f"Check all have full access to eACL public container"):
            check_full_access_to_container(
                user_wallet.wallet_path, cid, object_oids.pop(), file_path
            )
            check_full_access_to_container(
                other_wallet.wallet_path, cid, object_oids.pop(), file_path
            )

    @allure.title("Testcase to allow NeoFS operations for only one other pubkey.")
    def test_extended_acl_deny_all_operations_exclude_pubkey(
        self, wallets, eacl_container_with_objects
    ):
        user_wallet = wallets.get_wallet()
        other_wallet, other_wallet_allow = wallets.get_wallets_list(EACLRole.OTHERS)[
            0:2
        ]
        cid, object_oids, file_path = eacl_container_with_objects

        with allure.step(
            "Deny all operations for others except single wallet via eACL"
        ):
            eacl = [
                EACLRule(
                    access=EACLAccess.ALLOW,
                    role=other_wallet_allow.wallet_path,
                    operation=op,
                )
                for op in EACLOperation
            ]
            eacl += [
                EACLRule(access=EACLAccess.DENY, role=EACLRole.OTHERS, operation=op)
                for op in EACLOperation
            ]
            set_eacl(user_wallet.wallet_path, cid, create_eacl(cid, eacl))
            wait_for_cache_expired()

        with allure.step(
            "Check only owner and allowed other have full access to public container"
        ):
            with allure.step("Check other has not access to operations with container"):
                check_no_access_to_container(
                    other_wallet.wallet_path, cid, object_oids[0], file_path
                )

            with allure.step("Check owner has full access to public container"):
                check_full_access_to_container(
                    user_wallet.wallet_path, cid, object_oids.pop(), file_path
                )

            with allure.step("Check allowed other has full access to public container"):
                check_full_access_to_container(
                    other_wallet_allow.wallet_path, cid, object_oids.pop(), file_path
                )

    @allure.title("Testcase to validate NeoFS replication with eACL deny rules.")
    def test_extended_acl_deny_replication(
        self, wallets, eacl_full_placement_container_with_object, file_path
    ):
        user_wallet = wallets.get_wallet()
        cid, oid, file_path = eacl_full_placement_container_with_object

        with allure.step("Deny all operations for user via eACL"):
            eacl_deny = [
                EACLRule(access=EACLAccess.DENY, role=EACLRole.USER, operation=op)
                for op in EACLOperation
            ]
            eacl_deny += [
                EACLRule(access=EACLAccess.DENY, role=EACLRole.OTHERS, operation=op)
                for op in EACLOperation
            ]
            set_eacl(user_wallet.wallet_path, cid, create_eacl(cid, eacl_deny))
            wait_for_cache_expired()

        with allure.step("Drop object to check replication"):
            drop_object(node_name=[*NEOFS_NETMAP_DICT][0], cid=cid, oid=oid)

        storage_wallet_path = NEOFS_NETMAP_DICT[[*NEOFS_NETMAP_DICT][0]]["wallet_path"]
        with allure.step("Wait for dropped object replicated"):
            wait_object_replication_on_nodes(
                storage_wallet_path, cid, oid, self.NODE_COUNT
            )
