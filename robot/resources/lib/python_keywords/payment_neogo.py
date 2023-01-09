import base64
import json
import logging
import re
import time
from typing import Optional

import allure
from cluster import MainChain, MorphChain
from common import FROSTFS_CONTRACT, GAS_HASH, MAINNET_BLOCK_TIME, NEOGO_EXECUTABLE
from frostfs_testlib.cli import NeoGo
from frostfs_testlib.shell import Shell
from frostfs_testlib.utils.converters import contract_hash_to_address
from frostfs_testlib.utils.wallet import get_last_address_from_wallet
from neo3.wallet import utils as neo3_utils
from neo3.wallet import wallet as neo3_wallet
from utility import parse_time

logger = logging.getLogger("NeoLogger")

EMPTY_PASSWORD = ""
TX_PERSIST_TIMEOUT = 15  # seconds
ASSET_POWER_MAINCHAIN = 10**8
ASSET_POWER_SIDECHAIN = 10**12


def get_nns_contract_hash(morph_chain: MorphChain) -> str:
    return morph_chain.rpc_client.get_contract_state(1)["hash"]


def get_contract_hash(morph_chain: MorphChain, resolve_name: str, shell: Shell) -> str:
    nns_contract_hash = get_nns_contract_hash(morph_chain)
    neogo = NeoGo(shell=shell, neo_go_exec_path=NEOGO_EXECUTABLE)
    out = neogo.contract.testinvokefunction(
        scripthash=nns_contract_hash,
        method="resolve",
        arguments=f"string:{resolve_name} int:16",
        rpc_endpoint=morph_chain.get_endpoint(),
    )
    stack_data = json.loads(out.stdout.replace("\n", ""))["stack"][0]["value"]
    return bytes.decode(base64.b64decode(stack_data[0]["value"]))


@allure.step("Withdraw Mainnet Gas")
def withdraw_mainnet_gas(shell: Shell, main_chain: MainChain, wlt: str, amount: int):
    address = get_last_address_from_wallet(wlt, EMPTY_PASSWORD)
    scripthash = neo3_utils.address_to_script_hash(address)

    neogo = NeoGo(shell=shell, neo_go_exec_path=NEOGO_EXECUTABLE)
    out = neogo.contract.invokefunction(
        wallet=wlt,
        address=address,
        rpc_endpoint=main_chain.get_endpoint(),
        scripthash=FROSTFS_CONTRACT,
        method="withdraw",
        arguments=f"{scripthash} int:{amount}",
        multisig_hash=f"{scripthash}:Global",
        wallet_password="",
    )

    m = re.match(r"^Sent invocation transaction (\w{64})$", out.stdout)
    if m is None:
        raise Exception("Can not get Tx.")
    tx = m.group(1)
    if not transaction_accepted(tx):
        raise AssertionError(f"TX {tx} hasn't been processed")


def transaction_accepted(main_chain: MainChain, tx_id: str):
    """
    This function returns True in case of accepted TX.
    Args:
        tx_id(str): transaction ID
    Returns:
        (bool)
    """

    try:
        for _ in range(0, TX_PERSIST_TIMEOUT):
            time.sleep(1)
            resp = main_chain.rpc_client.get_transaction_height(tx_id)
            if resp is not None:
                logger.info(f"TX is accepted in block: {resp}")
                return True
    except Exception as out:
        logger.info(f"request failed with error: {out}")
        raise out
    return False


@allure.step("Get FrostFS Balance")
def get_balance(shell: Shell, morph_chain: MorphChain, wallet_path: str, wallet_password: str = ""):
    """
    This function returns FrostFS balance for given wallet.
    """
    with open(wallet_path) as wallet_file:
        wallet = neo3_wallet.Wallet.from_json(json.load(wallet_file), password=wallet_password)
    acc = wallet.accounts[-1]
    payload = [{"type": "Hash160", "value": str(acc.script_hash)}]
    try:
        resp = morph_chain.rpc_client.invoke_function(
            get_contract_hash(morph_chain, "balance.frostfs", shell=shell), "balanceOf", payload
        )
        logger.info(f"Got response \n{resp}")
        value = int(resp["stack"][0]["value"])
        return value / ASSET_POWER_SIDECHAIN
    except Exception as out:
        logger.error(f"failed to get wallet balance: {out}")
        raise out


@allure.title("Transfer Gas")
def transfer_gas(
    shell: Shell,
    amount: int,
    main_chain: MainChain,
    wallet_from_path: Optional[str] = None,
    wallet_from_password: Optional[str] = None,
    address_from: Optional[str] = None,
    address_to: Optional[str] = None,
    wallet_to_path: Optional[str] = None,
    wallet_to_password: Optional[str] = None,
):
    """
    This function transfer GAS in main chain from mainnet wallet to
    the provided wallet. If the wallet contains more than one address,
    the assets will be transferred to the last one.
    Args:
        shell: Shell instance.
        wallet_from_password: Password of the wallet; it is required to decode the wallet
            and extract its addresses.
        wallet_from_path: Path to chain node wallet.
        address_from: The address of the wallet to transfer assets from.
        wallet_to_path: The path to the wallet to transfer assets to.
        wallet_to_password: The password to the wallet to transfer assets to.
        address_to: The address of the wallet to transfer assets to.
        amount: Amount of gas to transfer.
    """
    wallet_from_path = wallet_from_path or main_chain.get_wallet_path()
    wallet_from_password = (
        wallet_from_password
        if wallet_from_password is not None
        else main_chain.get_wallet_password()
    )
    address_from = address_from or get_last_address_from_wallet(
        wallet_from_path, wallet_from_password
    )
    address_to = address_to or get_last_address_from_wallet(wallet_to_path, wallet_to_password)

    neogo = NeoGo(shell, neo_go_exec_path=NEOGO_EXECUTABLE)
    out = neogo.nep17.transfer(
        rpc_endpoint=main_chain.get_endpoint(),
        wallet=wallet_from_path,
        wallet_password=wallet_from_password,
        amount=amount,
        from_address=address_from,
        to_address=address_to,
        token="GAS",
        force=True,
    )
    txid = out.stdout.strip().split("\n")[-1]
    if len(txid) != 64:
        raise Exception("Got no TXID after run the command")
    if not transaction_accepted(main_chain, txid):
        raise AssertionError(f"TX {txid} hasn't been processed")
    time.sleep(parse_time(MAINNET_BLOCK_TIME))


@allure.step("FrostFS Deposit")
def deposit_gas(
    shell: Shell,
    main_chain: MainChain,
    amount: int,
    wallet_from_path: str,
    wallet_from_password: str,
):
    """
    Transferring GAS from given wallet to FrostFS contract address.
    """
    # get FrostFS contract address
    deposit_addr = contract_hash_to_address(FROSTFS_CONTRACT)
    logger.info(f"FrostFS contract address: {deposit_addr}")
    address_from = get_last_address_from_wallet(
        wallet_path=wallet_from_path, wallet_password=wallet_from_password
    )
    transfer_gas(
        shell=shell,
        main_chain=main_chain,
        amount=amount,
        wallet_from_path=wallet_from_path,
        wallet_from_password=wallet_from_password,
        address_to=deposit_addr,
        address_from=address_from,
    )


@allure.step("Get Mainnet Balance")
def get_mainnet_balance(main_chain: MainChain, address: str):
    resp = main_chain.rpc_client.get_nep17_balances(address=address)
    logger.info(f"Got getnep17balances response: {resp}")
    for balance in resp["balance"]:
        if balance["assethash"] == GAS_HASH:
            return float(balance["amount"]) / ASSET_POWER_MAINCHAIN
    return float(0)


@allure.step("Get Sidechain Balance")
def get_sidechain_balance(morph_chain: MorphChain, address: str):
    resp = morph_chain.rpc_client.get_nep17_balances(address=address)
    logger.info(f"Got getnep17balances response: {resp}")
    for balance in resp["balance"]:
        if balance["assethash"] == GAS_HASH:
            return float(balance["amount"]) / ASSET_POWER_SIDECHAIN
    return float(0)
