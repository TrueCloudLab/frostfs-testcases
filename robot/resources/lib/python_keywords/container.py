#!/usr/bin/python3.9

"""
    This module contains keywords that utilize `neofs-cli container` commands.
"""

import json
import logging
from time import sleep
from typing import Optional, Union

import allure
import json_transformers
from common import NEOFS_CLI_EXEC, WALLET_CONFIG
from neofs_testlib.cli import NeofsCli
from neofs_testlib.shell import Shell

logger = logging.getLogger("NeoLogger")

DEFAULT_PLACEMENT_RULE = "REP 2 IN X CBF 1 SELECT 4 FROM * AS X"
SINGLE_PLACEMENT_RULE = "REP 1 IN X CBF 1 SELECT 4 FROM * AS X"
REP_2_FOR_3_NODES_PLACEMENT_RULE = "REP 2 IN X CBF 1 SELECT 3 FROM * AS X"


@allure.step("Create Container")
def create_container(
    wallet: str,
    shell: Shell,
    endpoint: str,
    rule: str = DEFAULT_PLACEMENT_RULE,
    basic_acl: str = "",
    attributes: Optional[dict] = None,
    session_token: str = "",
    session_wallet: str = "",
    name: str = None,
    options: dict = None,
    await_mode: bool = True,
    wait_for_creation: bool = True,
) -> str:
    """
    A wrapper for `neofs-cli container create` call.

    Args:
        wallet (str): a wallet on whose behalf a container is created
        rule (optional, str): placement rule for container
        basic_acl (optional, str): an ACL for container, will be
                            appended to `--basic-acl` key
        attributes (optional, dict): container attributes , will be
                            appended to `--attributes` key
        session_token (optional, str): a path to session token file
        session_wallet(optional, str): a path to the wallet which signed
                            the session token; this parameter makes sense
                            when paired with `session_token`
        shell: executor for cli command
        endpoint: NeoFS endpoint to send request to, appends to `--rpc-endpoint` key
        options (optional, dict): any other options to pass to the call
        name (optional, str): container name attribute
        await_mode (bool): block execution until container is persisted
        wait_for_creation (): Wait for container shows in container list

    Returns:
        (str): CID of the created container
    """

    cli = NeofsCli(shell, NEOFS_CLI_EXEC, WALLET_CONFIG)
    result = cli.container.create(
        rpc_endpoint=endpoint,
        wallet=session_wallet if session_wallet else wallet,
        policy=rule,
        basic_acl=basic_acl,
        attributes=attributes,
        name=name,
        session=session_token,
        await_mode=await_mode,
        **options or {},
    )

    cid = _parse_cid(result.stdout)

    logger.info("Container created; waiting until it is persisted in the sidechain")

    if wait_for_creation:
        wait_for_container_creation(wallet, cid, shell, endpoint)

    return cid


def wait_for_container_creation(
    wallet: str, cid: str, shell: Shell, endpoint: str, attempts: int = 15, sleep_interval: int = 1
):
    for _ in range(attempts):
        containers = list_containers(wallet, shell, endpoint)
        if cid in containers:
            return
        logger.info(f"There is no {cid} in {containers} yet; sleep {sleep_interval} and continue")
        sleep(sleep_interval)
    raise RuntimeError(
        f"After {attempts * sleep_interval} seconds container {cid} hasn't been persisted; exiting"
    )


def wait_for_container_deletion(
    wallet: str, cid: str, shell: Shell, endpoint: str, attempts: int = 30, sleep_interval: int = 1
):
    for _ in range(attempts):
        try:
            get_container(wallet, cid, shell=shell, endpoint=endpoint)
            sleep(sleep_interval)
            continue
        except Exception as err:
            if "container not found" not in str(err):
                raise AssertionError(f'Expected "container not found" in error, got\n{err}')
            return
    raise AssertionError(f"Expected container deleted during {attempts * sleep_interval} sec.")


@allure.step("List Containers")
def list_containers(wallet: str, shell: Shell, endpoint: str) -> list[str]:
    """
    A wrapper for `neofs-cli container list` call. It returns all the
    available containers for the given wallet.
    Args:
        wallet (str): a wallet on whose behalf we list the containers
        shell: executor for cli command
        endpoint: NeoFS endpoint to send request to, appends to `--rpc-endpoint` key
    Returns:
        (list): list of containers
    """
    cli = NeofsCli(shell, NEOFS_CLI_EXEC, WALLET_CONFIG)
    result = cli.container.list(rpc_endpoint=endpoint, wallet=wallet)
    logger.info(f"Containers: \n{result}")
    return result.stdout.split()


@allure.step("Get Container")
def get_container(
    wallet: str,
    cid: str,
    shell: Shell,
    endpoint: str,
    json_mode: bool = True,
) -> Union[dict, str]:
    """
    A wrapper for `neofs-cli container get` call. It extracts container's
    attributes and rearranges them into a more compact view.
    Args:
        wallet (str): path to a wallet on whose behalf we get the container
        cid (str): ID of the container to get
        shell: executor for cli command
        endpoint: NeoFS endpoint to send request to, appends to `--rpc-endpoint` key
        json_mode (bool): return container in JSON format
    Returns:
        (dict, str): dict of container attributes
    """

    cli = NeofsCli(shell, NEOFS_CLI_EXEC, WALLET_CONFIG)
    result = cli.container.get(rpc_endpoint=endpoint, wallet=wallet, cid=cid, json_mode=json_mode)

    if not json_mode:
        return result.stdout

    container_info = json.loads(result.stdout)
    attributes = dict()
    for attr in container_info["attributes"]:
        attributes[attr["key"]] = attr["value"]
    container_info["attributes"] = attributes
    container_info["ownerID"] = json_transformers.json_reencode(container_info["ownerID"]["value"])
    return container_info


@allure.step("Delete Container")
# TODO: make the error message about a non-found container more user-friendly
# https://github.com/nspcc-dev/neofs-contract/issues/121
def delete_container(
    wallet: str,
    cid: str,
    shell: Shell,
    endpoint: str,
    force: bool = False,
    session_token: Optional[str] = None,
    await_mode: bool = False,
) -> None:
    """
    A wrapper for `neofs-cli container delete` call.
    Args:
        wallet (str): path to a wallet on whose behalf we delete the container
        cid (str): ID of the container to delete
        shell: executor for cli command
        endpoint: NeoFS endpoint to send request to, appends to `--rpc-endpoint` key
        force (bool): do not check whether container contains locks and remove immediately
        session_token: a path to session token file
    This function doesn't return anything.
    """

    cli = NeofsCli(shell, NEOFS_CLI_EXEC, WALLET_CONFIG)
    cli.container.delete(
        wallet=wallet,
        cid=cid,
        rpc_endpoint=endpoint,
        force=force,
        session=session_token,
        await_mode=await_mode,
    )


def _parse_cid(output: str) -> str:
    """
    Parses container ID from a given CLI output. The input string we expect:
            container ID: 2tz86kVTDpJxWHrhw3h6PbKMwkLtBEwoqhHQCKTre1FN
            awaiting...
            container has been persisted on sidechain
    We want to take 'container ID' value from the string.

    Args:
        output (str): CLI output to parse

    Returns:
        (str): extracted CID
    """
    try:
        # taking first line from command's output
        first_line = output.split("\n")[0]
    except Exception:
        first_line = ""
        logger.error(f"Got empty output: {output}")
    splitted = first_line.split(": ")
    if len(splitted) != 2:
        raise ValueError(f"no CID was parsed from command output: \t{first_line}")
    return splitted[1]


@allure.step("Search container by name")
def search_container_by_name(wallet: str, name: str, shell: Shell, endpoint: str):
    list_cids = list_containers(wallet, shell, endpoint)
    for cid in list_cids:
        cont_info = get_container(wallet, cid, shell, endpoint, True)
        if cont_info.get("attributes").get("Name", None) == name:
            return cid
    return None
