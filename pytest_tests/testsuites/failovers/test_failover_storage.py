import logging

import allure
import pytest
from cluster import Cluster, StorageNode
from failover_utils import wait_all_storage_nodes_returned, wait_object_replication
from file_helper import generate_file, get_file_hash
from neofs_testlib.hosting import Host
from neofs_testlib.shell import CommandOptions
from python_keywords.container import create_container
from python_keywords.neofs_verbs import get_object, put_object_to_random_node
from wellknown_acl import PUBLIC_ACL

from steps.cluster_test_base import ClusterTestBase

logger = logging.getLogger("NeoLogger")
stopped_nodes: list[StorageNode] = []


@pytest.fixture(scope="function", autouse=True)
@allure.step("Return all stopped hosts")
def after_run_return_all_stopped_hosts(cluster: Cluster):
    yield
    return_stopped_hosts(cluster)


def panic_reboot_host(host: Host) -> None:
    shell = host.get_shell()
    shell.exec('sudo sh -c "echo 1 > /proc/sys/kernel/sysrq"')

    options = CommandOptions(close_stdin=True, timeout=1, check=False)
    shell.exec('sudo sh -c "echo b > /proc/sysrq-trigger"', options)


def return_stopped_hosts(cluster: Cluster) -> None:
    for node in list(stopped_nodes):
        with allure.step(f"Start host {node}"):
            node.host.start_host()
        stopped_nodes.remove(node)

    wait_all_storage_nodes_returned(cluster)


@pytest.mark.failover
class TestFailoverStorage(ClusterTestBase):
    @allure.title("Lose and return storage node's host")
    @pytest.mark.parametrize("hard_reboot", [True, False])
    @pytest.mark.failover_reboot
    def test_lose_storage_node_host(
        self, default_wallet, hard_reboot: bool, require_multiple_hosts, simple_object_size
    ):
        wallet = default_wallet
        placement_rule = "REP 2 IN X CBF 2 SELECT 2 FROM * AS X"
        source_file_path = generate_file(simple_object_size)
        cid = create_container(
            wallet,
            shell=self.shell,
            endpoint=self.cluster.default_rpc_endpoint,
            rule=placement_rule,
            basic_acl=PUBLIC_ACL,
        )
        oid = put_object_to_random_node(
            wallet, source_file_path, cid, shell=self.shell, cluster=self.cluster
        )
        nodes = wait_object_replication(
            cid, oid, 2, shell=self.shell, nodes=self.cluster.storage_nodes
        )

        for node in nodes:
            stopped_nodes.append(node)

            with allure.step(f"Stop host {node}"):
                node.host.stop_host("hard" if hard_reboot else "soft")

            new_nodes = wait_object_replication(
                cid,
                oid,
                2,
                shell=self.shell,
                nodes=list(set(self.cluster.storage_nodes) - {node}),
            )
        assert all(old_node not in new_nodes for old_node in nodes)

        with allure.step("Check object data is not corrupted"):
            got_file_path = get_object(
                wallet, cid, oid, endpoint=new_nodes[0].get_rpc_endpoint(), shell=self.shell
            )
            assert get_file_hash(source_file_path) == get_file_hash(got_file_path)

        with allure.step(f"Return all hosts"):
            return_stopped_hosts(self.cluster)

        with allure.step("Check object data is not corrupted"):
            new_nodes = wait_object_replication(
                cid, oid, 2, shell=self.shell, nodes=self.cluster.storage_nodes
            )
            got_file_path = get_object(
                wallet, cid, oid, shell=self.shell, endpoint=new_nodes[0].get_rpc_endpoint()
            )
            assert get_file_hash(source_file_path) == get_file_hash(got_file_path)

    @allure.title("Panic storage node's host")
    @pytest.mark.parametrize("sequence", [True, False])
    @pytest.mark.failover_panic
    def test_panic_storage_node_host(
        self, default_wallet, require_multiple_hosts, sequence: bool, simple_object_size
    ):
        wallet = default_wallet
        placement_rule = "REP 2 IN X CBF 2 SELECT 2 FROM * AS X"
        source_file_path = generate_file(simple_object_size)
        cid = create_container(
            wallet,
            shell=self.shell,
            endpoint=self.cluster.default_rpc_endpoint,
            rule=placement_rule,
            basic_acl=PUBLIC_ACL,
        )
        oid = put_object_to_random_node(
            wallet, source_file_path, cid, shell=self.shell, cluster=self.cluster
        )

        nodes = wait_object_replication(
            cid, oid, 2, shell=self.shell, nodes=self.cluster.storage_nodes
        )
        allure.attach(
            "\n".join(nodes),
            "Current nodes with object",
            allure.attachment_type.TEXT,
        )

        new_nodes: list[StorageNode] = []
        for node in nodes:
            with allure.step(f"Hard reboot host {node} via magic SysRq option"):
                panic_reboot_host(node.host)
                if sequence:
                    try:
                        new_nodes = wait_object_replication(
                            cid,
                            oid,
                            2,
                            shell=self.shell,
                            nodes=list(set(self.cluster.storage_nodes) - {node}),
                        )
                    except AssertionError:
                        new_nodes = wait_object_replication(
                            cid,
                            oid,
                            2,
                            shell=self.shell,
                            nodes=self.cluster.storage_nodes,
                        )

                    allure.attach(
                        "\n".join(new_nodes),
                        f"Nodes with object after {node} fail",
                        allure.attachment_type.TEXT,
                    )

        if not sequence:
            new_nodes = wait_object_replication(
                cid, oid, 2, shell=self.shell, nodes=self.cluster.storage_nodes
            )
            allure.attach(
                "\n".join(new_nodes),
                "Nodes with object after nodes fail",
                allure.attachment_type.TEXT,
            )

        got_file_path = get_object(
            wallet, cid, oid, shell=self.shell, endpoint=new_nodes[0].get_rpc_endpoint()
        )
        assert get_file_hash(source_file_path) == get_file_hash(got_file_path)
