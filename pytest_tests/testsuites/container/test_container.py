import json

import allure
import pytest
from epoch import tick_epoch
from python_keywords.container import (
    create_container,
    delete_container,
    get_container,
    list_containers,
    wait_for_container_creation,
    wait_for_container_deletion,
)
from utility import placement_policy_from_container
from wellknown_acl import PRIVATE_ACL_F

from steps.cluster_test_base import ClusterTestBase


@pytest.mark.container
@pytest.mark.sanity
@pytest.mark.container
class TestContainer(ClusterTestBase):
    @pytest.mark.parametrize("name", ["", "test-container"], ids=["No name", "Set particular name"])
    @pytest.mark.smoke
    def test_container_creation(self, default_wallet, name):
        scenario_title = f"with name {name}" if name else "without name"
        allure.dynamic.title(f"User can create container {scenario_title}")

        wallet = default_wallet
        with open(wallet) as file:
            json_wallet = json.load(file)

        placement_rule = "REP 2 IN X CBF 1 SELECT 2 FROM * AS X"
        cid = create_container(
            wallet,
            rule=placement_rule,
            name=name,
            shell=self.shell,
            endpoint=self.cluster.default_rpc_endpoint,
        )

        containers = list_containers(
            wallet, shell=self.shell, endpoint=self.cluster.default_rpc_endpoint
        )
        assert cid in containers, f"Expected container {cid} in containers: {containers}"

        container_info: str = get_container(
            wallet,
            cid,
            json_mode=False,
            shell=self.shell,
            endpoint=self.cluster.default_rpc_endpoint,
        )
        container_info = (
            container_info.casefold()
        )  # To ignore case when comparing with expected values

        info_to_check = {
            f"basic ACL: {PRIVATE_ACL_F} (private)",
            f"owner ID: {json_wallet.get('accounts')[0].get('address')}",
            f"container ID: {cid}",
        }
        if name:
            info_to_check.add(f"Name={name}")

        with allure.step("Check container has correct information"):
            expected_policy = placement_rule.casefold()
            actual_policy = placement_policy_from_container(container_info)
            assert (
                actual_policy == expected_policy
            ), f"Expected policy\n{expected_policy} but got policy\n{actual_policy}"

            for info in info_to_check:
                expected_info = info.casefold()
                assert (
                    expected_info in container_info
                ), f"Expected {expected_info} in container info:\n{container_info}"

        with allure.step("Delete container and check it was deleted"):
            delete_container(
                wallet, cid, shell=self.shell, endpoint=self.cluster.default_rpc_endpoint
            )
            self.tick_epoch()
            wait_for_container_deletion(
                wallet, cid, shell=self.shell, endpoint=self.cluster.default_rpc_endpoint
            )

    @allure.title("Parallel container creation and deletion")
    def test_container_creation_deletion_parallel(self, default_wallet):
        containers_count = 3
        wallet = default_wallet
        placement_rule = "REP 2 IN X CBF 1 SELECT 2 FROM * AS X"

        cids: list[str] = []
        with allure.step(f"Create {containers_count} containers"):
            for _ in range(containers_count):
                cids.append(
                    create_container(
                        wallet,
                        rule=placement_rule,
                        await_mode=False,
                        shell=self.shell,
                        endpoint=self.cluster.default_rpc_endpoint,
                        wait_for_creation=False,
                    )
                )

        with allure.step(f"Wait for containers occur in container list"):
            for cid in cids:
                wait_for_container_creation(
                    wallet,
                    cid,
                    sleep_interval=containers_count,
                    shell=self.shell,
                    endpoint=self.cluster.default_rpc_endpoint,
                )

        with allure.step("Delete containers and check they were deleted"):
            for cid in cids:
                delete_container(
                    wallet, cid, shell=self.shell, endpoint=self.cluster.default_rpc_endpoint
                )
            self.tick_epoch()
            wait_for_container_deletion(
                wallet, cid, shell=self.shell, endpoint=self.cluster.default_rpc_endpoint
            )
