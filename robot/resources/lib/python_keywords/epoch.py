import logging
from time import sleep
from typing import Optional

import allure
from cluster import Cluster, StorageNode
from common import (
    MAINNET_BLOCK_TIME,
    NEOFS_ADM_CONFIG_PATH,
    NEOFS_ADM_EXEC,
    NEOFS_CLI_EXEC,
    NEOGO_EXECUTABLE,
)
from neofs_testlib.cli import NeofsAdm, NeofsCli, NeoGo
from neofs_testlib.shell import Shell
from neofs_testlib.utils.wallet import get_last_address_from_wallet
from payment_neogo import get_contract_hash
from test_control import wait_for_success
from utility import parse_time

logger = logging.getLogger("NeoLogger")


@allure.step("Ensure fresh epoch")
def ensure_fresh_epoch(
    shell: Shell, cluster: Cluster, alive_node: Optional[StorageNode] = None
) -> int:
    # ensure new fresh epoch to avoid epoch switch during test session
    alive_node = alive_node if alive_node else cluster.storage_nodes[0]
    current_epoch = get_epoch(shell, cluster, alive_node)
    tick_epoch(shell, cluster, alive_node)
    epoch = get_epoch(shell, cluster, alive_node)
    assert epoch > current_epoch, "Epoch wasn't ticked"
    return epoch


@allure.step("Wait for epochs align in whole cluster")
@wait_for_success(60, 5)
def wait_for_epochs_align(shell: Shell, cluster: Cluster) -> bool:
    epochs = []
    for node in cluster.storage_nodes:
        epochs.append(get_epoch(shell, cluster, node))
    unique_epochs = list(set(epochs))
    assert (
        len(unique_epochs) == 1
    ), f"unaligned epochs found,  {epochs}, count of unique epochs {len(unique_epochs)}"


@allure.step("Get Epoch")
def get_epoch(shell: Shell, cluster: Cluster, alive_node: Optional[StorageNode] = None):
    alive_node = alive_node if alive_node else cluster.storage_nodes[0]
    endpoint = alive_node.get_rpc_endpoint()
    wallet_path = alive_node.get_wallet_path()
    wallet_config = alive_node.get_wallet_config_path()

    cli = NeofsCli(shell=shell, neofs_cli_exec_path=NEOFS_CLI_EXEC, config_file=wallet_config)

    epoch = cli.netmap.epoch(endpoint, wallet_path)
    return int(epoch.stdout)


@allure.step("Tick Epoch")
def tick_epoch(shell: Shell, cluster: Cluster, alive_node: Optional[StorageNode] = None):
    """
    Tick epoch using neofs-adm or NeoGo if neofs-adm is not available (DevEnv)
    Args:
        shell: local shell to make queries about current epoch. Remote shell will be used to tick new one
        cluster: cluster instance under test
        alive_node: node to send requests to (first node in cluster by default)
    """

    alive_node = alive_node if alive_node else cluster.storage_nodes[0]
    remote_shell = alive_node.host.get_shell()

    if NEOFS_ADM_EXEC and NEOFS_ADM_CONFIG_PATH:
        # If neofs-adm is available, then we tick epoch with it (to be consistent with UAT tests)
        neofsadm = NeofsAdm(
            shell=remote_shell,
            neofs_adm_exec_path=NEOFS_ADM_EXEC,
            config_file=NEOFS_ADM_CONFIG_PATH,
        )
        neofsadm.morph.force_new_epoch()
        return

    # Otherwise we tick epoch using transaction
    cur_epoch = get_epoch(shell, cluster)

    # Use first node by default
    ir_node = cluster.ir_nodes[0]
    # In case if no local_wallet_path is provided, we use wallet_path
    ir_wallet_path = ir_node.get_wallet_path()
    ir_wallet_pass = ir_node.get_wallet_password()
    ir_address = get_last_address_from_wallet(ir_wallet_path, ir_wallet_pass)

    morph_chain = cluster.morph_chain_nodes[0]
    morph_endpoint = morph_chain.get_endpoint()

    neogo = NeoGo(shell, neo_go_exec_path=NEOGO_EXECUTABLE)
    neogo.contract.invokefunction(
        wallet=ir_wallet_path,
        wallet_password=ir_wallet_pass,
        scripthash=get_contract_hash(morph_chain, "netmap.neofs", shell=shell),
        method="newEpoch",
        arguments=f"int:{cur_epoch + 1}",
        multisig_hash=f"{ir_address}:Global",
        address=ir_address,
        rpc_endpoint=morph_endpoint,
        force=True,
        gas=1,
    )
    sleep(parse_time(MAINNET_BLOCK_TIME))
