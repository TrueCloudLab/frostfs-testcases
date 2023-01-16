import logging
import os
import uuid
from typing import Optional

import allure
import pytest
from cluster_test_base import ClusterTestBase
from common import ASSETS_DIR, FREE_STORAGE, WALLET_PASS
from file_helper import generate_file
from grpc_responses import OBJECT_ACCESS_DENIED, OBJECT_NOT_FOUND
from neofs_testlib.utils.wallet import init_wallet
from python_keywords.acl import (
    EACLAccess,
    EACLOperation,
    EACLRole,
    EACLRule,
    create_eacl,
    form_bearertoken_file,
    set_eacl,
)
from python_keywords.container import create_container
from python_keywords.neofs_verbs import put_object_to_random_node
from python_keywords.payment_neogo import deposit_gas, transfer_gas
from python_keywords.storage_group import (
    delete_storagegroup,
    get_storagegroup,
    list_storagegroup,
    put_storagegroup,
    verify_get_storage_group,
    verify_list_storage_group,
)

logger = logging.getLogger("NeoLogger")
deposit = 30


@pytest.mark.parametrize(
    "object_size",
    [pytest.lazy_fixture("simple_object_size"), pytest.lazy_fixture("complex_object_size")],
    ids=["simple object", "complex object"],
)
@pytest.mark.sanity
@pytest.mark.acl
@pytest.mark.storage_group
class TestStorageGroup(ClusterTestBase):
    @pytest.fixture(autouse=True)
    def prepare_two_wallets(self, default_wallet):
        self.main_wallet = default_wallet
        self.other_wallet = os.path.join(os.getcwd(), ASSETS_DIR, f"{str(uuid.uuid4())}.json")
        init_wallet(self.other_wallet, WALLET_PASS)
        if not FREE_STORAGE:
            main_chain = self.cluster.main_chain_nodes[0]
            deposit = 30
            transfer_gas(
                shell=self.shell,
                amount=deposit + 1,
                main_chain=main_chain,
                wallet_to_path=self.other_wallet,
                wallet_to_password=WALLET_PASS,
            )
            deposit_gas(
                shell=self.shell,
                amount=deposit,
                main_chain=main_chain,
                wallet_from_path=self.other_wallet,
                wallet_from_password=WALLET_PASS,
            )

    @allure.title("Test Storage Group in Private Container")
    def test_storagegroup_basic_private_container(self, object_size, max_object_size):
        cid = create_container(
            self.main_wallet, shell=self.shell, endpoint=self.cluster.default_rpc_endpoint
        )
        file_path = generate_file(object_size)
        oid = put_object_to_random_node(self.main_wallet, file_path, cid, self.shell, self.cluster)
        objects = [oid]
        storage_group = put_storagegroup(
            shell=self.shell,
            endpoint=self.cluster.default_rpc_endpoint,
            wallet=self.main_wallet,
            cid=cid,
            objects=objects,
        )

        self.expect_success_for_storagegroup_operations(
            wallet=self.main_wallet,
            cid=cid,
            obj_list=objects,
            object_size=object_size,
            max_object_size=max_object_size,
        )
        self.expect_failure_for_storagegroup_operations(
            wallet=self.other_wallet,
            cid=cid,
            obj_list=objects,
            gid=storage_group,
        )
        self.storagegroup_operations_by_system_ro_container(
            wallet=self.main_wallet,
            cid=cid,
            obj_list=objects,
            object_size=object_size,
            max_object_size=max_object_size,
        )

    @allure.title("Test Storage Group in Public Container")
    def test_storagegroup_basic_public_container(self, object_size, max_object_size):
        cid = create_container(
            self.main_wallet,
            basic_acl="public-read-write",
            shell=self.shell,
            endpoint=self.cluster.default_rpc_endpoint,
        )
        file_path = generate_file(object_size)
        oid = put_object_to_random_node(
            self.main_wallet, file_path, cid, shell=self.shell, cluster=self.cluster
        )
        objects = [oid]
        self.expect_success_for_storagegroup_operations(
            wallet=self.main_wallet,
            cid=cid,
            obj_list=objects,
            object_size=object_size,
            max_object_size=max_object_size,
        )
        self.expect_success_for_storagegroup_operations(
            wallet=self.other_wallet,
            cid=cid,
            obj_list=objects,
            object_size=object_size,
            max_object_size=max_object_size,
        )
        self.storagegroup_operations_by_system_ro_container(
            wallet=self.main_wallet,
            cid=cid,
            obj_list=objects,
            object_size=object_size,
            max_object_size=max_object_size,
        )

    @allure.title("Test Storage Group in Read-Only Container")
    def test_storagegroup_basic_ro_container(self, object_size, max_object_size):
        cid = create_container(
            self.main_wallet,
            basic_acl="public-read",
            shell=self.shell,
            endpoint=self.cluster.default_rpc_endpoint,
        )
        file_path = generate_file(object_size)
        oid = put_object_to_random_node(
            self.main_wallet, file_path, cid, shell=self.shell, cluster=self.cluster
        )
        objects = [oid]
        self.expect_success_for_storagegroup_operations(
            wallet=self.main_wallet,
            cid=cid,
            obj_list=objects,
            object_size=object_size,
            max_object_size=max_object_size,
        )
        self.storagegroup_operations_by_other_ro_container(
            owner_wallet=self.main_wallet,
            other_wallet=self.other_wallet,
            cid=cid,
            obj_list=objects,
            object_size=object_size,
            max_object_size=max_object_size,
        )
        self.storagegroup_operations_by_system_ro_container(
            wallet=self.main_wallet,
            cid=cid,
            obj_list=objects,
            object_size=object_size,
            max_object_size=max_object_size,
        )

    @allure.title("Test Storage Group with Bearer Allow")
    def test_storagegroup_bearer_allow(self, object_size, max_object_size):
        cid = create_container(
            self.main_wallet,
            basic_acl="eacl-public-read-write",
            shell=self.shell,
            endpoint=self.cluster.default_rpc_endpoint,
        )
        file_path = generate_file(object_size)
        oid = put_object_to_random_node(
            self.main_wallet, file_path, cid, shell=self.shell, cluster=self.cluster
        )
        objects = [oid]
        self.expect_success_for_storagegroup_operations(
            wallet=self.main_wallet,
            cid=cid,
            obj_list=objects,
            object_size=object_size,
            max_object_size=max_object_size,
        )
        storage_group = put_storagegroup(
            self.shell, self.cluster.default_rpc_endpoint, self.main_wallet, cid, objects
        )
        eacl_deny = [
            EACLRule(access=EACLAccess.DENY, role=role, operation=op)
            for op in EACLOperation
            for role in EACLRole
        ]
        set_eacl(
            self.main_wallet,
            cid,
            create_eacl(cid, eacl_deny, shell=self.shell),
            shell=self.shell,
            endpoint=self.cluster.default_rpc_endpoint,
        )
        self.expect_failure_for_storagegroup_operations(
            self.main_wallet, cid, objects, storage_group
        )
        bearer_file = form_bearertoken_file(
            self.main_wallet,
            cid,
            [
                EACLRule(operation=op, access=EACLAccess.ALLOW, role=EACLRole.USER)
                for op in EACLOperation
            ],
            shell=self.shell,
            endpoint=self.cluster.default_rpc_endpoint,
        )
        self.expect_success_for_storagegroup_operations(
            wallet=self.main_wallet,
            cid=cid,
            obj_list=objects,
            object_size=object_size,
            max_object_size=max_object_size,
            bearer=bearer_file,
        )

    @allure.title("Test to check Storage Group lifetime")
    def test_storagegroup_lifetime(self, object_size):
        cid = create_container(
            self.main_wallet, shell=self.shell, endpoint=self.cluster.default_rpc_endpoint
        )
        file_path = generate_file(object_size)
        oid = put_object_to_random_node(
            self.main_wallet, file_path, cid, shell=self.shell, cluster=self.cluster
        )
        objects = [oid]
        storage_group = put_storagegroup(
            self.shell,
            self.cluster.default_rpc_endpoint,
            self.main_wallet,
            cid,
            objects,
            lifetime=1,
        )
        with allure.step("Tick two epochs"):
            for _ in range(2):
                self.tick_epoch()
        self.wait_for_epochs_align()
        with pytest.raises(Exception, match=OBJECT_NOT_FOUND):
            get_storagegroup(
                shell=self.shell,
                endpoint=self.cluster.default_rpc_endpoint,
                wallet=self.main_wallet,
                cid=cid,
                gid=storage_group,
            )

    @allure.step("Run Storage Group Operations And Expect Success")
    def expect_success_for_storagegroup_operations(
        self,
        wallet: str,
        cid: str,
        obj_list: list,
        object_size: int,
        max_object_size: int,
        bearer: Optional[str] = None,
    ):
        """
        This func verifies if the Object's owner is allowed to
        Put, List, Get and Delete the Storage Group which contains
        the Object.
        """
        storage_group = put_storagegroup(
            self.shell, self.cluster.default_rpc_endpoint, wallet, cid, obj_list, bearer
        )
        verify_list_storage_group(
            shell=self.shell,
            endpoint=self.cluster.default_rpc_endpoint,
            wallet=wallet,
            cid=cid,
            gid=storage_group,
            bearer=bearer,
        )
        verify_get_storage_group(
            shell=self.shell,
            cluster=self.cluster,
            wallet=wallet,
            cid=cid,
            gid=storage_group,
            obj_list=obj_list,
            object_size=object_size,
            max_object_size=max_object_size,
            bearer=bearer,
        )
        delete_storagegroup(
            shell=self.shell,
            endpoint=self.cluster.default_rpc_endpoint,
            wallet=wallet,
            cid=cid,
            gid=storage_group,
            bearer=bearer,
        )

    @allure.step("Run Storage Group Operations And Expect Failure")
    def expect_failure_for_storagegroup_operations(
        self, wallet: str, cid: str, obj_list: list, gid: str
    ):
        """
        This func verifies if the Object's owner isn't allowed to
        Put, List, Get and Delete the Storage Group which contains
        the Object.
        """
        with pytest.raises(Exception, match=OBJECT_ACCESS_DENIED):
            put_storagegroup(
                shell=self.shell,
                endpoint=self.cluster.default_rpc_endpoint,
                wallet=wallet,
                cid=cid,
                objects=obj_list,
            )
        with pytest.raises(Exception, match=OBJECT_ACCESS_DENIED):
            list_storagegroup(
                shell=self.shell, endpoint=self.cluster.default_rpc_endpoint, wallet=wallet, cid=cid
            )
        with pytest.raises(Exception, match=OBJECT_ACCESS_DENIED):
            get_storagegroup(
                shell=self.shell,
                endpoint=self.cluster.default_rpc_endpoint,
                wallet=wallet,
                cid=cid,
                gid=gid,
            )
        with pytest.raises(Exception, match=OBJECT_ACCESS_DENIED):
            delete_storagegroup(
                shell=self.shell,
                endpoint=self.cluster.default_rpc_endpoint,
                wallet=wallet,
                cid=cid,
                gid=gid,
            )

    @allure.step("Run Storage Group Operations On Other's Behalf In RO Container")
    def storagegroup_operations_by_other_ro_container(
        self,
        owner_wallet: str,
        other_wallet: str,
        cid: str,
        obj_list: list,
        object_size: int,
        max_object_size: int,
    ):
        storage_group = put_storagegroup(
            self.shell, self.cluster.default_rpc_endpoint, owner_wallet, cid, obj_list
        )
        with pytest.raises(Exception, match=OBJECT_ACCESS_DENIED):
            put_storagegroup(
                shell=self.shell,
                endpoint=self.cluster.default_rpc_endpoint,
                wallet=other_wallet,
                cid=cid,
                objects=obj_list,
            )
        verify_list_storage_group(
            shell=self.shell,
            endpoint=self.cluster.default_rpc_endpoint,
            wallet=other_wallet,
            cid=cid,
            gid=storage_group,
        )
        verify_get_storage_group(
            shell=self.shell,
            cluster=self.cluster,
            wallet=other_wallet,
            cid=cid,
            gid=storage_group,
            obj_list=obj_list,
            object_size=object_size,
            max_object_size=max_object_size,
        )
        with pytest.raises(Exception, match=OBJECT_ACCESS_DENIED):
            delete_storagegroup(
                shell=self.shell,
                endpoint=self.cluster.default_rpc_endpoint,
                wallet=other_wallet,
                cid=cid,
                gid=storage_group,
            )

    @allure.step("Run Storage Group Operations On Systems's Behalf In RO Container")
    def storagegroup_operations_by_system_ro_container(
        self,
        wallet: str,
        cid: str,
        obj_list: list,
        object_size: int,
        max_object_size: int,
    ):
        """
        In this func we create a Storage Group on Inner Ring's key behalf
        and include an Object created on behalf of some user. We expect
        that System key is granted to make all operations except PUT and DELETE.
        """
        ir_node = self.cluster.ir_nodes[0]
        ir_wallet_path = ir_node.get_wallet_path()
        ir_wallet_password = ir_node.get_wallet_password()
        ir_wallet_config = ir_node.get_wallet_config_path()

        if not FREE_STORAGE:
            main_chain = self.cluster.main_chain_nodes[0]
            deposit = 30
            transfer_gas(
                shell=self.shell,
                amount=deposit + 1,
                main_chain=main_chain,
                wallet_to_path=ir_wallet_path,
                wallet_to_password=ir_wallet_password,
            )
            deposit_gas(
                shell=self.shell,
                amount=deposit,
                main_chain=main_chain,
                wallet_from_path=ir_wallet_path,
                wallet_from_password=ir_wallet_password,
            )
        storage_group = put_storagegroup(
            self.shell, self.cluster.default_rpc_endpoint, wallet, cid, obj_list
        )
        with pytest.raises(Exception, match=OBJECT_ACCESS_DENIED):
            put_storagegroup(
                self.shell,
                self.cluster.default_rpc_endpoint,
                ir_wallet_path,
                cid,
                obj_list,
                wallet_config=ir_wallet_config,
            )
        verify_list_storage_group(
            shell=self.shell,
            endpoint=self.cluster.default_rpc_endpoint,
            wallet=ir_wallet_path,
            cid=cid,
            gid=storage_group,
            wallet_config=ir_wallet_config,
        )
        verify_get_storage_group(
            shell=self.shell,
            cluster=self.cluster,
            wallet=ir_wallet_path,
            cid=cid,
            gid=storage_group,
            obj_list=obj_list,
            object_size=object_size,
            max_object_size=max_object_size,
            wallet_config=ir_wallet_config,
        )
        with pytest.raises(Exception, match=OBJECT_ACCESS_DENIED):
            delete_storagegroup(
                shell=self.shell,
                endpoint=self.cluster.default_rpc_endpoint,
                wallet=ir_wallet_path,
                cid=cid,
                gid=storage_group,
                wallet_config=ir_wallet_config,
            )
