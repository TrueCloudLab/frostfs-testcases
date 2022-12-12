import concurrent.futures
import re
from dataclasses import asdict

import allure
from common import STORAGE_NODE_SERVICE_NAME_REGEX
from k6 import K6, LoadParams, LoadResults
from neofs_testlib.cli.neofs_authmate import NeofsAuthmate
from neofs_testlib.cli.neogo import NeoGo
from neofs_testlib.hosting import Hosting
from neofs_testlib.shell import CommandOptions, SSHShell
from neofs_testlib.shell.interfaces import InteractiveInput

NEOFS_AUTHMATE_PATH = "neofs-s3-authmate"
STOPPED_HOSTS = []


@allure.title("Get services endpoints")
def get_services_endpoints(
    hosting: Hosting, service_name_regex: str, endpoint_attribute: str
) -> list[str]:
    service_configs = hosting.find_service_configs(service_name_regex)
    return [service_config.attributes[endpoint_attribute] for service_config in service_configs]


@allure.title("Stop nodes")
def stop_unused_nodes(storage_nodes: list, used_nodes_count: int):
    for node in storage_nodes[used_nodes_count:]:
        host = node.host
        STOPPED_HOSTS.append(host)
        host.stop_host("hard")


@allure.title("Start nodes")
def start_stopped_nodes():
    for host in STOPPED_HOSTS:
        host.start_host()
        STOPPED_HOSTS.remove(host)


@allure.title("Init s3 client")
def init_s3_client(
    load_nodes: list, login: str, pkey: str, container_placement_policy: str, hosting: Hosting
):
    service_configs = hosting.find_service_configs(STORAGE_NODE_SERVICE_NAME_REGEX)
    host = hosting.get_host_by_service(service_configs[0].name)
    wallet_path = service_configs[0].attributes["wallet_path"]
    neogo_cli_config = host.get_cli_config("neo-go")
    neogo_wallet = NeoGo(shell=host.get_shell(), neo_go_exec_path=neogo_cli_config.exec_path).wallet
    dump_keys_output = neogo_wallet.dump_keys(wallet_config=wallet_path).stdout
    public_key = str(re.search(r":\n(?P<public_key>.*)", dump_keys_output).group("public_key"))
    node_endpoint = service_configs[0].attributes["rpc_endpoint"]
    # prompt_pattern doesn't work at the moment
    for load_node in load_nodes:
        ssh_client = SSHShell(host=load_node, login=login, private_key_path=pkey)
        path = ssh_client.exec(r"sudo find . -name 'k6' -exec dirname {} \; -quit").stdout.strip(
            "\n"
        )
        neofs_authmate_exec = NeofsAuthmate(ssh_client, NEOFS_AUTHMATE_PATH)
        issue_secret_output = neofs_authmate_exec.secret.issue(
            wallet=f"{path}/scenarios/files/wallet.json",
            peer=node_endpoint,
            bearer_rules=f"{path}/scenarios/files/rules.json",
            gate_public_key=public_key,
            container_placement_policy=container_placement_policy,
            container_policy=f"{path}/scenarios/files/policy.json",
            wallet_password="",
        ).stdout
        aws_access_key_id = str(
            re.search(r"access_key_id.*:\s.(?P<aws_access_key_id>\w*)", issue_secret_output).group(
                "aws_access_key_id"
            )
        )
        aws_secret_access_key = str(
            re.search(
                r"secret_access_key.*:\s.(?P<aws_secret_access_key>\w*)", issue_secret_output
            ).group("aws_secret_access_key")
        )
        # prompt_pattern doesn't work at the moment
        configure_input = [
            InteractiveInput(prompt_pattern=r"AWS Access Key ID.*", input=aws_access_key_id),
            InteractiveInput(
                prompt_pattern=r"AWS Secret Access Key.*", input=aws_secret_access_key
            ),
            InteractiveInput(prompt_pattern=r".*", input=""),
            InteractiveInput(prompt_pattern=r".*", input=""),
        ]
        ssh_client.exec("aws configure", CommandOptions(interactive_inputs=configure_input))


@allure.title("Clear cache and data from storage nodes")
def clear_cache_and_data(hosting: Hosting):
    service_configs = hosting.find_service_configs(STORAGE_NODE_SERVICE_NAME_REGEX)
    for service_config in service_configs:
        host = hosting.get_host_by_service(service_config.name)
        host.stop_service(service_config.name)
        host.delete_storage_node_data(service_config.name)
        host.start_service(service_config.name)


@allure.title("Prepare objects")
def prepare_objects(k6_instance: K6):
    k6_instance.prepare()


@allure.title("Prepare K6 instances and objects")
def prepare_k6_instances(
    load_nodes: list, login: str, pkey: str, load_params: LoadParams, prepare: bool = True
) -> list:
    k6_load_objects = []
    for load_node in load_nodes:
        ssh_client = SSHShell(host=load_node, login=login, private_key_path=pkey)
        k6_load_object = K6(load_params, ssh_client)
        k6_load_objects.append(k6_load_object)
    for k6_load_object in k6_load_objects:
        if prepare:
            with allure.step("Prepare objects"):
                prepare_objects(k6_load_object)
    return k6_load_objects


@allure.title("Run K6")
def run_k6_load(k6_instance: K6) -> LoadResults:
    with allure.step("Executing load"):
        k6_instance.start()
        k6_instance.wait_until_finished(k6_instance.load_params.load_time * 2)
    with allure.step("Printing results"):
        k6_instance.get_k6_results()
        return k6_instance.parsing_results()


@allure.title("MultiNode K6 Run")
def multi_node_k6_run(k6_instances: list) -> dict:
    results = []
    avg_results = {}
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = []
        for k6_instance in k6_instances:
            futures.append(executor.submit(run_k6_load, k6_instance))
        for future in concurrent.futures.as_completed(futures):
            results.append(asdict(future.result()))
    for k6_result in results:
        for key in k6_result:
            try:
                avg_results[key] += k6_result[key] / len(results)
            except KeyError:
                avg_results[key] = k6_result[key] / len(results)
    return avg_results


@allure.title("Compare results")
def compare_load_results(result: dict, result_new: dict):
    for key in result:
        if result[key] != 0 and result_new[key] != 0:
            if (abs(result[key] - result_new[key]) / min(result[key], result_new[key])) < 0.25:
                continue
            else:
                raise AssertionError(f"Difference in {key} values more than 25%")
        elif result[key] == 0 and result_new[key] == 0:
            continue
        else:
            raise AssertionError(f"Unexpected zero value in {key}")
