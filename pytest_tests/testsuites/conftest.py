import logging
import os
import re
import shutil
import uuid
from datetime import datetime

import allure
import pytest
import yaml
from binary_version_helper import get_local_binaries_versions, get_remote_binaries_versions
from cluster import Cluster
from common import (
    ASSETS_DIR,
    BACKGROUND_LOAD_MAX_TIME,
    BACKGROUND_OBJ_SIZE,
    BACKGROUND_READERS_COUNT,
    BACKGROUND_WRITERS_COUNT,
    COMPLEX_OBJECT_CHUNKS_COUNT,
    COMPLEX_OBJECT_TAIL_SIZE,
    FREE_STORAGE,
    HOSTING_CONFIG_FILE,
    LOAD_NODE_SSH_PRIVATE_KEY_PATH,
    LOAD_NODE_SSH_USER,
    LOAD_NODES,
    SIMPLE_OBJECT_SIZE,
    STORAGE_NODE_SERVICE_NAME_REGEX,
    WALLET_PASS,
)
from env_properties import save_env_properties
from k6 import LoadParams
from load import get_services_endpoints, prepare_k6_instances
from neofs_testlib.hosting import Hosting
from neofs_testlib.reporter import AllureHandler, get_reporter
from neofs_testlib.shell import LocalShell, Shell
from neofs_testlib.utils.wallet import init_wallet
from payment_neogo import deposit_gas, transfer_gas
from pytest import FixtureRequest
from python_keywords.neofs_verbs import get_netmap_netinfo
from python_keywords.node_management import storage_node_healthcheck

from helpers.wallet import WalletFactory

logger = logging.getLogger("NeoLogger")


def pytest_collection_modifyitems(items):
    # Make network tests last based on @pytest.mark.node_mgmt
    def priority(item: pytest.Item) -> int:
        is_node_mgmt_test = item.get_closest_marker("node_mgmt")
        return 0 if not is_node_mgmt_test else 1

    items.sort(key=lambda item: priority(item))


@pytest.fixture(scope="session")
def configure_testlib():
    get_reporter().register_handler(AllureHandler())
    yield


@pytest.fixture(scope="session")
def client_shell(configure_testlib) -> Shell:
    yield LocalShell()


@pytest.fixture(scope="session")
def hosting(configure_testlib) -> Hosting:
    with open(HOSTING_CONFIG_FILE, "r") as file:
        hosting_config = yaml.full_load(file)

    hosting_instance = Hosting()
    hosting_instance.configure(hosting_config)

    yield hosting_instance


@pytest.fixture(scope="session")
def require_multiple_hosts(hosting: Hosting):
    """Designates tests that require environment with multiple hosts.

    These tests will be skipped on an environment that has only 1 host.
    """
    if len(hosting.hosts) <= 1:
        pytest.skip("Test only works with multiple hosts")
    yield


@pytest.fixture(scope="session")
def max_object_size(cluster: Cluster, client_shell: Shell) -> int:
    storage_node = cluster.storage_nodes[0]
    net_info = get_netmap_netinfo(
        wallet=storage_node.get_wallet_path(),
        wallet_config=storage_node.get_wallet_config_path(),
        endpoint=storage_node.get_rpc_endpoint(),
        shell=client_shell,
    )
    yield net_info["maximum_object_size"]


@pytest.fixture(scope="session")
def simple_object_size(max_object_size: int) -> int:
    yield int(SIMPLE_OBJECT_SIZE) if int(SIMPLE_OBJECT_SIZE) < max_object_size else max_object_size


@pytest.fixture(scope="session")
def complex_object_size(max_object_size: int) -> int:
    return max_object_size * int(COMPLEX_OBJECT_CHUNKS_COUNT) + int(COMPLEX_OBJECT_TAIL_SIZE)


@pytest.fixture(scope="session")
def wallet_factory(temp_directory: str, client_shell: Shell, cluster: Cluster) -> WalletFactory:
    return WalletFactory(temp_directory, client_shell, cluster)


@pytest.fixture(scope="session")
def cluster(hosting: Hosting) -> Cluster:
    yield Cluster(hosting)


@pytest.fixture(scope="session", autouse=True)
@allure.title("Check binary versions")
def check_binary_versions(request, hosting: Hosting, client_shell: Shell):
    local_versions = get_local_binaries_versions(client_shell)
    remote_versions = get_remote_binaries_versions(hosting)

    all_versions = {**local_versions, **remote_versions}
    save_env_properties(request.config, all_versions)


@pytest.fixture(scope="session")
@allure.title("Prepare tmp directory")
def temp_directory():
    with allure.step("Prepare tmp directory"):
        full_path = os.path.join(os.getcwd(), ASSETS_DIR)
        shutil.rmtree(full_path, ignore_errors=True)
        os.mkdir(full_path)

    yield full_path

    with allure.step("Remove tmp directory"):
        shutil.rmtree(full_path)


@pytest.fixture(scope="session", autouse=True)
@allure.title("Collect logs")
def collect_logs(temp_directory, hosting: Hosting):
    start_time = datetime.utcnow()
    yield
    end_time = datetime.utcnow()

    # Dump logs to temp directory (because they might be too large to keep in RAM)
    logs_dir = os.path.join(temp_directory, "logs")
    dump_logs(hosting, logs_dir, start_time, end_time)
    attach_logs(logs_dir)
    check_logs(logs_dir)


@pytest.fixture(scope="session", autouse=True)
@allure.title("Run health check for all storage nodes")
def run_health_check(collect_logs, cluster: Cluster):
    failed_nodes = []
    for node in cluster.storage_nodes:
        health_check = storage_node_healthcheck(node)
        if health_check.health_status != "READY" or health_check.network_status != "ONLINE":
            failed_nodes.append(node)

    if failed_nodes:
        raise AssertionError(f"Nodes {failed_nodes} are not healthy")


@pytest.fixture(scope="session")
def background_grpc_load(client_shell):
    registry_file = os.path.join("/tmp/", f"{str(uuid.uuid4())}.bolt")
    prepare_file = os.path.join("/tmp/", f"{str(uuid.uuid4())}.json")
    allure.dynamic.title(
        f"Start background load with parameters: "
        f"writers = {BACKGROUND_WRITERS_COUNT}, "
        f"obj_size = {BACKGROUND_OBJ_SIZE}, "
        f"load_time = {BACKGROUND_LOAD_MAX_TIME}"
        f"prepare_json = {prepare_file}"
    )
    with allure.step("Get endpoints"):
        endpoints_list = get_services_endpoints(
            hosting=hosting,
            service_name_regex=STORAGE_NODE_SERVICE_NAME_REGEX,
            endpoint_attribute="rpc_endpoint",
        )
        endpoints = ",".join(endpoints_list)
    load_params = LoadParams(
        endpoint=endpoints,
        obj_size=BACKGROUND_OBJ_SIZE,
        registry_file=registry_file,
        containers_count=1,
        obj_count=0,
        out_file=prepare_file,
        readers=0,
        writers=BACKGROUND_WRITERS_COUNT,
        deleters=0,
        load_time=BACKGROUND_LOAD_MAX_TIME,
        load_type="grpc",
    )
    k6_load_instances = prepare_k6_instances(
        load_nodes=LOAD_NODES,
        login=LOAD_NODE_SSH_USER,
        pkey=LOAD_NODE_SSH_PRIVATE_KEY_PATH,
        load_params=load_params,
    )
    with allure.step("Run background load"):
        for k6_load_instance in k6_load_instances:
            k6_load_instance.start()
    yield
    with allure.step("Stop background load"):
        for k6_load_instance in k6_load_instances:
            k6_load_instance.stop()
    with allure.step("Verify background load data"):
        verify_params = LoadParams(
            endpoint=endpoints,
            clients=BACKGROUND_READERS_COUNT,
            registry_file=registry_file,
            load_time=BACKGROUND_LOAD_MAX_TIME,
            load_type="verify",
        )
        k6_verify_instances = prepare_k6_instances(
            load_nodes=LOAD_NODES,
            login=LOAD_NODE_SSH_USER,
            pkey=LOAD_NODE_SSH_PRIVATE_KEY_PATH,
            load_params=verify_params,
            prepare=False,
        )
        with allure.step("Run verify background load data"):
            for k6_verify_instance in k6_verify_instances:
                k6_verify_instance.start()
                k6_verify_instance.wait_until_finished(BACKGROUND_LOAD_MAX_TIME)


@pytest.fixture(scope="session")
@allure.title("Prepare wallet and deposit")
def default_wallet(client_shell: Shell, temp_directory: str, cluster: Cluster):
    wallet_path = os.path.join(os.getcwd(), ASSETS_DIR, f"{str(uuid.uuid4())}.json")
    init_wallet(wallet_path, WALLET_PASS)
    allure.attach.file(wallet_path, os.path.basename(wallet_path), allure.attachment_type.JSON)

    if not FREE_STORAGE:
        main_chain = cluster.main_chain_nodes[0]
        deposit = 30
        transfer_gas(
            shell=client_shell,
            amount=deposit + 1,
            main_chain=main_chain,
            wallet_to_path=wallet_path,
            wallet_to_password=WALLET_PASS,
        )
        deposit_gas(
            shell=client_shell,
            main_chain=main_chain,
            amount=deposit,
            wallet_from_path=wallet_path,
            wallet_from_password=WALLET_PASS,
        )

    return wallet_path


@allure.title("Check logs for OOM and PANIC entries in {logs_dir}")
def check_logs(logs_dir: str):
    problem_pattern = r"\Wpanic\W|\Woom\W"

    log_file_paths = []
    for directory_path, _, file_names in os.walk(logs_dir):
        log_file_paths += [
            os.path.join(directory_path, file_name)
            for file_name in file_names
            if re.match(r"\.(txt|log)", os.path.splitext(file_name)[-1], flags=re.IGNORECASE)
        ]

    logs_with_problem = []
    for file_path in log_file_paths:
        with allure.step(f"Check log file {file_path}"):
            with open(file_path, "r") as log_file:
                if re.search(problem_pattern, log_file.read(), flags=re.IGNORECASE):
                    logs_with_problem.append(file_path)
    if logs_with_problem:
        raise pytest.fail(f"System logs {', '.join(logs_with_problem)} contain critical errors")


def dump_logs(hosting: Hosting, logs_dir: str, since: datetime, until: datetime) -> None:
    # Dump logs to temp directory (because they might be too large to keep in RAM)
    os.makedirs(logs_dir)

    for host in hosting.hosts:
        with allure.step(f"Dump logs from host {host.config.address}"):
            try:
                host.dump_logs(logs_dir, since=since, until=until)
            except Exception as ex:
                logger.warning(f"Exception during logs collection: {ex}")


def attach_logs(logs_dir: str) -> None:
    # Zip all files and attach to Allure because it is more convenient to download a single
    # zip with all logs rather than mess with individual logs files per service or node
    logs_zip_file_path = shutil.make_archive(logs_dir, "zip", logs_dir)
    allure.attach.file(logs_zip_file_path, name="logs.zip", extension="zip")
