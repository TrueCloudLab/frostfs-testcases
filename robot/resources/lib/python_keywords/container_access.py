from typing import List, Optional

from acl import EACLOperation
from cluster import Cluster
from frostfs_testlib.shell import Shell
from python_keywords.object_access import (
    can_delete_object,
    can_get_head_object,
    can_get_object,
    can_get_range_hash_of_object,
    can_get_range_of_object,
    can_put_object,
    can_search_object,
)


def check_full_access_to_container(
    wallet: str,
    cid: str,
    oid: str,
    file_name: str,
    shell: Shell,
    cluster: Cluster,
    bearer: Optional[str] = None,
    wallet_config: Optional[str] = None,
    xhdr: Optional[dict] = None,
):
    endpoint = cluster.default_rpc_endpoint
    assert can_put_object(wallet, cid, file_name, shell, cluster, bearer, wallet_config, xhdr)
    assert can_get_head_object(wallet, cid, oid, shell, endpoint, bearer, wallet_config, xhdr)
    assert can_get_range_of_object(wallet, cid, oid, shell, endpoint, bearer, wallet_config, xhdr)
    assert can_get_range_hash_of_object(
        wallet, cid, oid, shell, endpoint, bearer, wallet_config, xhdr
    )
    assert can_search_object(wallet, cid, shell, endpoint, oid, bearer, wallet_config, xhdr)
    assert can_get_object(wallet, cid, oid, file_name, shell, cluster, bearer, wallet_config, xhdr)
    assert can_delete_object(wallet, cid, oid, shell, endpoint, bearer, wallet_config, xhdr)


def check_no_access_to_container(
    wallet: str,
    cid: str,
    oid: str,
    file_name: str,
    shell: Shell,
    cluster: Cluster,
    bearer: Optional[str] = None,
    wallet_config: Optional[str] = None,
    xhdr: Optional[dict] = None,
):
    endpoint = cluster.default_rpc_endpoint
    assert not can_put_object(wallet, cid, file_name, shell, cluster, bearer, wallet_config, xhdr)
    assert not can_get_head_object(wallet, cid, oid, shell, endpoint, bearer, wallet_config, xhdr)
    assert not can_get_range_of_object(
        wallet, cid, oid, shell, endpoint, bearer, wallet_config, xhdr
    )
    assert not can_get_range_hash_of_object(
        wallet, cid, oid, shell, endpoint, bearer, wallet_config, xhdr
    )
    assert not can_search_object(wallet, cid, shell, endpoint, oid, bearer, wallet_config, xhdr)
    assert not can_get_object(
        wallet, cid, oid, file_name, shell, cluster, bearer, wallet_config, xhdr
    )
    assert not can_delete_object(wallet, cid, oid, shell, endpoint, bearer, wallet_config, xhdr)


def check_custom_access_to_container(
    wallet: str,
    cid: str,
    oid: str,
    file_name: str,
    shell: Shell,
    cluster: Cluster,
    deny_operations: Optional[List[EACLOperation]] = None,
    ignore_operations: Optional[List[EACLOperation]] = None,
    bearer: Optional[str] = None,
    wallet_config: Optional[str] = None,
    xhdr: Optional[dict] = None,
):
    endpoint = cluster.default_rpc_endpoint
    deny_operations = [op.value for op in deny_operations or []]
    ignore_operations = [op.value for op in ignore_operations or []]
    checks: dict = {}
    if EACLOperation.PUT.value not in ignore_operations:
        checks[EACLOperation.PUT.value] = can_put_object(
            wallet, cid, file_name, shell, cluster, bearer, wallet_config, xhdr
        )
    if EACLOperation.HEAD.value not in ignore_operations:
        checks[EACLOperation.HEAD.value] = can_get_head_object(
            wallet, cid, oid, shell, endpoint, bearer, wallet_config, xhdr
        )
    if EACLOperation.GET_RANGE.value not in ignore_operations:
        checks[EACLOperation.GET_RANGE.value] = can_get_range_of_object(
            wallet, cid, oid, shell, endpoint, bearer, wallet_config, xhdr
        )
    if EACLOperation.GET_RANGE_HASH.value not in ignore_operations:
        checks[EACLOperation.GET_RANGE_HASH.value] = can_get_range_hash_of_object(
            wallet, cid, oid, shell, endpoint, bearer, wallet_config, xhdr
        )
    if EACLOperation.SEARCH.value not in ignore_operations:
        checks[EACLOperation.SEARCH.value] = can_search_object(
            wallet, cid, shell, endpoint, oid, bearer, wallet_config, xhdr
        )
    if EACLOperation.GET.value not in ignore_operations:
        checks[EACLOperation.GET.value] = can_get_object(
            wallet, cid, oid, file_name, shell, cluster, bearer, wallet_config, xhdr
        )
    if EACLOperation.DELETE.value not in ignore_operations:
        checks[EACLOperation.DELETE.value] = can_delete_object(
            wallet, cid, oid, shell, endpoint, bearer, wallet_config, xhdr
        )

    failed_checks = [
        f"allowed {action} failed"
        for action, success in checks.items()
        if not success and action not in deny_operations
    ] + [
        f"denied {action} succeeded"
        for action, success in checks.items()
        if success and action in deny_operations
    ]

    assert not failed_checks, ", ".join(failed_checks)


def check_read_only_container(
    wallet: str,
    cid: str,
    oid: str,
    file_name: str,
    shell: Shell,
    cluster: Cluster,
    bearer: Optional[str] = None,
    wallet_config: Optional[str] = None,
    xhdr: Optional[dict] = None,
):
    return check_custom_access_to_container(
        wallet,
        cid,
        oid,
        file_name,
        deny_operations=[EACLOperation.PUT, EACLOperation.DELETE],
        bearer=bearer,
        wallet_config=wallet_config,
        xhdr=xhdr,
        shell=shell,
        cluster=cluster,
    )
