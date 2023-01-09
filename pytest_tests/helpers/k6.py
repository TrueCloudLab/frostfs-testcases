import re
from contextlib import contextmanager
from dataclasses import dataclass
from time import sleep
from typing import Optional

import allure
from frostfs_testlib.shell import Shell
from remote_process import RemoteProcess

EXIT_RESULT_CODE = 0
LOAD_RESULTS_PATTERNS = {
    "grpc": {
        "write_ops": r"frostfs_obj_put_total\W*\d*\W*(?P<write_ops>\d*\.\d*)",
        "read_ops": r"frostfs_obj_get_total\W*\d*\W*(?P<read_ops>\d*\.\d*)",
    },
    "s3": {
        "write_ops": r"aws_obj_put_total\W*\d*\W*(?P<write_ops>\d*\.\d*)",
        "read_ops": r"aws_obj_get_total\W*\d*\W*(?P<write_ops>\d*\.\d*)",
    },
    "http": {"total_ops": r"http_reqs\W*\d*\W*(?P<total_ops>\d*\.\d*)"},
}


@dataclass
class LoadParams:
    load_type: str
    endpoint: str
    writers: Optional[int] = None
    readers: Optional[int] = None
    deleters: Optional[int] = None
    clients: Optional[int] = None
    containers_count: Optional[int] = None
    out_file: Optional[str] = None
    load_time: Optional[int] = None
    obj_count: Optional[int] = None
    obj_size: Optional[int] = None
    registry_file: Optional[str] = None


@dataclass
class LoadResults:
    data_sent: float = 0.0
    data_received: float = 0.0
    read_ops: float = 0.0
    write_ops: float = 0.0
    total_ops: float = 0.0


class K6:
    def __init__(self, load_params: LoadParams, shell: Shell):

        self.load_params = load_params
        self.shell = shell

        self._k6_dir = None
        self._k6_result = None

        self._k6_process = None
        self._k6_stop_attempts = 5
        self._k6_stop_timeout = 15

    @property
    def process_dir(self) -> str:
        return self._k6_process.process_dir

    @property
    def k6_dir(self) -> str:
        if not self._k6_dir:
            self._k6_dir = self.shell.exec(
                r"sudo find . -name 'k6' -exec dirname {} \; -quit"
            ).stdout.strip("\n")
        return self._k6_dir

    @allure.step("Prepare containers and objects")
    def prepare(self) -> str:
        self._k6_dir = self.k6_dir
        if self.load_params.load_type == "http" or self.load_params.load_type == "grpc":
            command = (
                f"{self.k6_dir}/scenarios/preset/preset_grpc.py "
                f"--size {self.load_params.obj_size}  "
                f"--containers {self.load_params.containers_count} "
                f"--out {self.k6_dir}/{self.load_params.load_type}_{self.load_params.out_file} "
                f"--endpoint {self.load_params.endpoint.split(',')[0]} "
                f"--preload_obj {self.load_params.obj_count} "
            )
            terminal = self.shell.exec(command)
            return terminal.stdout.strip("\n")
        elif self.load_params.load_type == "s3":
            command = (
                f"{self.k6_dir}/scenarios/preset/preset_s3.py --size {self.load_params.obj_size} "
                f"--buckets {self.load_params.containers_count} "
                f"--out {self.k6_dir}/{self.load_params.load_type}_{self.load_params.out_file} "
                f"--endpoint {self.load_params.endpoint.split(',')[0]} "
                f"--preload_obj {self.load_params.obj_count} "
                f"--location load-1-1"
            )
            terminal = self.shell.exec(command)
            return terminal.stdout.strip("\n")
        else:
            raise AssertionError("Wrong K6 load type")

    @allure.step("Generate K6 command")
    def _generate_env_variables(self, load_params: LoadParams, k6_dir: str) -> str:
        env_vars = {
            "DURATION": load_params.load_time or None,
            "WRITE_OBJ_SIZE": load_params.obj_size or None,
            "WRITERS": load_params.writers or 0,
            "READERS": load_params.readers or 0,
            "DELETERS": load_params.deleters or 0,
            "REGISTRY_FILE": load_params.registry_file or None,
            "CLIENTS": load_params.clients or None,
            f"{self.load_params.load_type.upper()}_ENDPOINTS": self.load_params.endpoint,
            "PREGEN_JSON": f"{self.k6_dir}/{self.load_params.load_type}_{self.load_params.out_file}"
            if load_params.out_file
            else None,
        }
        allure.attach(
            "\n".join(f"{param}: {value}" for param, value in env_vars.items()),
            "K6 ENV variables",
            allure.attachment_type.TEXT,
        )
        return " ".join(
            [f"-e {param}={value}" for param, value in env_vars.items() if value is not None]
        )

    @allure.step("Start K6 on initiator")
    def start(self) -> None:

        self._k6_dir = self.k6_dir
        command = (
            f"{self.k6_dir}/k6 run {self._generate_env_variables(self.load_params, self.k6_dir)} "
            f"{self.k6_dir}/scenarios/{self.load_params.load_type}.js"
        )
        self._k6_process = RemoteProcess.create(command, self.shell)

    @allure.step("Wait until K6 is finished")
    def wait_until_finished(self, timeout: int = 0, k6_should_be_running: bool = False) -> None:
        if self._k6_process is None:
            assert "No k6 instances were executed"
        if k6_should_be_running:
            assert self._k6_process.running(), "k6 should be running."
        for __attempt in reversed(range(5)) if timeout else [0]:
            if not self._k6_process.running():
                return
            if __attempt:  # no sleep in last iteration
                sleep(int(timeout / 5))
        self._stop_k6()
        raise TimeoutError(f"Expected K6 finished in {timeout} sec.")

    @contextmanager
    def start_context(
        self, warm_up_time: int = 0, expected_finish: bool = False, expected_fail: bool = False
    ) -> None:
        self.start()
        sleep(warm_up_time)
        try:
            yield self
        except Exception as err:
            if self._k6_process.running():
                self._kill_k6()
            raise

        if expected_fail:
            self._kill_k6()
        elif expected_finish:
            if self._k6_process.running():
                self._kill_k6()
                raise AssertionError("K6 has not finished in expected time")
            else:
                self._k6_should_be_finished()
        else:
            self._stop_k6()

    @allure.step("Get K6 results")
    def get_k6_results(self) -> None:
        self.__log_k6_output()

    @allure.step("Assert K6 should be finished")
    def _k6_should_be_finished(self) -> None:
        k6_rc = self._k6_process.rc()
        assert k6_rc == 0, f"K6 unexpectedly finished with RC {k6_rc}"

    @allure.step("Terminate K6 on initiator")
    def stop(self) -> None:
        if not self._k6_process.running():
            raise AssertionError("K6 unexpectedly finished")

        self._stop_k6()

        k6_rc = self._k6_process.rc()
        assert k6_rc == EXIT_RESULT_CODE, f"Return code of K6 job should be 0, but {k6_rc}"

    def check_k6_is_running(self) -> bool:
        if self._k6_process:
            return self._k6_process.running()
        return False

    @property
    def is_finished(self) -> bool:
        return not self._k6_process.running()

    def parsing_results(self) -> LoadResults:
        output = self._k6_process.stdout(full=True).replace("\n", "")
        metric_regex_map = {
            "data_received": r"data_received\W*\d*.\d*.\w*\W*(?P<data_received>\d*)",
            "data_sent": r"data_sent\W*\d*.\d*.\w*\W*(?P<data_sent>\d*)",
        }
        metric_regex_map.update(LOAD_RESULTS_PATTERNS[self.load_params.load_type])
        metric_values = {}
        for metric_name, metric_regex in metric_regex_map.items():
            match = re.search(metric_regex, output)
            if match:
                metric_values[metric_name] = float(match.group(metric_name))
                continue
            metric_values[metric_name] = 0.0
        load_result = LoadResults(**metric_values)
        return load_result

    @allure.step("Try to stop K6 with SIGTERM")
    def _stop_k6(self) -> None:
        for __attempt in range(self._k6_stop_attempts):
            if not self._k6_process.running():
                break

            self._k6_process.stop()
            sleep(self._k6_stop_timeout)
        else:
            raise AssertionError("Can not stop K6 process within timeout")

    def _kill_k6(self) -> None:
        self._k6_process.kill()

    @allure.step("Log K6 output")
    def __log_k6_output(self) -> None:
        allure.attach(self._k6_process.stdout(full=True), "K6 output", allure.attachment_type.TEXT)
