import allure
import pytest
from cluster_test_base import ClusterTestBase
from python_keywords.acl import EACLRole
from python_keywords.container import create_container
from python_keywords.container_access import (
    check_full_access_to_container,
    check_no_access_to_container,
    check_read_only_container,
)
from python_keywords.frostfs_verbs import put_object_to_random_node
from wellknown_acl import PRIVATE_ACL_F, PUBLIC_ACL_F, READONLY_ACL_F


@pytest.mark.sanity
@pytest.mark.smoke
@pytest.mark.acl
@pytest.mark.acl_basic
class TestACLBasic(ClusterTestBase):
    @pytest.fixture(scope="function")
    def public_container(self, wallets):
        user_wallet = wallets.get_wallet()
        with allure.step("Create public container"):
            cid_public = create_container(
                user_wallet.wallet_path,
                basic_acl=PUBLIC_ACL_F,
                shell=self.shell,
                endpoint=self.cluster.default_rpc_endpoint,
            )

        yield cid_public

        # with allure.step('Delete public container'):
        #     delete_container(user_wallet.wallet_path, cid_public)

    @pytest.fixture(scope="function")
    def private_container(self, wallets):
        user_wallet = wallets.get_wallet()
        with allure.step("Create private container"):
            cid_private = create_container(
                user_wallet.wallet_path,
                basic_acl=PRIVATE_ACL_F,
                shell=self.shell,
                endpoint=self.cluster.default_rpc_endpoint,
            )

        yield cid_private

        # with allure.step('Delete private container'):
        #     delete_container(user_wallet.wallet_path, cid_private)

    @pytest.fixture(scope="function")
    def read_only_container(self, wallets):
        user_wallet = wallets.get_wallet()
        with allure.step("Create public readonly container"):
            cid_read_only = create_container(
                user_wallet.wallet_path,
                basic_acl=READONLY_ACL_F,
                shell=self.shell,
                endpoint=self.cluster.default_rpc_endpoint,
            )

        yield cid_read_only

        # with allure.step('Delete public readonly container'):
        #     delete_container(user_wallet.wallet_path, cid_read_only)

    @allure.title("Test basic ACL on public container")
    def test_basic_acl_public(self, wallets, public_container, file_path):
        """
        Test basic ACL set during public container creation.
        """
        user_wallet = wallets.get_wallet()
        other_wallet = wallets.get_wallet(role=EACLRole.OTHERS)
        cid = public_container
        for wallet, desc in ((user_wallet, "owner"), (other_wallet, "other users")):
            with allure.step("Add test objects to container"):
                # We create new objects for each wallet because check_full_access_to_container
                # deletes the object
                owner_object_oid = put_object_to_random_node(
                    user_wallet.wallet_path,
                    file_path,
                    cid,
                    shell=self.shell,
                    cluster=self.cluster,
                    attributes={"created": "owner"},
                )
                other_object_oid = put_object_to_random_node(
                    other_wallet.wallet_path,
                    file_path,
                    cid,
                    shell=self.shell,
                    cluster=self.cluster,
                    attributes={"created": "other"},
                )
            with allure.step(f"Check {desc} has full access to public container"):
                check_full_access_to_container(
                    wallet.wallet_path,
                    cid,
                    owner_object_oid,
                    file_path,
                    shell=self.shell,
                    cluster=self.cluster,
                )
                check_full_access_to_container(
                    wallet.wallet_path,
                    cid,
                    other_object_oid,
                    file_path,
                    shell=self.shell,
                    cluster=self.cluster,
                )

    @allure.title("Test basic ACL on private container")
    def test_basic_acl_private(self, wallets, private_container, file_path):
        """
        Test basic ACL set during private container creation.
        """
        user_wallet = wallets.get_wallet()
        other_wallet = wallets.get_wallet(role=EACLRole.OTHERS)
        cid = private_container
        with allure.step("Add test objects to container"):
            owner_object_oid = put_object_to_random_node(
                user_wallet.wallet_path, file_path, cid, shell=self.shell, cluster=self.cluster
            )

        with allure.step("Check only owner has full access to private container"):
            with allure.step("Check no one except owner has access to operations with container"):
                check_no_access_to_container(
                    other_wallet.wallet_path,
                    cid,
                    owner_object_oid,
                    file_path,
                    shell=self.shell,
                    cluster=self.cluster,
                )

            with allure.step("Check owner has full access to private container"):
                check_full_access_to_container(
                    user_wallet.wallet_path,
                    cid,
                    owner_object_oid,
                    file_path,
                    shell=self.shell,
                    cluster=self.cluster,
                )

    @allure.title("Test basic ACL on readonly container")
    def test_basic_acl_readonly(self, wallets, client_shell, read_only_container, file_path):
        """
        Test basic ACL Operations for Read-Only Container.
        """
        user_wallet = wallets.get_wallet()
        other_wallet = wallets.get_wallet(role=EACLRole.OTHERS)
        cid = read_only_container

        with allure.step("Add test objects to container"):
            object_oid = put_object_to_random_node(
                user_wallet.wallet_path, file_path, cid, shell=client_shell, cluster=self.cluster
            )

        with allure.step("Check other has read-only access to operations with container"):
            check_read_only_container(
                other_wallet.wallet_path,
                cid,
                object_oid,
                file_path,
                shell=client_shell,
                cluster=self.cluster,
            )

        with allure.step("Check owner has full access to public container"):
            check_full_access_to_container(
                user_wallet.wallet_path,
                cid,
                object_oid,
                file_path,
                shell=client_shell,
                cluster=self.cluster,
            )
