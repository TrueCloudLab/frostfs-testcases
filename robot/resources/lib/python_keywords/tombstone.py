import json
import logging

import allure
from frostfs_testlib.shell import Shell
from frostfs_verbs import head_object
from neo3.wallet import wallet

logger = logging.getLogger("NeoLogger")


@allure.step("Verify Head Tombstone")
def verify_head_tombstone(
    wallet_path: str, cid: str, oid_ts: str, oid: str, shell: Shell, endpoint: str
):
    header = head_object(wallet_path, cid, oid_ts, shell=shell, endpoint=endpoint)["header"]

    s_oid = header["sessionToken"]["body"]["object"]["target"]["objects"]
    logger.info(f"Header Session OIDs is {s_oid}")
    logger.info(f"OID is {oid}")

    assert header["containerID"] == cid, "Tombstone Header CID is wrong"

    with open(wallet_path, "r") as file:
        wlt_data = json.loads(file.read())
    wlt = wallet.Wallet.from_json(wlt_data, password="")
    addr = wlt.accounts[0].address

    assert header["ownerID"] == addr, "Tombstone Owner ID is wrong"
    assert header["objectType"] == "TOMBSTONE", "Header Type isn't Tombstone"
    assert (
        header["sessionToken"]["body"]["object"]["verb"] == "DELETE"
    ), "Header Session Type isn't DELETE"
    assert (
        header["sessionToken"]["body"]["object"]["target"]["container"] == cid
    ), "Header Session ID is wrong"
    assert (
        oid in header["sessionToken"]["body"]["object"]["target"]["objects"]
    ), "Header Session OID is wrong"
