import logging
import re

from common import FROSTFS_ADM_EXEC, FROSTFS_CLI_EXEC, WALLET_CONFIG
from frostfs_testlib.cli import FrostfsAdm, FrostfsCli
from frostfs_testlib.hosting import Hosting
from frostfs_testlib.shell import Shell

logger = logging.getLogger("NeoLogger")


def get_local_binaries_versions(shell: Shell) -> dict[str, str]:
    versions = {}

    for binary in ["neo-go", "frostfs-authmate"]:
        out = shell.exec(f"{binary} --version").stdout
        versions[binary] = _parse_version(out)

    frostfs_cli = FrostfsCli(shell, FROSTFS_CLI_EXEC, WALLET_CONFIG)
    versions["frostfs-cli"] = _parse_version(frostfs_cli.version.get().stdout)

    try:
        frostfs_adm = FrostfsAdm(shell, FROSTFS_ADM_EXEC)
        versions["frostfs-adm"] = _parse_version(frostfs_adm.version.get().stdout)
    except RuntimeError:
        logger.info(f"frostfs-adm not installed")

    out = shell.exec("aws --version").stdout
    out_lines = out.split("\n")
    versions["AWS"] = out_lines[0] if out_lines else "Unknown"

    return versions


def get_remote_binaries_versions(hosting: Hosting) -> dict[str, str]:
    versions_by_host = {}
    for host in hosting.hosts:
        binary_path_by_name = {}  # Maps binary name to executable path
        for service_config in host.config.services:
            exec_path = service_config.attributes.get("exec_path")
            if exec_path:
                binary_path_by_name[service_config.name] = exec_path
        for cli_config in host.config.clis:
            binary_path_by_name[cli_config.name] = cli_config.exec_path

        shell = host.get_shell()
        versions_at_host = {}
        for binary_name, binary_path in binary_path_by_name.items():
            try:
                result = shell.exec(f"{binary_path} --version")
                versions_at_host[binary_name] = _parse_version(result.stdout)
            except Exception as exc:
                logger.error(f"Cannot get version for {binary_path} because of\n{exc}")
                versions_at_host[binary_name] = "Unknown"
        versions_by_host[host.config.address] = versions_at_host

    # Consolidate versions across all hosts
    versions = {}
    for host, binary_versions in versions_by_host.items():
        for name, version in binary_versions.items():
            captured_version = versions.get(name)
            if captured_version:
                assert (
                    captured_version == version
                ), f"Binary {name} has inconsistent version on host {host}"
            else:
                versions[name] = version
    return versions


def _parse_version(version_output: str) -> str:
    version = re.search(r"version[:\s]*v?(.+)", version_output, re.IGNORECASE)
    return version.group(1).strip() if version else "Unknown"
