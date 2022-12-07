import logging
from random import choices
from time import sleep

import allure
import pytest
from cluster import StorageNode
from failover_utils import wait_all_storage_nodes_returned, wait_object_replication
from file_helper import generate_file, get_file_hash
from iptables_helper import IpTablesHelper
from python_keywords.container import create_container
from python_keywords.neofs_verbs import get_object, put_object_to_random_node
from wellknown_acl import PUBLIC_ACL

from steps.cluster_test_base import ClusterTestBase

logger = logging.getLogger("NeoLogger")
STORAGE_NODE_COMMUNICATION_PORT = "8080"
STORAGE_NODE_COMMUNICATION_PORT_TLS = "8082"
PORTS_TO_BLOCK = [STORAGE_NODE_COMMUNICATION_PORT, STORAGE_NODE_COMMUNICATION_PORT_TLS]
blocked_nodes: list[StorageNode] = []


@pytest.mark.failover
@pytest.mark.failover_network
class TestFailoverNetwork(ClusterTestBase):
    @pytest.fixture(autouse=True)
    @allure.step("Restore network")
    def restore_network(self):
        yield

        not_empty = len(blocked_nodes) != 0
        for node in list(blocked_nodes):
            with allure.step(f"Restore network at host for {node.label}"):
                IpTablesHelper.restore_input_traffic_to_port(node.host.get_shell(), PORTS_TO_BLOCK)
            blocked_nodes.remove(node)
        if not_empty:
            wait_all_storage_nodes_returned(self.cluster)

    @allure.title("Block Storage node traffic")
    def test_block_storage_node_traffic(
        self, default_wallet, require_multiple_hosts, simple_object_size
    ):
        """
        Block storage nodes traffic using iptables and wait for replication for objects.
        """
        wallet = default_wallet
        placement_rule = "REP 2 IN X CBF 2 SELECT 2 FROM * AS X"
        wakeup_node_timeout = 10  # timeout to let nodes detect that traffic has blocked
        nodes_to_block_count = 2

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

        logger.info(f"Nodes are {nodes}")
        nodes_to_block = nodes
        if nodes_to_block_count > len(nodes):
            # TODO: the intent of this logic is not clear, need to revisit
            nodes_to_block = choices(nodes, k=2)

        excluded_nodes = []
        for node in nodes_to_block:
            with allure.step(f"Block incoming traffic at node {node} on port {PORTS_TO_BLOCK}"):
                blocked_nodes.append(node)
                excluded_nodes.append(node)
                IpTablesHelper.drop_input_traffic_to_port(node.host.get_shell(), PORTS_TO_BLOCK)
                sleep(wakeup_node_timeout)

            with allure.step(f"Check object is not stored on node {node}"):
                new_nodes = wait_object_replication(
                    cid,
                    oid,
                    2,
                    shell=self.shell,
                    nodes=list(set(self.cluster.storage_nodes) - set(excluded_nodes)),
                )
                assert node not in new_nodes

            with allure.step(f"Check object data is not corrupted"):
                got_file_path = get_object(
                    wallet, cid, oid, endpoint=new_nodes[0].get_rpc_endpoint(), shell=self.shell
                )
                assert get_file_hash(source_file_path) == get_file_hash(got_file_path)

        for node in nodes_to_block:
            with allure.step(f"Unblock incoming traffic at host {node} on port {PORTS_TO_BLOCK}"):
                IpTablesHelper.restore_input_traffic_to_port(node.host.get_shell(), PORTS_TO_BLOCK)
                blocked_nodes.remove(node)
                sleep(wakeup_node_timeout)

        with allure.step(f"Check object data is not corrupted"):
            new_nodes = wait_object_replication(
                cid, oid, 2, shell=self.shell, nodes=self.cluster.storage_nodes
            )

            got_file_path = get_object(
                wallet, cid, oid, shell=self.shell, endpoint=new_nodes[0].get_rpc_endpoint()
            )
            assert get_file_hash(source_file_path) == get_file_hash(got_file_path)
