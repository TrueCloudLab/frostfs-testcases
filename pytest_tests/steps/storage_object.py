import logging
from time import sleep

import allure
import pytest
from cluster import Cluster
from epoch import tick_epoch
from frostfs_testlib.shell import Shell
from grpc_responses import OBJECT_ALREADY_REMOVED
from python_keywords.frostfs_verbs import delete_object, get_object
from storage_object_info import StorageObjectInfo
from tombstone import verify_head_tombstone

logger = logging.getLogger("NeoLogger")

CLEANUP_TIMEOUT = 10


@allure.step("Delete Objects")
def delete_objects(
    storage_objects: list[StorageObjectInfo], shell: Shell, cluster: Cluster
) -> None:
    """
    Deletes given storage objects.

    Args:
        storage_objects: list of objects to delete
        shell: executor for cli command
    """

    with allure.step("Delete objects"):
        for storage_object in storage_objects:
            storage_object.tombstone = delete_object(
                storage_object.wallet_file_path,
                storage_object.cid,
                storage_object.oid,
                shell=shell,
                endpoint=cluster.default_rpc_endpoint,
            )
            verify_head_tombstone(
                wallet_path=storage_object.wallet_file_path,
                cid=storage_object.cid,
                oid_ts=storage_object.tombstone,
                oid=storage_object.oid,
                shell=shell,
                endpoint=cluster.default_rpc_endpoint,
            )

    tick_epoch(shell, cluster)
    sleep(CLEANUP_TIMEOUT)

    with allure.step("Get objects and check errors"):
        for storage_object in storage_objects:
            with pytest.raises(Exception, match=OBJECT_ALREADY_REMOVED):
                get_object(
                    storage_object.wallet_file_path,
                    storage_object.cid,
                    storage_object.oid,
                    shell=shell,
                    endpoint=cluster.default_rpc_endpoint,
                )
