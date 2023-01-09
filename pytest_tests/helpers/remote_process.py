from __future__ import annotations

import uuid
from typing import Optional

import allure
from frostfs_testlib.shell import Shell
from frostfs_testlib.shell.interfaces import CommandOptions
from tenacity import retry, stop_after_attempt, wait_fixed


class RemoteProcess:
    def __init__(self, cmd: str, process_dir: str, shell: Shell):
        self.process_dir = process_dir
        self.cmd = cmd
        self.stdout_last_line_number = 0
        self.stderr_last_line_number = 0
        self.pid: Optional[str] = None
        self.proc_rc: Optional[int] = None
        self.saved_stdout: Optional[str] = None
        self.saved_stderr: Optional[str] = None
        self.shell = shell

    @classmethod
    @allure.step("Create remote process")
    def create(cls, command: str, shell: Shell) -> RemoteProcess:
        """
        Create a process on a remote host.

        Created dir for process with following files:
            command.sh: script to execute
            pid: contains process id
            rc: contains script return code
            stderr: contains script errors
            stdout: contains script output

        Args:
            shell: Shell instance
            command: command to be run on a remote host

        Returns:
            RemoteProcess instance for further examination
        """
        remote_process = cls(cmd=command, process_dir=f"/tmp/proc_{uuid.uuid4()}", shell=shell)
        remote_process._create_process_dir()
        remote_process._generate_command_script(command)
        remote_process._start_process()
        remote_process.pid = remote_process._get_pid()
        return remote_process

    @allure.step("Get process stdout")
    def stdout(self, full: bool = False) -> str:
        """
        Method to get process stdout, either fresh info or full.

        Args:
            full: returns full stdout that we have to this moment

        Returns:
            Fresh stdout. By means of stdout_last_line_number only new stdout lines are returned.
            If process is finished (proc_rc is not None) saved stdout is returned
        """
        if self.saved_stdout is not None:
            cur_stdout = self.saved_stdout
        else:
            terminal = self.shell.exec(f"cat {self.process_dir}/stdout")
            if self.proc_rc is not None:
                self.saved_stdout = terminal.stdout
            cur_stdout = terminal.stdout

        if full:
            return cur_stdout
        whole_stdout = cur_stdout.split("\n")
        if len(whole_stdout) > self.stdout_last_line_number:
            resulted_stdout = "\n".join(whole_stdout[self.stdout_last_line_number :])
            self.stdout_last_line_number = len(whole_stdout)
            return resulted_stdout
        return ""

    @allure.step("Get process stderr")
    def stderr(self, full: bool = False) -> str:
        """
        Method to get process stderr, either fresh info or full.

        Args:
            full: returns full stderr that we have to this moment

        Returns:
            Fresh stderr. By means of stderr_last_line_number only new stderr lines are returned.
            If process is finished (proc_rc is not None) saved stderr is returned
        """
        if self.saved_stderr is not None:
            cur_stderr = self.saved_stderr
        else:
            terminal = self.shell.exec(f"cat {self.process_dir}/stderr")
            if self.proc_rc is not None:
                self.saved_stderr = terminal.stdout
            cur_stderr = terminal.stdout
        if full:
            return cur_stderr
        whole_stderr = cur_stderr.split("\n")
        if len(whole_stderr) > self.stderr_last_line_number:
            resulted_stderr = "\n".join(whole_stderr[self.stderr_last_line_number :])
            self.stderr_last_line_number = len(whole_stderr)
            return resulted_stderr
        return ""

    @allure.step("Get process rc")
    def rc(self) -> Optional[int]:
        if self.proc_rc is not None:
            return self.proc_rc

        terminal = self.shell.exec(f"cat {self.process_dir}/rc", CommandOptions(check=False))
        if "No such file or directory" in terminal.stderr:
            return None
        elif terminal.stderr or terminal.return_code != 0:
            raise AssertionError(f"cat process rc was not successfull: {terminal.stderr}")

        self.proc_rc = int(terminal.stdout)
        return self.proc_rc

    @allure.step("Check if process is running")
    def running(self) -> bool:
        return self.rc() is None

    @allure.step("Send signal to process")
    def send_signal(self, signal: int) -> None:
        kill_res = self.shell.exec(f"kill -{signal} {self.pid}", CommandOptions(check=False))
        if "No such process" in kill_res.stderr:
            return
        if kill_res.return_code:
            raise AssertionError(
                f"Signal {signal} not sent. Return code of kill: {kill_res.return_code}"
            )

    @allure.step("Stop process")
    def stop(self) -> None:
        self.send_signal(15)

    @allure.step("Kill process")
    def kill(self) -> None:
        self.send_signal(9)

    @allure.step("Clear process directory")
    def clear(self) -> None:
        if self.process_dir == "/":
            raise AssertionError(f"Invalid path to delete: {self.process_dir}")
        self.shell.exec(f"rm -rf {self.process_dir}")

    @allure.step("Start remote process")
    def _start_process(self) -> None:
        self.shell.exec(
            f"nohup {self.process_dir}/command.sh </dev/null "
            f">{self.process_dir}/stdout "
            f"2>{self.process_dir}/stderr &"
        )

    @allure.step("Create process directory")
    def _create_process_dir(self) -> None:
        self.shell.exec(f"mkdir {self.process_dir}; chmod 777 {self.process_dir}")
        terminal = self.shell.exec(f"realpath {self.process_dir}")
        self.process_dir = terminal.stdout.strip()

    @allure.step("Get pid")
    @retry(wait=wait_fixed(10), stop=stop_after_attempt(5), reraise=True)
    def _get_pid(self) -> str:
        terminal = self.shell.exec(f"cat {self.process_dir}/pid")
        assert terminal.stdout, f"invalid pid: {terminal.stdout}"
        return terminal.stdout.strip()

    @allure.step("Generate command script")
    def _generate_command_script(self, command: str) -> None:
        command = command.replace('"', '\\"').replace("\\", "\\\\")
        script = (
            f"#!/bin/bash\n"
            f"cd {self.process_dir}\n"
            f"{command} &\n"
            f"pid=\$!\n"
            f"cd {self.process_dir}\n"
            f"echo \$pid > {self.process_dir}/pid\n"
            f"wait \$pid\n"
            f"echo $? > {self.process_dir}/rc"
        )

        self.shell.exec(f'echo "{script}" > {self.process_dir}/command.sh')
        self.shell.exec(f"cat {self.process_dir}/command.sh")
        self.shell.exec(f"chmod +x {self.process_dir}/command.sh")
