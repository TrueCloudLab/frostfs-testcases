import allure
import pytest
from cluster_test_base import ClusterTestBase
from failover_utils import wait_object_replication
from frostfs_testlib.shell import Shell
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
from python_keywords.frostfs_verbs import put_object_to_random_node
from python_keywords.node_management import drop_object
from python_keywords.object_access import (
    can_delete_object,
    can_get_head_object,
    can_get_object,
    can_get_range_hash_of_object,
    can_get_range_of_object,
    can_put_object,
    can_search_object,
)
from wellknown_acl import PUBLIC_ACL


@pytest.mark.sanity
@pytest.mark.acl
@pytest.mark.acl_extended
class TestEACLContainer(ClusterTestBase):
    @pytest.fixture(scope="function")
    def eacl_full_placement_container_with_object(self, wallets, file_path) -> str:
        user_wallet = wallets.get_wallet()
        storage_nodes = self.cluster.storage_nodes
        node_count = len(storage_nodes)
        with allure.step("Create eACL public container with full placement rule"):
            full_placement_rule = f"REP {node_count} IN X CBF 1 SELECT {node_count} FROM * AS X"
            cid = create_container(
                wallet=user_wallet.wallet_path,
                rule=full_placement_rule,
                basic_acl=PUBLIC_ACL,
                shell=self.shell,
                endpoint=self.cluster.default_rpc_endpoint,
            )

        with allure.step("Add test object to container"):
            oid = put_object_to_random_node(
                user_wallet.wallet_path, file_path, cid, shell=self.shell, cluster=self.cluster
            )
            wait_object_replication(
                cid,
                oid,
                node_count,
                shell=self.shell,
                nodes=storage_nodes,
            )

        yield cid, oid, file_path

    @pytest.mark.parametrize("deny_role", [EACLRole.USER, EACLRole.OTHERS])
    def test_extended_acl_deny_all_operations(
        self, wallets, eacl_container_with_objects, deny_role
    ):
        user_wallet = wallets.get_wallet()
        other_wallet = wallets.get_wallet(EACLRole.OTHERS)
        deny_role_wallet = other_wallet if deny_role == EACLRole.OTHERS else user_wallet
        not_deny_role_wallet = user_wallet if deny_role == EACLRole.OTHERS else other_wallet
        deny_role_str = "all others" if deny_role == EACLRole.OTHERS else "user"
        not_deny_role_str = "user" if deny_role == EACLRole.OTHERS else "all others"
        allure.dynamic.title(f"Testcase to deny FrostFS operations for {deny_role_str}.")
        cid, object_oids, file_path = eacl_container_with_objects

        with allure.step(f"Deny all operations for {deny_role_str} via eACL"):
            eacl_deny = [
                EACLRule(access=EACLAccess.DENY, role=deny_role, operation=op)
                for op in EACLOperation
            ]
            set_eacl(
                user_wallet.wallet_path,
                cid,
                create_eacl(cid, eacl_deny, shell=self.shell),
                shell=self.shell,
                endpoint=self.cluster.default_rpc_endpoint,
            )
            wait_for_cache_expired()

        with allure.step(f"Check only {not_deny_role_str} has full access to container"):
            with allure.step(
                f"Check {deny_role_str} has not access to any operations with container"
            ):
                check_no_access_to_container(
                    deny_role_wallet.wallet_path,
                    cid,
                    object_oids[0],
                    file_path,
                    shell=self.shell,
                    cluster=self.cluster,
                )

            with allure.step(
                f"Check {not_deny_role_wallet} has full access to eACL public container"
            ):
                check_full_access_to_container(
                    not_deny_role_wallet.wallet_path,
                    cid,
                    object_oids.pop(),
                    file_path,
                    shell=self.shell,
                    cluster=self.cluster,
                )

        with allure.step(f"Allow all operations for {deny_role_str} via eACL"):
            eacl_deny = [
                EACLRule(access=EACLAccess.ALLOW, role=deny_role, operation=op)
                for op in EACLOperation
            ]
            set_eacl(
                user_wallet.wallet_path,
                cid,
                create_eacl(cid, eacl_deny, shell=self.shell),
                shell=self.shell,
                endpoint=self.cluster.default_rpc_endpoint,
            )
            wait_for_cache_expired()

        with allure.step("Check all have full access to eACL public container"):
            check_full_access_to_container(
                user_wallet.wallet_path,
                cid,
                object_oids.pop(),
                file_path,
                shell=self.shell,
                cluster=self.cluster,
            )
            check_full_access_to_container(
                other_wallet.wallet_path,
                cid,
                object_oids.pop(),
                file_path,
                shell=self.shell,
                cluster=self.cluster,
            )

    @allure.title("Testcase to allow FrostFS operations for only one other pubkey.")
    def test_extended_acl_deny_all_operations_exclude_pubkey(
        self, wallets, eacl_container_with_objects
    ):
        user_wallet = wallets.get_wallet()
        other_wallet, other_wallet_allow = wallets.get_wallets_list(EACLRole.OTHERS)[0:2]
        cid, object_oids, file_path = eacl_container_with_objects

        with allure.step("Deny all operations for others except single wallet via eACL"):
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
            set_eacl(
                user_wallet.wallet_path,
                cid,
                create_eacl(cid, eacl, shell=self.shell),
                shell=self.shell,
                endpoint=self.cluster.default_rpc_endpoint,
            )
            wait_for_cache_expired()

        with allure.step("Check only owner and allowed other have full access to public container"):
            with allure.step("Check other has not access to operations with container"):
                check_no_access_to_container(
                    other_wallet.wallet_path,
                    cid,
                    object_oids[0],
                    file_path,
                    shell=self.shell,
                    cluster=self.cluster,
                )

            with allure.step("Check owner has full access to public container"):
                check_full_access_to_container(
                    user_wallet.wallet_path,
                    cid,
                    object_oids.pop(),
                    file_path,
                    shell=self.shell,
                    cluster=self.cluster,
                )

            with allure.step("Check allowed other has full access to public container"):
                check_full_access_to_container(
                    other_wallet_allow.wallet_path,
                    cid,
                    object_oids.pop(),
                    file_path,
                    shell=self.shell,
                    cluster=self.cluster,
                )

    @allure.title("Testcase to validate FrostFS replication with eACL deny rules.")
    def test_extended_acl_deny_replication(
        self,
        wallets,
        eacl_full_placement_container_with_object,
    ):
        user_wallet = wallets.get_wallet()
        cid, oid, file_path = eacl_full_placement_container_with_object
        storage_nodes = self.cluster.storage_nodes
        storage_node = self.cluster.storage_nodes[0]

        with allure.step("Deny all operations for user via eACL"):
            eacl_deny = [
                EACLRule(access=EACLAccess.DENY, role=EACLRole.USER, operation=op)
                for op in EACLOperation
            ]
            eacl_deny += [
                EACLRule(access=EACLAccess.DENY, role=EACLRole.OTHERS, operation=op)
                for op in EACLOperation
            ]
            set_eacl(
                user_wallet.wallet_path,
                cid,
                create_eacl(cid, eacl_deny, shell=self.shell),
                shell=self.shell,
                endpoint=self.cluster.default_rpc_endpoint,
            )
            wait_for_cache_expired()

        with allure.step("Drop object to check replication"):
            drop_object(storage_node, cid=cid, oid=oid)

        storage_wallet_path = storage_node.get_wallet_path()
        with allure.step("Wait for dropped object replicated"):
            wait_object_replication(
                cid,
                oid,
                len(storage_nodes),
                self.shell,
                storage_nodes,
            )

    @allure.title("Testcase to validate FrostFS system operations with extended ACL")
    def test_extended_actions_system(self, wallets, eacl_container_with_objects):
        user_wallet = wallets.get_wallet()
        ir_wallet, storage_wallet = wallets.get_wallets_list(role=EACLRole.SYSTEM)[:2]

        cid, object_oids, file_path = eacl_container_with_objects
        endpoint = self.cluster.default_rpc_endpoint

        with allure.step("Check IR and STORAGE rules compliance"):
            assert not can_put_object(
                ir_wallet.wallet_path,
                cid,
                file_path,
                shell=self.shell,
                cluster=self.cluster,
                wallet_config=ir_wallet.config_path,
            )
            assert can_put_object(
                storage_wallet.wallet_path,
                cid,
                file_path,
                shell=self.shell,
                cluster=self.cluster,
                wallet_config=storage_wallet.config_path,
            )

            assert can_get_object(
                ir_wallet.wallet_path,
                cid,
                object_oids[0],
                file_path,
                shell=self.shell,
                cluster=self.cluster,
                wallet_config=ir_wallet.config_path,
            )
            assert can_get_object(
                storage_wallet.wallet_path,
                cid,
                object_oids[0],
                file_path,
                shell=self.shell,
                cluster=self.cluster,
                wallet_config=storage_wallet.config_path,
            )

            assert can_get_head_object(
                ir_wallet.wallet_path,
                cid,
                object_oids[0],
                shell=self.shell,
                endpoint=endpoint,
                wallet_config=ir_wallet.config_path,
            )
            assert can_get_head_object(
                storage_wallet.wallet_path,
                cid,
                object_oids[0],
                shell=self.shell,
                endpoint=endpoint,
                wallet_config=storage_wallet.config_path,
            )

            assert can_search_object(
                ir_wallet.wallet_path,
                cid,
                shell=self.shell,
                endpoint=endpoint,
                oid=object_oids[0],
                wallet_config=ir_wallet.config_path,
            )
            assert can_search_object(
                storage_wallet.wallet_path,
                cid,
                shell=self.shell,
                endpoint=endpoint,
                oid=object_oids[0],
                wallet_config=storage_wallet.config_path,
            )

            with pytest.raises(AssertionError):
                assert can_get_range_of_object(
                    wallet=ir_wallet.wallet_path,
                    cid=cid,
                    oid=object_oids[0],
                    shell=self.shell,
                    endpoint=endpoint,
                    wallet_config=ir_wallet.config_path,
                )
            with pytest.raises(AssertionError):
                assert can_get_range_of_object(
                    wallet=storage_wallet.wallet_path,
                    cid=cid,
                    oid=object_oids[0],
                    shell=self.shell,
                    endpoint=endpoint,
                    wallet_config=storage_wallet.config_path,
                )

            assert can_get_range_hash_of_object(
                wallet=ir_wallet.wallet_path,
                cid=cid,
                oid=object_oids[0],
                shell=self.shell,
                endpoint=endpoint,
                wallet_config=ir_wallet.config_path,
            )

            assert can_get_range_hash_of_object(
                wallet=storage_wallet.wallet_path,
                cid=cid,
                oid=object_oids[0],
                shell=self.shell,
                endpoint=endpoint,
                wallet_config=storage_wallet.config_path,
            )

            with pytest.raises(AssertionError):
                assert can_delete_object(
                    wallet=ir_wallet.wallet_path,
                    cid=cid,
                    oid=object_oids[0],
                    shell=self.shell,
                    endpoint=endpoint,
                    wallet_config=ir_wallet.config_path,
                )
            with pytest.raises(AssertionError):
                assert can_delete_object(
                    wallet=storage_wallet.wallet_path,
                    cid=cid,
                    oid=object_oids[0],
                    shell=self.shell,
                    endpoint=endpoint,
                    wallet_config=storage_wallet.config_path,
                )

        with allure.step("Deny all operations for SYSTEM via eACL"):
            set_eacl(
                user_wallet.wallet_path,
                cid,
                create_eacl(
                    cid=cid,
                    rules_list=[
                        EACLRule(access=EACLAccess.DENY, role=EACLRole.SYSTEM, operation=op)
                        for op in EACLOperation
                    ],
                    shell=self.shell,
                ),
                shell=self.shell,
                endpoint=endpoint,
            )
            wait_for_cache_expired()

        with allure.step("Check IR and STORAGE rules compliance with deny eACL"):
            assert not can_put_object(
                wallet=ir_wallet.wallet_path,
                cid=cid,
                file_name=file_path,
                shell=self.shell,
                cluster=self.cluster,
                wallet_config=ir_wallet.config_path,
            )
            assert not can_put_object(
                wallet=storage_wallet.wallet_path,
                cid=cid,
                file_name=file_path,
                shell=self.shell,
                cluster=self.cluster,
                wallet_config=storage_wallet.config_path,
            )

            with pytest.raises(AssertionError):
                assert can_get_object(
                    wallet=ir_wallet.wallet_path,
                    cid=cid,
                    oid=object_oids[0],
                    file_name=file_path,
                    shell=self.shell,
                    cluster=self.cluster,
                    wallet_config=ir_wallet.config_path,
                )
            with pytest.raises(AssertionError):
                assert can_get_object(
                    wallet=storage_wallet.wallet_path,
                    cid=cid,
                    oid=object_oids[0],
                    file_name=file_path,
                    shell=self.shell,
                    cluster=self.cluster,
                    wallet_config=storage_wallet.config_path,
                )

            with pytest.raises(AssertionError):
                assert can_get_head_object(
                    wallet=ir_wallet.wallet_path,
                    cid=cid,
                    oid=object_oids[0],
                    shell=self.shell,
                    endpoint=endpoint,
                    wallet_config=ir_wallet.config_path,
                )
            with pytest.raises(AssertionError):
                assert can_get_head_object(
                    wallet=storage_wallet.wallet_path,
                    cid=cid,
                    oid=object_oids[0],
                    shell=self.shell,
                    endpoint=endpoint,
                    wallet_config=storage_wallet.config_path,
                )

            with pytest.raises(AssertionError):
                assert can_search_object(
                    wallet=ir_wallet.wallet_path,
                    cid=cid,
                    shell=self.shell,
                    endpoint=endpoint,
                    oid=object_oids[0],
                    wallet_config=ir_wallet.config_path,
                )
            with pytest.raises(AssertionError):
                assert can_search_object(
                    wallet=storage_wallet.wallet_path,
                    cid=cid,
                    shell=self.shell,
                    endpoint=endpoint,
                    oid=object_oids[0],
                    wallet_config=storage_wallet.config_path,
                )

            with pytest.raises(AssertionError):
                assert can_get_range_of_object(
                    wallet=ir_wallet.wallet_path,
                    cid=cid,
                    oid=object_oids[0],
                    shell=self.shell,
                    endpoint=endpoint,
                    wallet_config=ir_wallet.config_path,
                )
            with pytest.raises(AssertionError):
                assert can_get_range_of_object(
                    wallet=storage_wallet.wallet_path,
                    cid=cid,
                    oid=object_oids[0],
                    shell=self.shell,
                    endpoint=endpoint,
                    wallet_config=storage_wallet.config_path,
                )

            with pytest.raises(AssertionError):
                assert can_get_range_hash_of_object(
                    wallet=ir_wallet.wallet_path,
                    cid=cid,
                    oid=object_oids[0],
                    shell=self.shell,
                    endpoint=endpoint,
                    wallet_config=ir_wallet.config_path,
                )
            with pytest.raises(AssertionError):
                assert can_get_range_hash_of_object(
                    wallet=storage_wallet.wallet_path,
                    cid=cid,
                    oid=object_oids[0],
                    shell=self.shell,
                    endpoint=endpoint,
                    wallet_config=storage_wallet.config_path,
                )

            with pytest.raises(AssertionError):
                assert can_delete_object(
                    wallet=ir_wallet.wallet_path,
                    cid=cid,
                    oid=object_oids[0],
                    shell=self.shell,
                    endpoint=endpoint,
                    wallet_config=ir_wallet.config_path,
                )
            with pytest.raises(AssertionError):
                assert can_delete_object(
                    wallet=storage_wallet.wallet_path,
                    cid=cid,
                    oid=object_oids[0],
                    shell=self.shell,
                    endpoint=endpoint,
                    wallet_config=storage_wallet.config_path,
                )

        with allure.step("Allow all operations for SYSTEM via eACL"):
            set_eacl(
                user_wallet.wallet_path,
                cid,
                create_eacl(
                    cid=cid,
                    rules_list=[
                        EACLRule(access=EACLAccess.ALLOW, role=EACLRole.SYSTEM, operation=op)
                        for op in EACLOperation
                    ],
                    shell=self.shell,
                ),
                shell=self.shell,
                endpoint=endpoint,
            )
            wait_for_cache_expired()

        with allure.step("Check IR and STORAGE rules compliance with allow eACL"):
            assert not can_put_object(
                wallet=ir_wallet.wallet_path,
                cid=cid,
                file_name=file_path,
                shell=self.shell,
                cluster=self.cluster,
                wallet_config=ir_wallet.config_path,
            )
            assert can_put_object(
                wallet=storage_wallet.wallet_path,
                cid=cid,
                file_name=file_path,
                shell=self.shell,
                cluster=self.cluster,
                wallet_config=storage_wallet.config_path,
            )

            assert can_get_object(
                wallet=ir_wallet.wallet_path,
                cid=cid,
                oid=object_oids[0],
                file_name=file_path,
                shell=self.shell,
                cluster=self.cluster,
                wallet_config=ir_wallet.config_path,
            )
            assert can_get_object(
                wallet=storage_wallet.wallet_path,
                cid=cid,
                oid=object_oids[0],
                file_name=file_path,
                shell=self.shell,
                cluster=self.cluster,
                wallet_config=storage_wallet.config_path,
            )

            assert can_get_head_object(
                wallet=ir_wallet.wallet_path,
                cid=cid,
                oid=object_oids[0],
                shell=self.shell,
                endpoint=endpoint,
                wallet_config=ir_wallet.config_path,
            )
            assert can_get_head_object(
                wallet=storage_wallet.wallet_path,
                cid=cid,
                oid=object_oids[0],
                shell=self.shell,
                endpoint=endpoint,
                wallet_config=storage_wallet.config_path,
            )

            assert can_search_object(
                wallet=ir_wallet.wallet_path,
                cid=cid,
                shell=self.shell,
                oid=object_oids[0],
                endpoint=endpoint,
                wallet_config=ir_wallet.config_path,
            )
            assert can_search_object(
                wallet=storage_wallet.wallet_path,
                cid=cid,
                shell=self.shell,
                oid=object_oids[0],
                endpoint=endpoint,
                wallet_config=storage_wallet.config_path,
            )

            with pytest.raises(AssertionError):
                assert can_get_range_of_object(
                    wallet=ir_wallet.wallet_path,
                    cid=cid,
                    oid=object_oids[0],
                    shell=self.shell,
                    endpoint=endpoint,
                    wallet_config=ir_wallet.config_path,
                )
            with pytest.raises(AssertionError):
                assert can_get_range_of_object(
                    wallet=storage_wallet.wallet_path,
                    cid=cid,
                    oid=object_oids[0],
                    shell=self.shell,
                    endpoint=endpoint,
                    wallet_config=storage_wallet.config_path,
                )

            assert can_get_range_hash_of_object(
                wallet=ir_wallet.wallet_path,
                cid=cid,
                oid=object_oids[0],
                shell=self.shell,
                endpoint=endpoint,
                wallet_config=ir_wallet.config_path,
            )

            assert can_get_range_hash_of_object(
                wallet=storage_wallet.wallet_path,
                cid=cid,
                oid=object_oids[0],
                shell=self.shell,
                endpoint=endpoint,
                wallet_config=storage_wallet.config_path,
            )

            with pytest.raises(AssertionError):
                assert can_delete_object(
                    wallet=ir_wallet.wallet_path,
                    cid=cid,
                    oid=object_oids[0],
                    shell=self.shell,
                    endpoint=endpoint,
                    wallet_config=ir_wallet.config_path,
                )
            with pytest.raises(AssertionError):
                assert can_delete_object(
                    wallet=storage_wallet.wallet_path,
                    cid=cid,
                    oid=object_oids[0],
                    shell=self.shell,
                    endpoint=endpoint,
                    wallet_config=storage_wallet.config_path,
                )
