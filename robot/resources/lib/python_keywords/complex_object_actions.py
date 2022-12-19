#!/usr/bin/python3

"""
    This module contains functions which are used for Large Object assembling:
    getting Last Object and split and getting Link Object. It is not enough to
    simply perform a "raw" HEAD request, as noted in the issue:
    https://github.com/nspcc-dev/neofs-node/issues/1304. Therefore, the reliable
    retrieval of the aforementioned objects must be done this way: send direct
    "raw" HEAD request to the every Storage Node and return the desired OID on
    first non-null response.
"""

import logging
from typing import Optional, Tuple

import allure
import neofs_verbs
from cluster import Cluster, StorageNode
from common import WALLET_CONFIG
from neofs_testlib.shell import Shell
from neofs_verbs import head_object
from storage_object import StorageObjectInfo

logger = logging.getLogger("NeoLogger")


def get_storage_object_chunks(
    storage_object: StorageObjectInfo, shell: Shell, cluster: Cluster
) -> list[str]:
    """
    Get complex object split objects ids (no linker object)

    Args:
    storage_object: storage_object to get it's chunks
    shell: client shell to do cmd requests
    cluster: cluster object under test

    Returns:
    list of object ids of complex object chunks
    """

    with allure.step(f"Get complex object chunks (f{storage_object.oid})"):
        split_object_id = get_link_object(
            storage_object.wallet_file_path,
            storage_object.cid,
            storage_object.oid,
            shell,
            cluster.storage_nodes,
            is_direct=False,
        )
        head = head_object(
            storage_object.wallet_file_path,
            storage_object.cid,
            split_object_id,
            shell,
            cluster.default_rpc_endpoint,
        )

        chunks_object_ids = []
        if "split" in head["header"] and "children" in head["header"]["split"]:
            chunks_object_ids = head["header"]["split"]["children"]

        return chunks_object_ids


def get_complex_object_split_ranges(
    storage_object: StorageObjectInfo, shell: Shell, cluster: Cluster
) -> list[Tuple[int, int]]:

    """
    Get list of split ranges tuples (offset, length) of a complex object
    For example if object size if 100 and max object size in system is 30
    the returned list should be
    [(0, 30), (30, 30), (60, 30), (90, 10)]

    Args:
    storage_object: storage_object to get it's chunks
    shell: client shell to do cmd requests
    cluster: cluster object under test

    Returns:
    list of object ids of complex object chunks
    """

    ranges: list = []
    offset = 0
    chunks_ids = get_storage_object_chunks(storage_object, shell, cluster)
    for chunk_id in chunks_ids:
        head = head_object(
            storage_object.wallet_file_path,
            storage_object.cid,
            chunk_id,
            shell,
            cluster.default_rpc_endpoint,
        )

        length = int(head["header"]["payloadLength"])
        ranges.append((offset, length))

        offset = offset + length

    return ranges


@allure.step("Get Link Object")
def get_link_object(
    wallet: str,
    cid: str,
    oid: str,
    shell: Shell,
    nodes: list[StorageNode],
    bearer: str = "",
    wallet_config: str = WALLET_CONFIG,
    is_direct: bool = True,
):
    """
    Args:
        wallet (str): path to the wallet on whose behalf the Storage Nodes
                        are requested
        cid (str): Container ID which stores the Large Object
        oid (str): Large Object ID
        shell: executor for cli command
        nodes: list of nodes to do search on
        bearer (optional, str): path to Bearer token file
        wallet_config (optional, str): path to the neofs-cli config file
        is_direct: send request directly to the node or not; this flag
                   turns into `--ttl 1` key
    Returns:
        (str): Link Object ID
        When no Link Object ID is found after all Storage Nodes polling,
        the function throws an error.
    """
    for node in nodes:
        endpoint = node.get_rpc_endpoint()
        try:
            resp = neofs_verbs.head_object(
                wallet,
                cid,
                oid,
                shell=shell,
                endpoint=endpoint,
                is_raw=True,
                is_direct=is_direct,
                bearer=bearer,
                wallet_config=wallet_config,
            )
            if resp["link"]:
                return resp["link"]
        except Exception:
            logger.info(f"No Link Object found on {endpoint}; continue")
    logger.error(f"No Link Object for {cid}/{oid} found among all Storage Nodes")
    return None


@allure.step("Get Last Object")
def get_last_object(
    wallet: str, cid: str, oid: str, shell: Shell, nodes: list[StorageNode]
) -> Optional[str]:
    """
    Args:
        wallet (str): path to the wallet on whose behalf the Storage Nodes
                        are requested
        cid (str): Container ID which stores the Large Object
        oid (str): Large Object ID
        shell: executor for cli command
        nodes: list of nodes to do search on
    Returns:
        (str): Last Object ID
        When no Last Object ID is found after all Storage Nodes polling,
        the function throws an error.
    """
    for node in nodes:
        endpoint = node.get_rpc_endpoint()
        try:
            resp = neofs_verbs.head_object(
                wallet, cid, oid, shell=shell, endpoint=endpoint, is_raw=True, is_direct=True
            )
            if resp["lastPart"]:
                return resp["lastPart"]
        except Exception:
            logger.info(f"No Last Object found on {endpoint}; continue")
    logger.error(f"No Last Object for {cid}/{oid} found among all Storage Nodes")
    return None
