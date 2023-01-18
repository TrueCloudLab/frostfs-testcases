import logging
import random

import allure
import pytest
from cluster import HTTPGate, MorphChain, StorageNode
from epoch import ensure_fresh_epoch, wait_for_epochs_align
from file_helper import generate_file
from neofs_testlib.hosting import Host
from neofs_testlib.shell import Shell
from python_keywords.container import create_container
from python_keywords.http_gate import (
    get_object_and_verify_hashes,
    get_via_http_curl,
    upload_via_http_gate_curl,
)
from python_keywords.neofs_verbs import delete_object, put_object_to_random_node, search_object
from python_keywords.node_management import check_node_in_map, storage_node_healthcheck
from tenacity import retry, stop_after_attempt, wait_fixed
from test_control import wait_for_success
from wallet import WalletFactory, WalletFile
from wellknown_acl import PUBLIC_ACL

from steps.cluster_test_base import ClusterTestBase

logger = logging.getLogger("NeoLogger")

NEOFS_IR = "neofs-ir"
NEOFS_HTTP = "neofs-http"
NEOFS_NODE = "neofs-storage"
NEO_GO = "neo-go"


@pytest.mark.failover
@pytest.mark.failover_network
class TestFailoverServiceKill(ClusterTestBase):
    PLACEMENT_RULE = "REP 1 IN X CBF 1 SELECT 1 FROM * AS X"

    @pytest.fixture(scope="class")
    def user_wallet(self, wallet_factory: WalletFactory) -> WalletFile:
        return wallet_factory.create_wallet()

    @pytest.fixture(scope="class")
    @allure.title("Create container")
    def user_container(self, user_wallet: WalletFile):
        return create_container(
            wallet=user_wallet.path,
            shell=self.shell,
            endpoint=self.cluster.default_rpc_endpoint,
            rule=self.PLACEMENT_RULE,
            basic_acl=PUBLIC_ACL,
        )

    @allure.title("Check and return  status of given service")
    def service_status(self, service: str, shell: Shell) -> str:
        return shell.exec(f"sudo systemctl is-active {service}").stdout.rstrip()

    @allure.step("Run health check to node")
    def health_check(self, node: StorageNode):
        health_check = storage_node_healthcheck(node)
        assert health_check.health_status == "READY" and health_check.network_status == "ONLINE"

    @allure.step("Wait for expected status of passed service")
    @wait_for_success(60, 5)
    def wait_for_expected_status(self, service: str, status: str, shell: Shell):
        real_status = self.service_status(service=service, shell=shell)
        assert (
            status == real_status
        ), f"Service {service}: expected status= {status}, real status {real_status}"

    @allure.step("Run neo-go dump-keys")
    def neo_go_dump_keys(self, shell: Shell, node: StorageNode) -> dict:
        host = node.host
        service_config = host.get_service_config(node.name)
        wallet_path = service_config.attributes["wallet_path"]
        output = shell.exec(f"neo-go wallet dump-keys -w {wallet_path}").stdout
        try:
            # taking first line from command's output contain wallet address
            first_line = output.split("\n")[0]
        except Exception:
            logger.error(f"Got empty output (neo-go dump keys): {output}")
        address_id = first_line.split()[0]
        # taking second line from command's output contain wallet key
        wallet_key = output.split("\n")[1]
        return {address_id: wallet_key}

    @allure.step("Run neo-go query height")
    def neo_go_query_height(self, shell: Shell, node: StorageNode) -> dict:
        morph_chain = self.morph_chain(node)
        output = shell.exec(f"neo-go query height -r {morph_chain.get_endpoint()}").stdout
        try:
            # taking first line from command's output contain the latest block in blockchain
            first_line = output.split("\n")[0]
        except Exception:
            logger.error(f"Got empty output (neo-go query height): {output}")
        latest_block = first_line.split(":")
        # taking second line from command's output contain wallet key
        second_line = output.split("\n")[1]
        validated_state = second_line.split(":")
        return {
            latest_block[0].replace(":", ""): int(latest_block[1]),
            validated_state[0].replace(":", ""): int(validated_state[1]),
        }

    @allure.step("Kill process")
    def kill_by_pid(self, pid: int, shell: Shell):
        shell.exec(f"sudo kill -9 {pid}")

    @allure.step("Kill by process name")
    def kill_by_service_name(self, service: str, shell: Shell):
        self.kill_by_pid(self.service_pid(service, shell), shell)

    @allure.step("Return pid by service name")
    # retry mechanism cause when the task has been started recently '0' PID could be returned
    @retry(wait=wait_fixed(10), stop=stop_after_attempt(5), reraise=True)
    def service_pid(self, service: str, shell: Shell) -> int:
        output = shell.exec(f"systemctl show --property MainPID {service}").stdout.rstrip()
        splitted = output.split("=")
        PID = int(splitted[1])
        assert PID > 0, f"Service {service} has invalid PID={PID}"
        return PID

    @allure.step("HTTPGate according to the passed node")
    def http_gate(self, node: StorageNode) -> HTTPGate:
        index = self.cluster.storage_nodes.index(node)
        return self.cluster.http_gates[index]

    @allure.step("MorphChain according to the passed node")
    def morph_chain(self, node: StorageNode) -> MorphChain:
        index = self.cluster.storage_nodes.index(node)
        return self.cluster.morph_chain_nodes[index]

    @allure.step("WalletFile according to the passed node")
    def storage_wallet(self, node: StorageNode) -> WalletFile:
        return WalletFile.from_node(node)

    def random_node(self, service: str):
        with allure.step(f"Find random node to process"):
            rand_node_num = random.randint(0, len(self.cluster.storage_nodes) - 1)
            node = self.cluster.storage_nodes[rand_node_num]
            shell = node.host.get_shell()
        with allure.step(f"Get status of {service} from the node {node.get_rpc_endpoint()}"):
            self.wait_for_expected_status(service=service, status="active", shell=shell)
        return node

    @allure.title(
        f"kill {NEO_GO}, wait for restart, then check is service healthy and can continue to process"
    )
    def test_neofs_go(self):
        node = self.random_node(service=NEO_GO)
        shell = node.host.get_shell()
        initial_pid = self.service_pid(NEO_GO, shell)
        dump_keys = self.neo_go_dump_keys(node=node, shell=shell)
        with allure.step(
            f"Node: {node.get_rpc_endpoint()}-> Kill {NEO_GO} service, PID {initial_pid}, then wait till the task will be restarted"
        ):
            self.kill_by_service_name(NEO_GO, shell)
            self.wait_for_expected_status(service=NEO_GO, status="active", shell=shell)
        with allure.step(f"Verify that pid has been changed"):
            new_pid = self.service_pid(NEO_GO, shell)
            assert (
                initial_pid != new_pid
            ), f"Pid hasn't been changed - initial {initial_pid}, new {new_pid}"
        with allure.step(f"Verify that {NEO_GO} dump-keys and query height are working well"):
            dump_keys_after_restart = self.neo_go_dump_keys(node=node, shell=shell)
            assert (
                dump_keys == dump_keys_after_restart
            ), f"Dump keys should be equal, initial:{dump_keys}, after restart: {dump_keys_after_restart}"
            query_height_result = self.neo_go_query_height(shell=shell, node=node)
            logger.info(f"QueryRst= {query_height_result}")

    @allure.title(
        f"kill {NEOFS_IR}, wait for restart, then check is service healthy and can continue to process"
    )
    def test_neofs_ir(self):
        node = self.random_node(service=NEOFS_IR)
        shell = node.host.get_shell()
        initial_pid = self.service_pid(NEOFS_IR, shell)
        with allure.step(
            f"Node: {node.get_rpc_endpoint()}-> Kill {NEOFS_IR} service, PID {initial_pid}, then wait till the task will be restarted"
        ):
            self.kill_by_service_name(NEOFS_IR, shell)
            self.wait_for_expected_status(service=NEOFS_IR, status="active", shell=shell)
        with allure.step(f"Verify that pid has been changed"):
            new_pid = self.service_pid(NEOFS_IR, shell)
            assert (
                initial_pid != new_pid
            ), f"Pid hasn't been changed - initial {initial_pid}, new {new_pid}"
        with allure.step(
            f"Node: {node.get_rpc_endpoint()}-> Force-new-epoch - check that {NEOFS_IR} is alive"
        ):
            ensure_fresh_epoch(self.shell, self.cluster)
            wait_for_epochs_align(self.shell, self.cluster)
            self.health_check(node)

    @pytest.mark.parametrize(
        "object_size",
        [pytest.lazy_fixture("simple_object_size"), pytest.lazy_fixture("complex_object_size")],
        ids=["simple object", "complex object"],
    )
    @allure.title(
        f"kill {NEOFS_HTTP}, wait for restart, then check is service healthy and can continue to process"
    )
    def test_neofs_http(self, user_container: str, object_size: int, user_wallet: WalletFile):
        node = self.random_node(service=NEOFS_HTTP)
        http = self.http_gate(node)
        shell = node.host.get_shell()
        initial_pid = self.service_pid(NEOFS_HTTP, shell)
        file_path_grpc = generate_file(object_size)
        with allure.step("Put objects using gRPC"):
            oid_grpc = put_object_to_random_node(
                wallet=user_wallet.path,
                path=file_path_grpc,
                cid=user_container,
                shell=self.shell,
                cluster=self.cluster,
            )
        with allure.step(
            f"Node: {node.get_rpc_endpoint()}-> Kill {NEOFS_HTTP} service, PID {initial_pid}, then wait till the task will be restarted"
        ):
            self.kill_by_service_name(NEOFS_HTTP, shell)
            self.wait_for_expected_status(service=NEOFS_HTTP, status="active", shell=shell)
        with allure.step(f"Verify that pid has been changed"):
            new_pid = self.service_pid(NEOFS_HTTP, shell)
            assert (
                initial_pid != new_pid
            ), f"Pid hasn't been changed - initial {initial_pid}, new {new_pid}"
        with allure.step(f"Get object_grpc and verify hashes: endpoint {node.get_rpc_endpoint()}"):
            get_object_and_verify_hashes(
                oid=oid_grpc,
                file_name=file_path_grpc,
                wallet=user_wallet.path,
                cid=user_container,
                shell=self.shell,
                nodes=self.cluster.storage_nodes,
                endpoint=http.get_endpoint(),
                object_getter=get_via_http_curl,
            )
        with allure.step(f"Put objects using curl utility - endpoint {node.get_rpc_endpoint()}"):
            file_path_http = generate_file(object_size)
            oid_http = upload_via_http_gate_curl(
                cid=user_container, filepath=file_path_http, endpoint=http.get_endpoint()
            )
        with allure.step(f"Get object_http and verify hashes: endpoint {http.get_endpoint()}"):
            get_object_and_verify_hashes(
                oid=oid_http,
                file_name=file_path_http,
                wallet=user_wallet.path,
                cid=user_container,
                shell=self.shell,
                nodes=self.cluster.storage_nodes,
                endpoint=http.get_endpoint(),
                object_getter=get_via_http_curl,
            )

    @pytest.mark.parametrize(
        "object_size",
        [pytest.lazy_fixture("simple_object_size"), pytest.lazy_fixture("complex_object_size")],
        ids=["simple object", "complex object"],
    )
    @allure.title(
        f"kill {NEOFS_NODE}, wait for restart, then check is service healthy and can continue to process"
    )
    def test_neofs_node(self, user_container: str, object_size: int, user_wallet: WalletFile):
        node = self.random_node(service=NEOFS_NODE)
        http = self.http_gate(node)
        shell = node.host.get_shell()
        initial_pid = self.service_pid(NEOFS_NODE, shell)
        file_path1 = generate_file(object_size)
        with allure.step("Put objects#1 using gRPC"):
            oid1 = put_object_to_random_node(
                wallet=user_wallet.path,
                path=file_path1,
                cid=user_container,
                shell=self.shell,
                cluster=self.cluster,
            )
        with allure.step(
            f"Node: {node.get_rpc_endpoint()}-> Kill {NEOFS_NODE} service, PID {initial_pid}, then wait till the task will be restarted"
        ):
            self.kill_by_service_name(NEOFS_NODE, shell)
            self.wait_for_expected_status(service=NEOFS_NODE, status="active", shell=shell)
        with allure.step(f"Verify that pid has been changed"):
            new_pid = self.service_pid(NEOFS_NODE, shell)
            assert (
                initial_pid != new_pid
            ), f"Pid hasn't been changed - initial {initial_pid}, new {new_pid}"

        with allure.step(f"Get object#1 and verify hashes: endpoint {http.get_endpoint()}"):
            get_object_and_verify_hashes(
                oid=oid1,
                file_name=file_path1,
                wallet=user_wallet.path,
                cid=user_container,
                shell=self.shell,
                nodes=self.cluster.storage_nodes,
                endpoint=http.get_endpoint(),
            )
        file_path2 = generate_file(object_size)
        with allure.step("Put objects#2 using gRPC"):
            oid2 = put_object_to_random_node(
                wallet=user_wallet.path,
                path=file_path2,
                cid=user_container,
                shell=self.shell,
                cluster=self.cluster,
            )
        with allure.step("Search object2"):
            search_result = search_object(
                user_wallet.path, user_container, shell=self.shell, endpoint=node.get_rpc_endpoint()
            )
            if oid2 not in search_result:
                raise AssertionError(f"Object_id {oid2} not found in {search_result}")

        with allure.step("Get object2"):
            get_object_and_verify_hashes(
                oid=oid2,
                file_name=file_path2,
                wallet=user_wallet.path,
                cid=user_container,
                shell=self.shell,
                nodes=self.cluster.storage_nodes,
                endpoint=http.get_endpoint(),
                object_getter=get_via_http_curl,
            )
        with allure.step("Delete objects"):
            for oid_to_delete in oid1, oid2:
                delete_object(
                    user_wallet.path,
                    user_container,
                    oid_to_delete,
                    self.shell,
                    node.get_rpc_endpoint(),
                )
