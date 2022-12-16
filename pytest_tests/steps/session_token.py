import base64
import json
import logging
import os
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

import allure
import json_transformers
from common import ASSETS_DIR, NEOFS_CLI_EXEC, WALLET_CONFIG
from data_formatters import get_wallet_public_key
from json_transformers import encode_for_json
from neofs_testlib.cli import NeofsCli
from neofs_testlib.shell import Shell
from storage_object_info import StorageObjectInfo
from wallet import WalletFile

logger = logging.getLogger("NeoLogger")

UNRELATED_KEY = "unrelated key in the session"
UNRELATED_OBJECT = "unrelated object in the session"
UNRELATED_CONTAINER = "unrelated container in the session"
WRONG_VERB = "wrong verb of the session"
INVALID_SIGNATURE = "invalid signature of the session data"


class ObjectVerb(Enum):
    PUT = "PUT"
    DELETE = "DELETE"
    GET = "GET"
    RANGEHASH = "RANGEHASH"
    RANGE = "RANGE"
    HEAD = "HEAD"
    SEARCH = "SEARCH"


class ContainerVerb(Enum):
    CREATE = "PUT"
    DELETE = "DELETE"
    SETEACL = "SETEACL"


@dataclass
class Lifetime:
    exp: int = 100000000
    nbf: int = 0
    iat: int = 0


@allure.step("Generate Session Token")
def generate_session_token(
    owner_wallet: WalletFile,
    session_wallet: WalletFile,
    session: dict[str, dict[str, Any]],
    tokens_dir: str,
    lifetime: Optional[Lifetime] = None,
) -> str:
    """
    This function generates session token  and writes it to the file.
    Args:
        owner_wallet: wallet of container owner
        session_wallet: wallet to which we grant the access via session token
        session: Contains allowed operation with parameters
        tokens_dir: Dir for token
        lifetime: lifetime options for session
    Returns:
        The path to the generated session token file
    """

    file_path = os.path.join(tokens_dir, str(uuid.uuid4()))

    pub_key_64 = get_wallet_public_key(session_wallet.path, session_wallet.password, "base64")

    lifetime = lifetime or Lifetime()

    session_token = {
        "body": {
            "id": f"{base64.b64encode(uuid.uuid4().bytes).decode('utf-8')}",
            "ownerID": {
                "value": f"{json_transformers.encode_for_json(owner_wallet.get_address())}"
            },
            "lifetime": {
                "exp": f"{lifetime.exp}",
                "nbf": f"{lifetime.nbf}",
                "iat": f"{lifetime.iat}",
            },
            "sessionKey": pub_key_64,
        }
    }
    session_token["body"].update(session)

    logger.info(f"Got this Session Token: {session_token}")
    with open(file_path, "w", encoding="utf-8") as session_token_file:
        json.dump(session_token, session_token_file, ensure_ascii=False, indent=4)

    return file_path


@allure.step("Generate Session Token For Container")
def generate_container_session_token(
    owner_wallet: WalletFile,
    session_wallet: WalletFile,
    verb: ContainerVerb,
    tokens_dir: str,
    lifetime: Optional[Lifetime] = None,
    cid: Optional[str] = None,
) -> str:
    """
    This function generates session token for ContainerSessionContext
    and writes it to the file. It is able to prepare session token file
    for a specific container (<cid>) or for every container (adds
    "wildcard" field).
    Args:
        owner_wallet: wallet of container owner.
        session_wallet: wallet to which we grant the access via session token.
        verb: verb to grant access to.
        lifetime: lifetime options for session.
        cid: container ID of the container
    Returns:
        The path to the generated session token file
    """
    session = {
        "container": {
            "verb": verb.value,
            "wildcard": cid is None,
            **({"containerID": {"value": f"{encode_for_json(cid)}"}} if cid is not None else {}),
        },
    }

    return generate_session_token(
        owner_wallet=owner_wallet,
        session_wallet=session_wallet,
        session=session,
        tokens_dir=tokens_dir,
        lifetime=lifetime,
    )


@allure.step("Generate Session Token For Object")
def generate_object_session_token(
    owner_wallet: WalletFile,
    session_wallet: WalletFile,
    oids: list[str],
    cid: str,
    verb: ObjectVerb,
    tokens_dir: str,
    lifetime: Optional[Lifetime] = None,
) -> str:
    """
    This function generates session token for ObjectSessionContext
    and writes it to the file.
    Args:
        owner_wallet: wallet of container owner
        session_wallet: wallet to which we grant the access via session token
        cid: container ID of the container
        oids: list of objectIDs to put into session
        verb: verb to grant access to; Valid verbs are: ObjectVerb.
        lifetime: lifetime options for session
    Returns:
        The path to the generated session token file
    """
    session = {
        "object": {
            "verb": verb.value,
            "target": {
                "container": {"value": encode_for_json(cid)},
                "objects": [{"value": encode_for_json(oid)} for oid in oids],
            },
        },
    }

    return generate_session_token(
        owner_wallet=owner_wallet,
        session_wallet=session_wallet,
        session=session,
        tokens_dir=tokens_dir,
        lifetime=lifetime,
    )


@allure.step("Get signed token for container session")
def get_container_signed_token(
    owner_wallet: WalletFile,
    user_wallet: WalletFile,
    verb: ContainerVerb,
    shell: Shell,
    tokens_dir: str,
    lifetime: Optional[Lifetime] = None,
) -> str:
    """
    Returns signed token file path for static container session
    """
    session_token_file = generate_container_session_token(
        owner_wallet=owner_wallet,
        session_wallet=user_wallet,
        verb=verb,
        tokens_dir=tokens_dir,
        lifetime=lifetime,
    )
    return sign_session_token(shell, session_token_file, owner_wallet)


@allure.step("Get signed token for object session")
def get_object_signed_token(
    owner_wallet: WalletFile,
    user_wallet: WalletFile,
    cid: str,
    storage_objects: list[StorageObjectInfo],
    verb: ObjectVerb,
    shell: Shell,
    tokens_dir: str,
    lifetime: Optional[Lifetime] = None,
) -> str:
    """
    Returns signed token file path for static object session
    """
    storage_object_ids = [storage_object.oid for storage_object in storage_objects]
    session_token_file = generate_object_session_token(
        owner_wallet=owner_wallet,
        session_wallet=user_wallet,
        oids=storage_object_ids,
        cid=cid,
        verb=verb,
        tokens_dir=tokens_dir,
        lifetime=lifetime,
    )
    return sign_session_token(shell, session_token_file, owner_wallet)


@allure.step("Create Session Token")
def create_session_token(
    shell: Shell,
    owner: str,
    wallet_path: str,
    wallet_password: str,
    rpc_endpoint: str,
) -> str:
    """
    Create session token for an object.
    Args:
        shell: Shell instance.
        owner: User that writes the token.
        wallet_path: The path to wallet to which we grant the access via session token.
        wallet_password: Wallet password.
        rpc_endpoint: Remote node address (as 'multiaddr' or '<host>:<port>').
    Returns:
        The path to the generated session token file.
    """
    session_token = os.path.join(os.getcwd(), ASSETS_DIR, str(uuid.uuid4()))
    neofscli = NeofsCli(shell=shell, neofs_cli_exec_path=NEOFS_CLI_EXEC)
    neofscli.session.create(
        rpc_endpoint=rpc_endpoint,
        address=owner,
        wallet=wallet_path,
        wallet_password=wallet_password,
        out=session_token,
    )
    return session_token


@allure.step("Sign Session Token")
def sign_session_token(shell: Shell, session_token_file: str, wlt: WalletFile) -> str:
    """
    This function signs the session token by the given wallet.

    Args:
        shell: Shell instance.
        session_token_file: The path to the session token file.
        wlt: The path to the signing wallet.

    Returns:
        The path to the signed token.
    """
    signed_token_file = os.path.join(os.getcwd(), ASSETS_DIR, str(uuid.uuid4()))
    neofscli = NeofsCli(shell=shell, neofs_cli_exec_path=NEOFS_CLI_EXEC, config_file=WALLET_CONFIG)
    neofscli.util.sign_session_token(
        wallet=wlt.path, from_file=session_token_file, to_file=signed_token_file
    )
    return signed_token_file
