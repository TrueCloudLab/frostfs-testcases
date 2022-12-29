import base64
import logging
import os
import random
import re
import shutil
import uuid
import zipfile
from typing import Optional
from urllib.parse import quote_plus

import allure
import requests
from aws_cli_client import LONG_TIMEOUT
from cli_helpers import _cmd_run
from cluster import StorageNode
from common import SIMPLE_OBJECT_SIZE
from file_helper import get_file_hash
from neofs_testlib.shell import Shell
from python_keywords.neofs_verbs import get_object
from python_keywords.storage_policy import get_nodes_without_object

logger = logging.getLogger("NeoLogger")

ASSETS_DIR = os.getenv("ASSETS_DIR", "TemporaryDir/")


@allure.step("Get via HTTP Gate")
def get_via_http_gate(cid: str, oid: str, endpoint: str, request_path: Optional[str] = None):
    """
    This function gets given object from HTTP gate
    cid:          container id to get object from
    oid:          object ID
    endpoint:     http gate endpoint
    request_path: (optional) http request, if ommited - use default [{endpoint}/get/{cid}/{oid}]
    """

    # if `request_path` parameter ommited, use default
    if request_path is None:
        request = f"{endpoint}/get/{cid}/{oid}"
    else:
        request = f"{endpoint}{request_path}"

    resp = requests.get(request, stream=True)

    if not resp.ok:
        raise Exception(
            f"""Failed to get object via HTTP gate:
                request: {resp.request.path_url},
                response: {resp.text},
                status code: {resp.status_code} {resp.reason}"""
        )

    logger.info(f"Request: {request}")
    _attach_allure_step(request, resp.status_code)

    file_path = os.path.join(os.getcwd(), ASSETS_DIR, f"{cid}_{oid}")
    with open(file_path, "wb") as file:
        shutil.copyfileobj(resp.raw, file)
    return file_path


@allure.step("Get via Zip HTTP Gate")
def get_via_zip_http_gate(cid: str, prefix: str, endpoint: str):
    """
    This function gets given object from HTTP gate
    cid:      container id to get object from
    prefix:   common prefix
    endpoint: http gate endpoint
    """
    request = f"{endpoint}/zip/{cid}/{prefix}"
    resp = requests.get(request, stream=True)

    if not resp.ok:
        raise Exception(
            f"""Failed to get object via HTTP gate:
                request: {resp.request.path_url},
                response: {resp.text},
                status code: {resp.status_code} {resp.reason}"""
        )

    logger.info(f"Request: {request}")
    _attach_allure_step(request, resp.status_code)

    file_path = os.path.join(os.getcwd(), ASSETS_DIR, f"{cid}_archive.zip")
    with open(file_path, "wb") as file:
        shutil.copyfileobj(resp.raw, file)

    with zipfile.ZipFile(file_path, "r") as zip_ref:
        zip_ref.extractall(ASSETS_DIR)

    return os.path.join(os.getcwd(), ASSETS_DIR, prefix)


@allure.step("Get via HTTP Gate by attribute")
def get_via_http_gate_by_attribute(
    cid: str, attribute: dict, endpoint: str, request_path: Optional[str] = None
):
    """
    This function gets given object from HTTP gate
    cid:          CID to get object from
    attribute:    attribute {name: attribute} value pair
    endpoint:     http gate endpoint
    request_path: (optional) http request path, if ommited - use default [{endpoint}/get_by_attribute/{Key}/{Value}]
    """
    attr_name = list(attribute.keys())[0]
    attr_value = quote_plus(str(attribute.get(attr_name)))
    # if `request_path` parameter ommited, use default
    if request_path is None:
        request = f"{endpoint}/get_by_attribute/{cid}/{quote_plus(str(attr_name))}/{attr_value}"
    else:
        request = f"{endpoint}{request_path}"

    resp = requests.get(request, stream=True)

    if not resp.ok:
        raise Exception(
            f"""Failed to get object via HTTP gate:
                request: {resp.request.path_url},
                response: {resp.text},
                status code: {resp.status_code} {resp.reason}"""
        )

    logger.info(f"Request: {request}")
    _attach_allure_step(request, resp.status_code)

    file_path = os.path.join(os.getcwd(), ASSETS_DIR, f"{cid}_{str(uuid.uuid4())}")
    with open(file_path, "wb") as file:
        shutil.copyfileobj(resp.raw, file)
    return file_path


@allure.step("Upload via HTTP Gate")
def upload_via_http_gate(cid: str, path: str, endpoint: str, headers: dict = None) -> str:
    """
    This function upload given object through HTTP gate
    cid:      CID to get object from
    path:     File path to upload
    endpoint: http gate endpoint
    headers:  Object header
    """
    request = f"{endpoint}/upload/{cid}"
    files = {"upload_file": open(path, "rb")}
    body = {"filename": path}
    resp = requests.post(request, files=files, data=body, headers=headers)

    if not resp.ok:
        raise Exception(
            f"""Failed to get object via HTTP gate:
                request: {resp.request.path_url},
                response: {resp.text},
                status code: {resp.status_code} {resp.reason}"""
        )

    logger.info(f"Request: {request}")
    _attach_allure_step(request, resp.json(), req_type="POST")

    assert resp.json().get("object_id"), f"OID found in response {resp}"

    return resp.json().get("object_id")


@allure.step("Check is the passed object large")
def is_object_large(filepath: str) -> bool:
    """
    This function check passed file size and return True if file_size > SIMPLE_OBJECT_SIZE
    filepath: File path to check
    """
    file_size = os.path.getsize(filepath)
    logger.info(f"Size= {file_size}")
    if file_size > int(SIMPLE_OBJECT_SIZE):
        return True
    else:
        return False


@allure.step("Upload via HTTP Gate using Curl")
def upload_via_http_gate_curl(
    cid: str,
    filepath: str,
    endpoint: str,
    headers: list = None,
    error_pattern: Optional[str] = None,
) -> str:
    """
    This function upload given object through HTTP gate using curl utility.
    cid: CID to get object from
    filepath: File path to upload
    headers: Object header
    endpoint: http gate endpoint
    error_pattern: [optional] expected error message from the command
    """
    request = f"{endpoint}/upload/{cid}"
    attributes = ""
    if headers:
        # parse attributes
        attributes = " ".join(headers)

    large_object = is_object_large(filepath)
    if large_object:
        # pre-clean
        _cmd_run("rm pipe -f")
        files = f"file=@pipe;filename={os.path.basename(filepath)}"
        cmd = f"mkfifo pipe;cat {filepath} > pipe & curl --no-buffer -F '{files}' {attributes} {request}"
        output = _cmd_run(cmd, LONG_TIMEOUT)
        # clean up pipe
        _cmd_run("rm pipe")
    else:
        files = f"file=@{filepath};filename={os.path.basename(filepath)}"
        cmd = f"curl -F '{files}' {attributes} {request}"
        output = _cmd_run(cmd)

    if error_pattern:
        match = error_pattern.casefold() in str(output).casefold()
        assert match, f"Expected {output} to match {error_pattern}"
        return ""

    oid_re = re.search(r'"object_id": "(.*)"', output)
    if not oid_re:
        raise AssertionError(f'Could not find "object_id" in {output}')
    return oid_re.group(1)


@allure.step("Get via HTTP Gate using Curl")
def get_via_http_curl(cid: str, oid: str, endpoint: str) -> str:
    """
    This function gets given object from HTTP gate using curl utility.
    cid:      CID to get object from
    oid:      object OID
    endpoint: http gate endpoint
    """
    request = f"{endpoint}/get/{cid}/{oid}"
    file_path = os.path.join(os.getcwd(), ASSETS_DIR, f"{cid}_{oid}_{str(uuid.uuid4())}")

    cmd = f"curl {request} > {file_path}"
    _cmd_run(cmd)

    return file_path


def _attach_allure_step(request: str, status_code: int, req_type="GET"):
    command_attachment = f"REQUEST: '{request}'\n" f"RESPONSE:\n {status_code}\n"
    with allure.step(f"{req_type} Request"):
        allure.attach(command_attachment, f"{req_type} Request", allure.attachment_type.TEXT)


@allure.step("Try to get object and expect error")
def try_to_get_object_and_expect_error(
    cid: str, oid: str, error_pattern: str, endpoint: str
) -> None:
    try:
        get_via_http_gate(cid=cid, oid=oid, endpoint=endpoint)
        raise AssertionError(f"Expected error on getting object with cid: {cid}")
    except Exception as err:
        match = error_pattern.casefold() in str(err).casefold()
        assert match, f"Expected {err} to match {error_pattern}"


@allure.step("Verify object can be get using HTTP header attribute")
def get_object_by_attr_and_verify_hashes(
    oid: str, file_name: str, cid: str, attrs: dict, endpoint: str
) -> None:
    got_file_path_http = get_via_http_gate(cid=cid, oid=oid, endpoint=endpoint)
    got_file_path_http_attr = get_via_http_gate_by_attribute(
        cid=cid, attribute=attrs, endpoint=endpoint
    )
    assert_hashes_are_equal(file_name, got_file_path_http, got_file_path_http_attr)


def get_object_and_verify_hashes(
    oid: str,
    file_name: str,
    wallet: str,
    cid: str,
    shell: Shell,
    nodes: list[StorageNode],
    endpoint: str,
    object_getter=None,
) -> None:

    nodes_list = get_nodes_without_object(
        wallet=wallet,
        cid=cid,
        oid=oid,
        shell=shell,
        nodes=nodes,
    )
    # for some reason we can face with case when nodes_list is empty due to object resides in all nodes
    if nodes_list:
        random_node = random.choice(nodes_list)
    else:
        random_node = random.choice(nodes)

    object_getter = object_getter or get_via_http_gate

    got_file_path = get_object(
        wallet=wallet,
        cid=cid,
        oid=oid,
        shell=shell,
        endpoint=random_node.get_rpc_endpoint(),
    )
    got_file_path_http = object_getter(cid=cid, oid=oid, endpoint=endpoint)

    assert_hashes_are_equal(file_name, got_file_path, got_file_path_http)


def assert_hashes_are_equal(orig_file_name: str, got_file_1: str, got_file_2: str) -> None:
    msg = "Expected hashes are equal for files {f1} and {f2}"
    got_file_hash_http = get_file_hash(got_file_1)
    assert get_file_hash(got_file_2) == got_file_hash_http, msg.format(f1=got_file_2, f2=got_file_1)
    assert get_file_hash(orig_file_name) == got_file_hash_http, msg.format(
        f1=orig_file_name, f2=got_file_1
    )


def attr_into_header(attrs: dict) -> dict:
    return {f"X-Attribute-{_key}": _value for _key, _value in attrs.items()}


@allure.step(
    "Convert each attribute (Key=Value) to the following format: -H 'X-Attribute-Key: Value'"
)
def attr_into_str_header_curl(attrs: dict) -> list:
    headers = []
    for k, v in attrs.items():
        headers.append(f"-H 'X-Attribute-{k}: {v}'")
    logger.info(f"[List of Attrs for curl:] {headers}")
    return headers


@allure.step(
    "Try to get object via http (pass http_request and optional attributes) and expect error"
)
def try_to_get_object_via_passed_request_and_expect_error(
    cid: str,
    oid: str,
    error_pattern: str,
    endpoint: str,
    http_request_path: str,
    attrs: dict = None,
) -> None:
    try:
        if attrs is None:
            get_via_http_gate(cid=cid, oid=oid, endpoint=endpoint, request_path=http_request_path)
        else:
            get_via_http_gate_by_attribute(
                cid=cid, attribute=attrs, endpoint=endpoint, request_path=http_request_path
            )
        raise AssertionError(f"Expected error on getting object with cid: {cid}")
    except Exception as err:
        match = error_pattern.casefold() in str(err).casefold()
        assert match, f"Expected {err} to match {error_pattern}"
