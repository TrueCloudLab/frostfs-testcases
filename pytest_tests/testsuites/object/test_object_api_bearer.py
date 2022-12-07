import allure
import pytest
from cluster import Cluster
from container import REP_2_FOR_3_NODES_PLACEMENT_RULE, SINGLE_PLACEMENT_RULE, create_container
from epoch import get_epoch
from neofs_testlib.shell import Shell
from neofs_verbs import delete_object, get_object
from pytest import FixtureRequest
from python_keywords.acl import EACLAccess, EACLOperation, EACLRole, EACLRule, form_bearertoken_file
from wellknown_acl import EACL_PUBLIC_READ_WRITE

from helpers.container import StorageContainer, StorageContainerInfo
from helpers.test_control import expect_not_raises
from helpers.wallet import WalletFile
from steps.cluster_test_base import ClusterTestBase
from steps.storage_object import StorageObjectInfo


@pytest.fixture(scope="module")
@allure.title("Create bearer token for OTHERS with all operations allowed for all containers")
def bearer_token_file_all_allow(default_wallet: str, client_shell: Shell, cluster: Cluster) -> str:
    bearer = form_bearertoken_file(
        default_wallet,
        "",
        [
            EACLRule(operation=op, access=EACLAccess.ALLOW, role=EACLRole.OTHERS)
            for op in EACLOperation
        ],
        shell=client_shell,
        endpoint=cluster.default_rpc_endpoint,
    )

    return bearer


@pytest.fixture(scope="module")
@allure.title("Create user container for bearer token usage")
def user_container(
    default_wallet: str, client_shell: Shell, cluster: Cluster, request: FixtureRequest
) -> StorageContainer:
    container_id = create_container(
        default_wallet,
        shell=client_shell,
        rule=request.param,
        basic_acl=EACL_PUBLIC_READ_WRITE,
        endpoint=cluster.default_rpc_endpoint,
    )
    # Deliberately using s3gate wallet here to test bearer token
    s3gate = cluster.s3gates[0]
    return StorageContainer(
        StorageContainerInfo(container_id, WalletFile.from_node(s3gate)),
        client_shell,
        cluster,
    )


@pytest.fixture()
def storage_objects(
    user_container: StorageContainer,
    bearer_token_file_all_allow: str,
    request: FixtureRequest,
    client_shell: Shell,
    cluster: Cluster,
) -> list[StorageObjectInfo]:
    epoch = get_epoch(client_shell, cluster)
    storage_objects: list[StorageObjectInfo] = []
    for node in cluster.storage_nodes:
        storage_objects.append(
            user_container.generate_object(
                request.param,
                epoch + 3,
                bearer_token=bearer_token_file_all_allow,
                endpoint=node.get_rpc_endpoint(),
            )
        )
    return storage_objects


@pytest.mark.smoke
@pytest.mark.bearer
class TestObjectApiWithBearerToken(ClusterTestBase):
    @pytest.mark.parametrize(
        "user_container",
        [SINGLE_PLACEMENT_RULE],
        ids=["single replica for all nodes placement rule"],
        indirect=True,
    )
    @pytest.mark.parametrize(
        "storage_objects",
        [pytest.lazy_fixture("simple_object_size"), pytest.lazy_fixture("complex_object_size")],
        ids=["simple object", "complex object"],
        indirect=True,
    )
    def test_delete_object_with_s3_wallet_bearer(
        self,
        storage_objects: list[StorageObjectInfo],
        bearer_token_file_all_allow: str,
        request: FixtureRequest,
    ):
        allure.dynamic.title(
            f"Check that objects can be deleted from any node using s3gate wallet with bearer "
            f"token for {request.node.callspec.id}"
        )

        s3_gate_wallet = self.cluster.s3gates[0]
        with allure.step("Try to delete each object from first storage node"):
            for storage_object in storage_objects:
                with expect_not_raises():
                    delete_object(
                        s3_gate_wallet.get_wallet_path(),
                        storage_object.cid,
                        storage_object.oid,
                        self.shell,
                        endpoint=self.cluster.default_rpc_endpoint,
                        bearer=bearer_token_file_all_allow,
                        wallet_config=s3_gate_wallet.get_wallet_config_path(),
                    )

    @pytest.mark.parametrize(
        "user_container",
        [REP_2_FOR_3_NODES_PLACEMENT_RULE],
        ids=["2 replicas for 3 nodes placement rule"],
        indirect=True,
    )
    @pytest.mark.parametrize(
        "file_size",
        [pytest.lazy_fixture("simple_object_size"), pytest.lazy_fixture("complex_object_size")],
        ids=["simple object", "complex object"],
    )
    def test_get_object_with_s3_wallet_bearer_from_all_nodes(
        self,
        user_container: StorageContainer,
        file_size: int,
        bearer_token_file_all_allow: str,
        request: FixtureRequest,
    ):
        allure.dynamic.title(
            "Check that objects can be deleted from any node using s3gate wallet with bearer "
            f"token for {request.node.callspec.id}"
        )

        s3_gate_wallet = self.cluster.s3gates[0]
        with allure.step("Put one object to container"):
            epoch = self.get_epoch()
            storage_object = user_container.generate_object(
                file_size, epoch + 3, bearer_token=bearer_token_file_all_allow
            )

        with allure.step("Try to fetch object from each storage node"):
            for node in self.cluster.storage_nodes:
                with expect_not_raises():
                    get_object(
                        s3_gate_wallet.get_wallet_path(),
                        storage_object.cid,
                        storage_object.oid,
                        self.shell,
                        endpoint=node.get_rpc_endpoint(),
                        bearer=bearer_token_file_all_allow,
                        wallet_config=s3_gate_wallet.get_wallet_config_path(),
                    )
