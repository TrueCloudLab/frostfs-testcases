#!/usr/bin/python3

"""
    This module contains keywords which are used for asserting
    that storage policies are respected.
"""

import logging
from typing import List

import allure
import complex_object_actions
import frostfs_verbs
from cluster import StorageNode
from frostfs_testlib.shell import Shell
from grpc_responses import OBJECT_NOT_FOUND, error_matches_status

logger = logging.getLogger("NeoLogger")


@allure.step("Get Object Copies")
def get_object_copies(
    complexity: str, wallet: str, cid: str, oid: str, shell: Shell, nodes: list[StorageNode]
) -> int:
    """
    The function performs requests to all nodes of the container and
    finds out if they store a copy of the object. The procedure is
    different for simple and complex object, so the function requires
    a sign of object complexity.
    Args:
        complexity (str): the tag of object size and complexity,
                            [Simple|Complex]
        wallet (str): the path to the wallet on whose behalf the
                            copies are got
        cid (str): ID of the container
        oid (str): ID of the Object
        shell: executor for cli command
    Returns:
        (int): the number of object copies in the container
    """
    return (
        get_simple_object_copies(wallet, cid, oid, shell, nodes)
        if complexity == "Simple"
        else get_complex_object_copies(wallet, cid, oid, shell, nodes)
    )


@allure.step("Get Simple Object Copies")
def get_simple_object_copies(
    wallet: str, cid: str, oid: str, shell: Shell, nodes: list[StorageNode]
) -> int:
    """
    To figure out the number of a simple object copies, only direct
    HEAD requests should be made to the every node of the container.
    We consider non-empty HEAD response as a stored object copy.
    Args:
        wallet (str): the path to the wallet on whose behalf the
                            copies are got
        cid (str): ID of the container
        oid (str): ID of the Object
        shell: executor for cli command
        nodes: nodes to search on
    Returns:
        (int): the number of object copies in the container
    """
    copies = 0
    for node in nodes:
        try:
            response = frostfs_verbs.head_object(
                wallet, cid, oid, shell=shell, endpoint=node.get_rpc_endpoint(), is_direct=True
            )
            if response:
                logger.info(f"Found object {oid} on node {node}")
                copies += 1
        except Exception:
            logger.info(f"No {oid} object copy found on {node}, continue")
            continue
    return copies


@allure.step("Get Complex Object Copies")
def get_complex_object_copies(
    wallet: str, cid: str, oid: str, shell: Shell, nodes: list[StorageNode]
) -> int:
    """
    To figure out the number of a complex object copies, we firstly
    need to retrieve its Last object. We consider that the number of
    complex object copies is equal to the number of its last object
    copies. When we have the Last object ID, the task is reduced
    to getting simple object copies.
    Args:
        wallet (str): the path to the wallet on whose behalf the
                            copies are got
        cid (str): ID of the container
        oid (str): ID of the Object
        shell: executor for cli command
    Returns:
        (int): the number of object copies in the container
    """
    last_oid = complex_object_actions.get_last_object(wallet, cid, oid, shell, nodes)
    assert last_oid, f"No Last Object for {cid}/{oid} found among all Storage Nodes"
    return get_simple_object_copies(wallet, cid, last_oid, shell, nodes)


@allure.step("Get Nodes With Object")
def get_nodes_with_object(
    cid: str, oid: str, shell: Shell, nodes: list[StorageNode]
) -> list[StorageNode]:
    """
    The function returns list of nodes which store
    the given object.
    Args:
         cid (str): ID of the container which store the object
         oid (str): object ID
         shell: executor for cli command
         nodes: nodes to find on
    Returns:
         (list): nodes which store the object
    """

    nodes_list = []
    for node in nodes:
        wallet = node.get_wallet_path()
        wallet_config = node.get_wallet_config_path()
        try:
            res = frostfs_verbs.head_object(
                wallet,
                cid,
                oid,
                shell=shell,
                endpoint=node.get_rpc_endpoint(),
                is_direct=True,
                wallet_config=wallet_config,
            )
            if res is not None:
                logger.info(f"Found object {oid} on node {node}")
                nodes_list.append(node)
        except Exception:
            logger.info(f"No {oid} object copy found on {node}, continue")
            continue
    return nodes_list


@allure.step("Get Nodes Without Object")
def get_nodes_without_object(
    wallet: str, cid: str, oid: str, shell: Shell, nodes: list[StorageNode]
) -> list[StorageNode]:
    """
    The function returns list of nodes which do not store
    the given object.
    Args:
         wallet (str): the path to the wallet on whose behalf
                     we request the nodes
         cid (str): ID of the container which store the object
         oid (str): object ID
         shell: executor for cli command
    Returns:
         (list): nodes which do not store the object
    """
    nodes_list = []
    for node in nodes:
        try:
            res = frostfs_verbs.head_object(
                wallet, cid, oid, shell=shell, endpoint=node.get_rpc_endpoint(), is_direct=True
            )
            if res is None:
                nodes_list.append(node)
        except Exception as err:
            if error_matches_status(err, OBJECT_NOT_FOUND):
                nodes_list.append(node)
            else:
                raise Exception(f"Got error {err} on head object command") from err
    return nodes_list
