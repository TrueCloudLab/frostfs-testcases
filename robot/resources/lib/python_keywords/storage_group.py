"""
    This module contains keywords for work with Storage Groups.
    It contains wrappers for `neofs-cli storagegroup` verbs.
"""
import logging
from typing import Optional

import allure
from cluster import Cluster
from common import NEOFS_CLI_EXEC, WALLET_CONFIG
from complex_object_actions import get_link_object
from neofs_testlib.cli import NeofsCli
from neofs_testlib.shell import Shell
from neofs_verbs import head_object

logger = logging.getLogger("NeoLogger")


@allure.step("Put Storagegroup")
def put_storagegroup(
    shell: Shell,
    endpoint: str,
    wallet: str,
    cid: str,
    objects: list,
    bearer: Optional[str] = None,
    wallet_config: str = WALLET_CONFIG,
    lifetime: int = 10,
) -> str:
    """
    Wrapper for `neofs-cli storagegroup put`. Before the SG is created,
    neofs-cli performs HEAD on `objects`, so this verb must be allowed
    for `wallet` in `cid`.
    Args:
        shell: Shell instance.
        wallet: Path to wallet on whose behalf the SG is created.
        cid: ID of Container to put SG to.
        lifetime: Storage group lifetime in epochs.
        objects: List of Object IDs to include into the SG.
        bearer: Path to Bearer token file.
        wallet_config: Path to neofs-cli config file.
    Returns:
        Object ID of created Storage Group.
    """
    neofscli = NeofsCli(shell=shell, neofs_cli_exec_path=NEOFS_CLI_EXEC, config_file=wallet_config)
    result = neofscli.storagegroup.put(
        wallet=wallet,
        cid=cid,
        lifetime=lifetime,
        members=objects,
        bearer=bearer,
        rpc_endpoint=endpoint,
    )
    gid = result.stdout.split("\n")[1].split(": ")[1]
    return gid


@allure.step("List Storagegroup")
def list_storagegroup(
    shell: Shell,
    endpoint: str,
    wallet: str,
    cid: str,
    bearer: Optional[str] = None,
    wallet_config: str = WALLET_CONFIG,
) -> list:
    """
    Wrapper for `neofs-cli storagegroup list`.  This operation
    requires SEARCH allowed for `wallet` in `cid`.
    Args:
        shell: Shell instance.
        wallet: Path to wallet on whose behalf the SGs are listed in the container
        cid: ID of Container to list.
        bearer: Path to Bearer token file.
        wallet_config: Path to neofs-cli config file.
    Returns:
        Object IDs of found Storage Groups.
    """
    neofscli = NeofsCli(shell=shell, neofs_cli_exec_path=NEOFS_CLI_EXEC, config_file=wallet_config)
    result = neofscli.storagegroup.list(
        wallet=wallet,
        cid=cid,
        bearer=bearer,
        rpc_endpoint=endpoint,
    )
    # throwing off the first string of output
    found_objects = result.stdout.split("\n")[1:]
    return found_objects


@allure.step("Get Storagegroup")
def get_storagegroup(
    shell: Shell,
    endpoint: str,
    wallet: str,
    cid: str,
    gid: str,
    bearer: str = "",
    wallet_config: str = WALLET_CONFIG,
) -> dict:
    """
    Wrapper for `neofs-cli storagegroup get`.
    Args:
        shell: Shell instance.
        wallet: Path to wallet on whose behalf the SG is got.
        cid: ID of Container where SG is stored.
        gid: ID of the Storage Group.
        bearer: Path to Bearer token file.
        wallet_config: Path to neofs-cli config file.
    Returns:
        Detailed information on the Storage Group.
    """
    neofscli = NeofsCli(shell=shell, neofs_cli_exec_path=NEOFS_CLI_EXEC, config_file=wallet_config)
    result = neofscli.storagegroup.get(
        wallet=wallet,
        cid=cid,
        bearer=bearer,
        id=gid,
        rpc_endpoint=endpoint,
    )

    # TODO: temporary solution for parsing output. Needs to be replaced with
    # JSON parsing when https://github.com/nspcc-dev/neofs-node/issues/1355
    # is done.
    strings = result.stdout.strip().split("\n")
    # first three strings go to `data`;
    # skip the 'Members:' string;
    # the rest of strings go to `members`
    data, members = strings[:3], strings[3:]
    sg_dict = {}
    for i in data:
        key, val = i.split(": ")
        sg_dict[key] = val
    sg_dict["Members"] = []
    for member in members[1:]:
        sg_dict["Members"].append(member.strip())
    return sg_dict


@allure.step("Delete Storagegroup")
def delete_storagegroup(
    shell: Shell,
    endpoint: str,
    wallet: str,
    cid: str,
    gid: str,
    bearer: str = "",
    wallet_config: str = WALLET_CONFIG,
) -> str:
    """
    Wrapper for `neofs-cli storagegroup delete`.
    Args:
        shell: Shell instance.
        wallet: Path to wallet on whose behalf the SG is deleted.
        cid: ID of Container where SG is stored.
        gid: ID of the Storage Group.
        bearer: Path to Bearer token file.
        wallet_config: Path to neofs-cli config file.
    Returns:
        Tombstone ID of the deleted Storage Group.
    """
    neofscli = NeofsCli(shell=shell, neofs_cli_exec_path=NEOFS_CLI_EXEC, config_file=wallet_config)
    result = neofscli.storagegroup.delete(
        wallet=wallet,
        cid=cid,
        bearer=bearer,
        id=gid,
        rpc_endpoint=endpoint,
    )
    tombstone_id = result.stdout.strip().split("\n")[1].split(": ")[1]
    return tombstone_id


@allure.step("Verify list operation over Storagegroup")
def verify_list_storage_group(
    shell: Shell,
    endpoint: str,
    wallet: str,
    cid: str,
    gid: str,
    bearer: str = None,
    wallet_config: str = WALLET_CONFIG,
):
    storage_groups = list_storagegroup(
        shell=shell,
        endpoint=endpoint,
        wallet=wallet,
        cid=cid,
        bearer=bearer,
        wallet_config=wallet_config,
    )
    assert gid in storage_groups


@allure.step("Verify get operation over Storagegroup")
def verify_get_storage_group(
    shell: Shell,
    cluster: Cluster,
    wallet: str,
    cid: str,
    gid: str,
    obj_list: list,
    object_size: int,
    max_object_size: int,
    bearer: str = None,
    wallet_config: str = WALLET_CONFIG,
):
    obj_parts = []
    endpoint = cluster.default_rpc_endpoint
    if object_size > max_object_size:
        for obj in obj_list:
            link_oid = get_link_object(
                wallet,
                cid,
                obj,
                shell=shell,
                nodes=cluster.storage_nodes,
                bearer=bearer,
                wallet_config=wallet_config,
            )
            obj_head = head_object(
                wallet=wallet,
                cid=cid,
                oid=link_oid,
                shell=shell,
                endpoint=endpoint,
                is_raw=True,
                bearer=bearer,
                wallet_config=wallet_config,
            )
            obj_parts = obj_head["header"]["split"]["children"]

    obj_num = len(obj_list)
    storagegroup_data = get_storagegroup(
        shell=shell,
        endpoint=endpoint,
        wallet=wallet,
        cid=cid,
        gid=gid,
        bearer=bearer,
        wallet_config=wallet_config,
    )
    exp_size = object_size * obj_num
    if object_size < max_object_size:
        assert int(storagegroup_data["Group size"]) == exp_size
        assert storagegroup_data["Members"] == obj_list
    else:
        assert int(storagegroup_data["Group size"]) == exp_size
        assert storagegroup_data["Members"] == obj_parts
