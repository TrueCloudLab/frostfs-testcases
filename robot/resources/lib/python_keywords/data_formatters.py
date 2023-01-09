import base64
import json

import base58
from neo3.wallet import wallet


def dict_to_attrs(attrs: dict) -> str:
    """
    This function takes a dictionary of object's attributes and converts them
    into string. The string is passed to `--attributes` key of frostfs-cli.

    Args:
        attrs (dict): object attributes in {"a": "b", "c": "d"} format.

    Returns:
        (str): string in "a=b,c=d" format.
    """
    return ",".join(f"{key}={value}" for key, value in attrs.items())


def __fix_wallet_schema(wallet: dict) -> None:
    # Temporary function to fix wallets that do not conform to the schema
    # TODO: get rid of it once issue  is solved
    if "name" not in wallet:
        wallet["name"] = None
    for account in wallet["accounts"]:
        if "extra" not in account:
            account["extra"] = None


def get_wallet_public_key(wallet_path: str, wallet_password: str, format: str = "hex") -> str:
    #  Get public key from wallet file
    with open(wallet_path, "r") as file:
        wallet_content = json.load(file)
    __fix_wallet_schema(wallet_content)

    wallet_from_json = wallet.Wallet.from_json(wallet_content, password=wallet_password)
    public_key_hex = str(wallet_from_json.accounts[0].public_key)

    # Convert public key to specified format
    if format == "hex":
        return public_key_hex
    if format == "base58":
        public_key_base58 = base58.b58encode(bytes.fromhex(public_key_hex))
        return public_key_base58.decode("utf-8")
    if format == "base64":
        public_key_base64 = base64.b64encode(bytes.fromhex(public_key_hex))
        return public_key_base64.decode("utf-8")
    raise ValueError(f"Invalid public key format: {format}")
