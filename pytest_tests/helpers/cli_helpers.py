#!/usr/bin/python3.9

"""
Helper functions to use with `frostfs-cli`, `neo-go` and other CLIs.
"""
import json
import logging
import subprocess
import sys
from contextlib import suppress
from datetime import datetime
from textwrap import shorten
from typing import Union

import allure
import pexpect

logger = logging.getLogger("NeoLogger")
COLOR_GREEN = "\033[92m"
COLOR_OFF = "\033[0m"


def _cmd_run(cmd: str, timeout: int = 30) -> str:
    """
    Runs given shell command <cmd>, in case of success returns its stdout,
    in case of failure returns error message.
    """
    compl_proc = None
    start_time = datetime.now()
    try:
        logger.info(f"{COLOR_GREEN}Executing command: {cmd}{COLOR_OFF}")
        start_time = datetime.utcnow()
        compl_proc = subprocess.run(
            cmd,
            check=True,
            universal_newlines=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            shell=True,
        )
        output = compl_proc.stdout
        return_code = compl_proc.returncode
        end_time = datetime.utcnow()
        logger.info(f"{COLOR_GREEN}Output: {output}{COLOR_OFF}")
        _attach_allure_log(cmd, output, return_code, start_time, end_time)

        return output
    except subprocess.CalledProcessError as exc:
        logger.info(
            f"Command: {cmd}\n" f"Error:\nreturn code: {exc.returncode} " f"\nOutput: {exc.output}"
        )
        end_time = datetime.now()
        return_code, cmd_output = subprocess.getstatusoutput(cmd)
        _attach_allure_log(cmd, cmd_output, return_code, start_time, end_time)

        raise RuntimeError(
            f"Command: {cmd}\n" f"Error:\nreturn code: {exc.returncode}\n" f"Output: {exc.output}"
        ) from exc
    except OSError as exc:
        raise RuntimeError(f"Command: {cmd}\n" f"Output: {exc.strerror}") from exc
    except Exception as exc:
        return_code, cmd_output = subprocess.getstatusoutput(cmd)
        end_time = datetime.now()
        _attach_allure_log(cmd, cmd_output, return_code, start_time, end_time)
        logger.info(
            f"Command: {cmd}\n"
            f"Error:\nreturn code: {return_code}\n"
            f"Output: {exc.output.decode('utf-8') if type(exc.output) is bytes else exc.output}"
        )
        raise


def _run_with_passwd(cmd: str) -> str:
    child = pexpect.spawn(cmd)
    child.delaybeforesend = 1
    child.expect(".*")
    child.sendline("\r")
    if sys.platform == "darwin":
        child.expect(pexpect.EOF)
        cmd = child.before
    else:
        child.wait()
        cmd = child.read()
    return cmd.decode()


def _configure_aws_cli(cmd: str, key_id: str, access_key: str, out_format: str = "json") -> str:
    child = pexpect.spawn(cmd)
    child.delaybeforesend = 1

    child.expect("AWS Access Key ID.*")
    child.sendline(key_id)

    child.expect("AWS Secret Access Key.*")
    child.sendline(access_key)

    child.expect("Default region name.*")
    child.sendline("")

    child.expect("Default output format.*")
    child.sendline(out_format)

    child.wait()
    cmd = child.read()
    # child.expect(pexpect.EOF)
    # cmd = child.before
    return cmd.decode()


def _attach_allure_log(
    cmd: str, output: str, return_code: int, start_time: datetime, end_time: datetime
) -> None:
    command_attachment = (
        f"COMMAND: '{cmd}'\n"
        f"OUTPUT:\n {output}\n"
        f"RC: {return_code}\n"
        f"Start / End / Elapsed\t {start_time.time()} / {end_time.time()} / {end_time - start_time}"
    )
    with allure.step(f'COMMAND: {shorten(cmd, width=60, placeholder="...")}'):
        allure.attach(command_attachment, "Command execution", allure.attachment_type.TEXT)


def log_command_execution(cmd: str, output: Union[str, dict]) -> None:
    logger.info(f"{cmd}: {output}")
    with suppress(Exception):
        json_output = json.dumps(output, indent=4, sort_keys=True)
        output = json_output
    command_attachment = f"COMMAND: '{cmd}'\n" f"OUTPUT:\n {output}\n"
    with allure.step(f'COMMAND: {shorten(cmd, width=60, placeholder="...")}'):
        allure.attach(command_attachment, "Command execution", allure.attachment_type.TEXT)
