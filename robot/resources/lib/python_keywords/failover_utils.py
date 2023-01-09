import logging
from time import sleep

import allure
from cluster import Cluster, StorageNode
from frostfs_testlib.shell import Shell
from python_keywords.node_management import storage_node_healthcheck
from storage_policy import get_nodes_with_object

logger = logging.getLogger("NeoLogger")


@allure.step("Wait for object replication")
def wait_object_replication(
    cid: str,
    oid: str,
    expected_copies: int,
    shell: Shell,
    nodes: list[StorageNode],
) -> list[StorageNode]:
    sleep_interval, attempts = 15, 20
    nodes_with_object = []
    for _ in range(attempts):
        nodes_with_object = get_nodes_with_object(cid, oid, shell=shell, nodes=nodes)
        if len(nodes_with_object) >= expected_copies:
            return nodes_with_object
        sleep(sleep_interval)
    raise AssertionError(
        f"Expected {expected_copies} copies of object, but found {len(nodes_with_object)}. "
        f"Waiting time {sleep_interval * attempts}"
    )


@allure.step("Wait for storage nodes returned to cluster")
def wait_all_storage_nodes_returned(cluster: Cluster) -> None:
    sleep_interval, attempts = 15, 20
    for __attempt in range(attempts):
        if is_all_storage_nodes_returned(cluster):
            return
        sleep(sleep_interval)
    raise AssertionError("Storage node(s) is broken")


def is_all_storage_nodes_returned(cluster: Cluster) -> bool:
    with allure.step("Run health check for all storage nodes"):
        for node in cluster.storage_nodes:
            try:
                health_check = storage_node_healthcheck(node)
            except Exception as err:
                logger.warning(f"Node healthcheck fails with error {err}")
                return False
            if health_check.health_status != "READY" or health_check.network_status != "ONLINE":
                return False
    return True
