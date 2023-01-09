import logging
import random
import re
import time
from dataclasses import dataclass
from typing import Optional

import allure
from cluster import Cluster, StorageNode
from common import FROSTFS_CLI_EXEC, MORPH_BLOCK_TIME
from epoch import tick_epoch
from frostfs_testlib.cli import FrostfsCli
from frostfs_testlib.shell import Shell
from utility import parse_time

logger = logging.getLogger("NeoLogger")


@dataclass
class HealthStatus:
    network_status: Optional[str] = None
    health_status: Optional[str] = None

    @staticmethod
    def from_stdout(output: str) -> "HealthStatus":
        network, health = None, None
        for line in output.split("\n"):
            if "Network status" in line:
                network = line.split(":")[-1].strip()
            if "Health status" in line:
                health = line.split(":")[-1].strip()
        return HealthStatus(network, health)


@allure.step("Stop random storage nodes")
def stop_random_storage_nodes(number: int, nodes: list[StorageNode]) -> list[StorageNode]:
    """
    Shuts down the given number of randomly selected storage nodes.
    Args:
       number: the number of storage nodes to stop
       nodes: the list of storage nodes to stop
    Returns:
        the list of nodes that were stopped
    """
    nodes_to_stop = random.sample(nodes, number)
    for node in nodes_to_stop:
        node.stop_service()
    return nodes_to_stop


@allure.step("Start storage node")
def start_storage_nodes(nodes: list[StorageNode]) -> None:
    """
    The function starts specified storage nodes.
    Args:
       nodes: the list of nodes to start
    """
    for node in nodes:
        node.start_service()


@allure.step("Get Locode from random storage node")
def get_locode_from_random_node(cluster: Cluster) -> str:
    node = random.choice(cluster.storage_nodes)
    locode = node.get_un_locode()
    logger.info(f"Chosen '{locode}' locode from node {node}")
    return locode


@allure.step("Healthcheck for storage node {node}")
def storage_node_healthcheck(node: StorageNode) -> HealthStatus:
    """
    The function returns storage node's health status.
    Args:
        node: storage node for which health status should be retrieved.
    Returns:
        health status as HealthStatus object.
    """
    command = "control healthcheck"
    output = _run_control_command_with_retries(node, command)
    return HealthStatus.from_stdout(output)


@allure.step("Set status for {node}")
def storage_node_set_status(node: StorageNode, status: str, retries: int = 0) -> None:
    """
    The function sets particular status for given node.
    Args:
        node: node for which status should be set.
        status: online or offline.
        retries (optional, int): number of retry attempts if it didn't work from the first time
    """
    command = f"control set-status --status {status}"
    _run_control_command_with_retries(node, command, retries)


@allure.step("Get netmap snapshot")
def get_netmap_snapshot(node: StorageNode, shell: Shell) -> str:
    """
    The function returns string representation of netmap snapshot.
    Args:
        node: node from which netmap snapshot should be requested.
    Returns:
        string representation of netmap
    """

    storage_wallet_config = node.get_wallet_config_path()
    storage_wallet_path = node.get_wallet_path()

    cli = FrostfsCli(shell, FROSTFS_CLI_EXEC, config_file=storage_wallet_config)
    return cli.netmap.snapshot(
        rpc_endpoint=node.get_rpc_endpoint(),
        wallet=storage_wallet_path,
    ).stdout


@allure.step("Get shard list for {node}")
def node_shard_list(node: StorageNode) -> list[str]:
    """
    The function returns list of shards for specified storage node.
    Args:
        node: node for which shards should be returned.
    Returns:
        list of shards.
    """
    command = "control shards list"
    output = _run_control_command_with_retries(node, command)
    return re.findall(r"Shard (.*):", output)


@allure.step("Shard set for {node}")
def node_shard_set_mode(node: StorageNode, shard: str, mode: str) -> str:
    """
    The function sets mode for specified shard.
    Args:
        node: node on which shard mode should be set.
    """
    command = f"control shards set-mode --id {shard} --mode {mode}"
    return _run_control_command_with_retries(node, command)


@allure.step("Drop object from {node}")
def drop_object(node: StorageNode, cid: str, oid: str) -> str:
    """
    The function drops object from specified node.
    Args:
        node_id str: node from which object should be dropped.
    """
    command = f"control drop-objects  -o {cid}/{oid}"
    return _run_control_command_with_retries(node, command)


@allure.step("Delete data from host for node {node}")
def delete_node_data(node: StorageNode) -> None:
    node.stop_service()
    node.host.delete_storage_node_data(node.name)
    time.sleep(parse_time(MORPH_BLOCK_TIME))


@allure.step("Exclude node {node_to_exclude} from network map")
def exclude_node_from_network_map(
    node_to_exclude: StorageNode,
    alive_node: StorageNode,
    shell: Shell,
    cluster: Cluster,
) -> None:
    node_netmap_key = node_to_exclude.get_wallet_public_key()

    storage_node_set_status(node_to_exclude, status="offline")

    time.sleep(parse_time(MORPH_BLOCK_TIME))
    tick_epoch(shell, cluster)

    snapshot = get_netmap_snapshot(node=alive_node, shell=shell)
    assert (
        node_netmap_key not in snapshot
    ), f"Expected node with key {node_netmap_key} to be absent in network map"


@allure.step("Include node {node_to_include} into network map")
def include_node_to_network_map(
    node_to_include: StorageNode,
    alive_node: StorageNode,
    shell: Shell,
    cluster: Cluster,
) -> None:
    storage_node_set_status(node_to_include, status="online")

    # Per suggestion of @fyrchik we need to wait for 2 blocks after we set status and after tick epoch.
    # First sleep can be omitted after https://github.com/nspcc-dev/frostfs-node/issues/1790 complete.

    time.sleep(parse_time(MORPH_BLOCK_TIME) * 2)
    tick_epoch(shell, cluster)
    time.sleep(parse_time(MORPH_BLOCK_TIME) * 2)

    check_node_in_map(node_to_include, shell, alive_node)


@allure.step("Check node {node} in network map")
def check_node_in_map(
    node: StorageNode, shell: Shell, alive_node: Optional[StorageNode] = None
) -> None:
    alive_node = alive_node or node

    node_netmap_key = node.get_wallet_public_key()
    logger.info(f"Node ({node.label}) netmap key: {node_netmap_key}")

    snapshot = get_netmap_snapshot(alive_node, shell)
    assert (
        node_netmap_key in snapshot
    ), f"Expected node with key {node_netmap_key} to be in network map"


def _run_control_command_with_retries(node: StorageNode, command: str, retries: int = 0) -> str:
    for attempt in range(1 + retries):  # original attempt + specified retries
        try:
            return _run_control_command(node, command)
        except AssertionError as err:
            if attempt < retries:
                logger.warning(f"Command {command} failed with error {err} and will be retried")
                continue
            raise AssertionError(f"Command {command} failed with error {err}") from err


def _run_control_command(node: StorageNode, command: str) -> None:
    host = node.host

    service_config = host.get_service_config(node.name)
    wallet_path = service_config.attributes["wallet_path"]
    wallet_password = service_config.attributes["wallet_password"]
    control_endpoint = service_config.attributes["control_endpoint"]

    shell = host.get_shell()
    wallet_config_path = f"/tmp/{node.name}-config.yaml"
    wallet_config = f'password: "{wallet_password}"'
    shell.exec(f"echo '{wallet_config}' > {wallet_config_path}")

    cli_config = host.get_cli_config("frostfs-cli")

    # TODO: implement cli.control
    # cli = frostfsCli(shell, cli_config.exec_path, wallet_config_path)
    result = shell.exec(
        f"{cli_config.exec_path} {command} --endpoint {control_endpoint} "
        f"--wallet {wallet_path} --config {wallet_config_path}"
    )
    return result.stdout
