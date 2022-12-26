import allure
import pytest
from cluster_test_base import ClusterTestBase
from common import (
    HTTP_GATE_SERVICE_NAME_REGEX,
    S3_GATE_SERVICE_NAME_REGEX,
    STORAGE_NODE_SERVICE_NAME_REGEX,
)
from k6 import LoadParams
from load import (
    clear_cache_and_data,
    get_services_endpoints,
    init_s3_client,
    multi_node_k6_run,
    prepare_k6_instances,
    start_stopped_nodes,
    stop_unused_nodes,
)
from load_params import (
    CONTAINER_PLACEMENT_POLICY,
    CONTAINERS_COUNT,
    DELETERS,
    LOAD_NODE_SSH_PRIVATE_KEY_PATH,
    LOAD_NODE_SSH_USER,
    LOAD_NODES,
    LOAD_NODES_COUNT,
    LOAD_TIME,
    LOAD_TYPE,
    OBJ_COUNT,
    OBJ_SIZE,
    OUT_FILE,
    READERS,
    STORAGE_NODE_COUNT,
    WRITERS,
)
from neofs_testlib.hosting import Hosting

ENDPOINTS_ATTRIBUTES = {
    "http": {"regex": HTTP_GATE_SERVICE_NAME_REGEX, "endpoint_attribute": "endpoint"},
    "grpc": {"regex": STORAGE_NODE_SERVICE_NAME_REGEX, "endpoint_attribute": "rpc_endpoint"},
    "s3": {"regex": S3_GATE_SERVICE_NAME_REGEX, "endpoint_attribute": "endpoint"},
}


@pytest.mark.load
class TestLoad(ClusterTestBase):
    @pytest.fixture(autouse=True)
    def clear_cache_and_data(self, hosting: Hosting):
        clear_cache_and_data(hosting=hosting)
        yield
        start_stopped_nodes()

    @pytest.fixture(scope="session", autouse=True)
    def init_s3_client(self, hosting: Hosting):
        if "s3" in list(map(lambda x: x.lower(), LOAD_TYPE)):
            init_s3_client(
                load_nodes=LOAD_NODES,
                login=LOAD_NODE_SSH_USER,
                pkey=LOAD_NODE_SSH_PRIVATE_KEY_PATH,
                hosting=hosting,
                container_placement_policy=CONTAINER_PLACEMENT_POLICY,
            )

    @pytest.mark.parametrize("obj_size, out_file", list(zip(OBJ_SIZE, OUT_FILE)))
    @pytest.mark.parametrize("writers, readers, deleters", list(zip(WRITERS, READERS, DELETERS)))
    @pytest.mark.parametrize("load_time", LOAD_TIME)
    @pytest.mark.parametrize("node_count", STORAGE_NODE_COUNT)
    @pytest.mark.parametrize("containers_count", CONTAINERS_COUNT)
    @pytest.mark.parametrize("load_type", LOAD_TYPE)
    @pytest.mark.parametrize("obj_count", OBJ_COUNT)
    @pytest.mark.parametrize("load_nodes_count", LOAD_NODES_COUNT)
    @pytest.mark.benchmark
    @pytest.mark.grpc
    def test_custom_load(
        self,
        obj_size,
        out_file,
        writers,
        readers,
        deleters,
        load_time,
        node_count,
        obj_count,
        load_type,
        load_nodes_count,
        containers_count,
        hosting: Hosting,
    ):
        allure.dynamic.title(
            f"Load test - node_count = {node_count}, "
            f"writers = {writers} readers = {readers}, "
            f"deleters = {deleters}, obj_size = {obj_size}, "
            f"load_time = {load_time}"
        )
        stop_unused_nodes(self.cluster.storage_nodes, node_count)
        with allure.step("Get endpoints"):
            endpoints_list = get_services_endpoints(
                hosting=hosting,
                service_name_regex=ENDPOINTS_ATTRIBUTES[LOAD_TYPE]["regex"],
                endpoint_attribute=ENDPOINTS_ATTRIBUTES[LOAD_TYPE]["endpoint_attribute"],
            )
            endpoints = ",".join(endpoints_list[:node_count])
        load_params = LoadParams(
            endpoint=endpoints,
            obj_size=obj_size,
            containers_count=containers_count,
            out_file=out_file,
            obj_count=obj_count,
            writers=writers,
            readers=readers,
            deleters=deleters,
            load_time=load_time,
            load_type=load_type,
        )
        load_nodes_list = LOAD_NODES[:load_nodes_count]
        k6_load_instances = prepare_k6_instances(
            load_nodes=load_nodes_list,
            login=LOAD_NODE_SSH_USER,
            pkey=LOAD_NODE_SSH_PRIVATE_KEY_PATH,
            load_params=load_params,
        )
        with allure.step("Run load"):
            multi_node_k6_run(k6_load_instances)
