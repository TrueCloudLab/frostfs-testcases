import logging
from http import HTTPStatus
from re import match

import allure
import pytest
import requests
from binary_version_helper import get_remote_binaries_versions
from common import BIN_VERSIONS_FILE
from env_properties import read_env_properties, save_env_properties
from frostfs_testlib.hosting import Hosting

logger = logging.getLogger("NeoLogger")


@allure.title("Check binaries versions")
@pytest.mark.sanity
@pytest.mark.check_binaries
@pytest.mark.skip("Skipped due to https://j.yadro.com/browse/OBJECT-628")
def test_binaries_versions(request, hosting: Hosting):
    """
    Compare binaries versions from external source (url) and deployed on servers.
    """
    if not BIN_VERSIONS_FILE:
        pytest.skip("File with binaries and versions was not provided")

    binaries_to_check = download_versions_info(BIN_VERSIONS_FILE)
    with allure.step("Get binaries versions from servers"):
        got_versions = get_remote_binaries_versions(hosting)

    env_properties = read_env_properties(request.config)

    # compare versions from servers and file
    failed_versions = {}
    additional_env_properties = {}
    for binary, version in binaries_to_check.items():
        actual_version = got_versions.get(binary)
        if actual_version != version:
            failed_versions[binary] = f"Expected version {version}, found version {actual_version}"

        # If some binary was not listed in the env properties file, let's add it
        # so that we have full information about versions in allure report
        if env_properties and binary not in env_properties:
            additional_env_properties[binary] = actual_version

    if env_properties and additional_env_properties:
        save_env_properties(request.config, additional_env_properties)

    # create clear beautiful error with aggregation info
    if failed_versions:
        msg = "\n".join({f"{binary}: {error}" for binary, error in failed_versions.items()})
        raise AssertionError(f"Found binaries with unexpected versions:\n{msg}")


@allure.step("Download versions info from {url}")
def download_versions_info(url: str) -> dict:
    binaries_to_version = {}

    response = requests.get(url)

    assert (
        response.status_code == HTTPStatus.OK
    ), f"Got {response.status_code} code. Content {response.json()}"

    content = response.text
    assert content, f"Expected file with content, got {response}"

    for line in content.split("\n"):
        m = match("(.*)=(.*)", line)
        if not m:
            logger.warning(f"Could not get binary/version from {line}")
            continue
        bin_name, bin_version = m.group(1), m.group(2)
        binaries_to_version[bin_name] = bin_version

    return binaries_to_version
