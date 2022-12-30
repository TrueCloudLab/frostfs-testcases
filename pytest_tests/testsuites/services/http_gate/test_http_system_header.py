import calendar
import datetime
import logging
from typing import Optional

import allure
import pytest
from container import create_container
from epoch import get_epoch
from file_helper import generate_file
from http_gate import (
    attr_into_str_header_curl,
    get_object_and_verify_hashes,
    try_to_get_object_and_expect_error,
    upload_via_http_gate_curl,
)
from python_keywords.neofs_verbs import get_netmap_netinfo, head_object
from wellknown_acl import PUBLIC_ACL

from steps.cluster_test_base import ClusterTestBase

logger = logging.getLogger("NeoLogger")
EXPIRATION_TIMESTAMP_HEADER = "__NEOFS__EXPIRATION_TIMESTAMP"
EXPIRATION_EPOCH_HEADER = "__NEOFS__EXPIRATION_EPOCH"
EXPIRATION_DURATION_HEADER = "__NEOFS__EXPIRATION_DURATION"
EXPIRATION_EXPIRATION_RFC = "__NEOFS__EXPIRATION_RFC3339"
NEOFS_EXPIRATION_EPOCH = "Neofs-Expiration-Epoch"
NEOFS_EXPIRATION_DURATION = "Neofs-Expiration-Duration"
NEOFS_EXPIRATION_TIMESTAMP = "Neofs-Expiration-Timestamp"
NEOFS_EXIPRATION_RFC3339 = "Neofs-Expiration-RFC3339"


@pytest.mark.sanity
@pytest.mark.http_gate
class Test_http_system_header(ClusterTestBase):
    PLACEMENT_RULE = "REP 2 IN X CBF 1 SELECT 2 FROM * AS X"

    @pytest.fixture(scope="class", autouse=True)
    @allure.title("[Class/Autouse]: Prepare wallet and deposit")
    def prepare_wallet(self, default_wallet):
        Test_http_system_header.wallet = default_wallet

    @pytest.fixture(scope="class")
    @allure.title("Create container")
    def user_container(self):
        return create_container(
            wallet=self.wallet,
            shell=self.shell,
            endpoint=self.cluster.default_rpc_endpoint,
            rule=self.PLACEMENT_RULE,
            basic_acl=PUBLIC_ACL,
        )

    @pytest.fixture(scope="class")
    @allure.title("epoch_duration in seconds")
    def epoch_duration(self) -> int:
        net_info = get_netmap_netinfo(
            wallet=self.wallet,
            endpoint=self.cluster.default_rpc_endpoint,
            shell=self.shell,
        )
        epoch_duration_in_blocks = net_info["epoch_duration"]
        time_per_block = net_info["time_per_block"]
        return int(epoch_duration_in_blocks * time_per_block)

    @allure.title("Return N-epoch count in minutes")
    def epoch_count_into_mins(self, epoch_duration: int, epoch: int) -> str:
        mins = epoch_duration * epoch / 60
        return f"{mins}m"

    @allure.title("Return future timestamp after N epochs are passed")
    def epoch_count_into_timestamp(
        self, epoch_duration: int, epoch: int, rfc3339: Optional[bool] = False
    ) -> str:
        current_datetime = datetime.datetime.utcnow()
        epoch_count_in_seconds = epoch_duration * epoch
        future_datetime = current_datetime + datetime.timedelta(seconds=epoch_count_in_seconds)
        if rfc3339:
            return future_datetime.isoformat("T") + "Z"
        else:
            return str(calendar.timegm(future_datetime.timetuple()))

    @allure.title("Check is  (header_output) Key=Value exists and equal in passed (header_to_find)")
    def check_key_value_presented_header(self, header_output: dict, header_to_find: dict) -> bool:
        header_att = header_output["header"]["attributes"]
        for key_to_check, val_to_check in header_to_find.items():
            if key_to_check not in header_att or val_to_check != header_att[key_to_check]:
                logger.info(f"Unable to find {key_to_check}: '{val_to_check}' in {header_att}")
                return False
        return True

    @allure.title(
        f"Validate that only {EXPIRATION_EPOCH_HEADER} exists in header and other headers are abesent"
    )
    def validation_for_http_header_attr(self, head_info: dict, expected_epoch: int) -> None:
        # check that __NEOFS__EXPIRATION_EPOCH attribute has corresponding epoch
        assert self.check_key_value_presented_header(
            head_info, {EXPIRATION_EPOCH_HEADER: str(expected_epoch)}
        ), f'Expected to find {EXPIRATION_EPOCH_HEADER}: {expected_epoch} in: {head_info["header"]["attributes"]}'
        # check that {EXPIRATION_EPOCH_HEADER} absents in header output
        assert not (
            self.check_key_value_presented_header(head_info, {EXPIRATION_DURATION_HEADER: ""})
        ), f"Only {EXPIRATION_EPOCH_HEADER} can be displayed in header attributes"
        # check that {EXPIRATION_TIMESTAMP_HEADER} absents in header output
        assert not (
            self.check_key_value_presented_header(head_info, {EXPIRATION_TIMESTAMP_HEADER: ""})
        ), f"Only {EXPIRATION_TIMESTAMP_HEADER} can be displayed in header attributes"
        # check that {EXPIRATION_EXPIRATION_RFC} absents in header output
        assert not (
            self.check_key_value_presented_header(head_info, {EXPIRATION_EXPIRATION_RFC: ""})
        ), f"Only {EXPIRATION_EXPIRATION_RFC} can be displayed in header attributes"

    @allure.title("Put / get / verify object and return head command result to invoker")
    def oid_header_info_for_object(self, file_path: str, attributes: dict, user_container: str):
        oid = upload_via_http_gate_curl(
            cid=user_container,
            filepath=file_path,
            endpoint=self.cluster.default_http_gate_endpoint,
            headers=attr_into_str_header_curl(attributes),
        )
        get_object_and_verify_hashes(
            oid=oid,
            file_name=file_path,
            wallet=self.wallet,
            cid=user_container,
            shell=self.shell,
            nodes=self.cluster.storage_nodes,
            endpoint=self.cluster.default_http_gate_endpoint,
        )
        head = head_object(
            wallet=self.wallet,
            cid=user_container,
            oid=oid,
            shell=self.shell,
            endpoint=self.cluster.default_rpc_endpoint,
        )
        return oid, head

    @allure.title("[negative] attempt to put object with expired epoch")
    def test_unable_put_expired_epoch(self, user_container: str, simple_object_size: int):
        headers = attr_into_str_header_curl(
            {"Neofs-Expiration-Epoch": str(get_epoch(self.shell, self.cluster) - 1)}
        )
        file_path = generate_file(simple_object_size)
        with allure.step(
            "Put object using HTTP with attribute Expiration-Epoch where epoch is expired"
        ):
            upload_via_http_gate_curl(
                cid=user_container,
                filepath=file_path,
                endpoint=self.cluster.default_http_gate_endpoint,
                headers=headers,
                error_pattern="object has expired",
            )

    @allure.title("[negative] attempt to put object with negative Neofs-Expiration-Duration")
    def test_unable_put_negative_duration(self, user_container: str, simple_object_size: int):
        headers = attr_into_str_header_curl({"Neofs-Expiration-Duration": "-1h"})
        file_path = generate_file(simple_object_size)
        with allure.step(
            "Put object using HTTP with attribute Neofs-Expiration-Duration where duration is negative"
        ):
            upload_via_http_gate_curl(
                cid=user_container,
                filepath=file_path,
                endpoint=self.cluster.default_http_gate_endpoint,
                headers=headers,
                error_pattern=f"{EXPIRATION_DURATION_HEADER} must be positive",
            )

    @allure.title(
        "[negative] attempt to put object with Neofs-Expiration-Timestamp value in the past"
    )
    def test_unable_put_expired_timestamp(self, user_container: str, simple_object_size: int):
        headers = attr_into_str_header_curl({"Neofs-Expiration-Timestamp": "1635075727"})
        file_path = generate_file(simple_object_size)
        with allure.step(
            "Put object using HTTP with attribute Neofs-Expiration-Timestamp where duration is in the past"
        ):
            upload_via_http_gate_curl(
                cid=user_container,
                filepath=file_path,
                endpoint=self.cluster.default_http_gate_endpoint,
                headers=headers,
                error_pattern=f"{EXPIRATION_TIMESTAMP_HEADER} must be in the future",
            )

    @allure.title(
        "[negative] Put object using HTTP with attribute Neofs-Expiration-RFC3339 where duration is in the past"
    )
    def test_unable_put_expired_rfc(self, user_container: str, simple_object_size: int):
        headers = attr_into_str_header_curl({"Neofs-Expiration-RFC3339": "2021-11-22T09:55:49Z"})
        file_path = generate_file(simple_object_size)
        upload_via_http_gate_curl(
            cid=user_container,
            filepath=file_path,
            endpoint=self.cluster.default_http_gate_endpoint,
            headers=headers,
            error_pattern=f"{EXPIRATION_EXPIRATION_RFC} must be in the future",
        )

    @allure.title("priority of attributes epoch>duration")
    @pytest.mark.parametrize(
        "object_size",
        [pytest.lazy_fixture("simple_object_size"), pytest.lazy_fixture("complex_object_size")],
        ids=["simple object", "complex object"],
    )
    def test_http_attr_priority_epoch_duration(
        self, user_container: str, object_size: int, epoch_duration: int
    ):
        self.tick_epoch()
        epoch_count = 1
        expected_epoch = get_epoch(self.shell, self.cluster) + epoch_count
        logger.info(
            f"epoch duration={epoch_duration}, current_epoch= {get_epoch(self.shell, self.cluster)} expected_epoch {expected_epoch}"
        )
        attributes = {NEOFS_EXPIRATION_EPOCH: expected_epoch, NEOFS_EXPIRATION_DURATION: "1m"}
        file_path = generate_file(object_size)
        with allure.step(
            f"Put objects using HTTP with attributes and head command should display {EXPIRATION_EPOCH_HEADER}: {expected_epoch} attr"
        ):
            oid, head_info = self.oid_header_info_for_object(
                file_path=file_path, attributes=attributes, user_container=user_container
            )
            self.validation_for_http_header_attr(head_info=head_info, expected_epoch=expected_epoch)
        with allure.step("Check that object becomes unavailable when epoch is expired"):
            for _ in range(0, epoch_count + 1):
                self.tick_epoch()
            assert (
                get_epoch(self.shell, self.cluster) == expected_epoch + 1
            ), f"Epochs should be equal: {get_epoch(self.shell, self.cluster)} != {expected_epoch + 1}"

            try_to_get_object_and_expect_error(
                cid=user_container,
                oid=oid,
                error_pattern="404 Not Found",
                endpoint=self.cluster.default_http_gate_endpoint,
            )

    @allure.title(
        f"priority of attributes duration>timestamp, duration time has higher priority and should be converted {EXPIRATION_EPOCH_HEADER}"
    )
    @pytest.mark.parametrize(
        "object_size",
        [pytest.lazy_fixture("simple_object_size"), pytest.lazy_fixture("complex_object_size")],
        ids=["simple object", "complex object"],
    )
    def test_http_attr_priority_dur_timestamp(
        self, user_container: str, object_size: int, epoch_duration: int
    ):
        self.tick_epoch()
        epoch_count = 2
        expected_epoch = get_epoch(self.shell, self.cluster) + epoch_count
        logger.info(
            f"epoch duration={epoch_duration}, current_epoch= {get_epoch(self.shell, self.cluster)} expected_epoch {expected_epoch}"
        )
        attributes = {
            NEOFS_EXPIRATION_DURATION: self.epoch_count_into_mins(
                epoch_duration=epoch_duration, epoch=2
            ),
            NEOFS_EXPIRATION_TIMESTAMP: self.epoch_count_into_timestamp(
                epoch_duration=epoch_duration, epoch=1
            ),
        }
        file_path = generate_file(object_size)
        with allure.step(
            f"Put objects using HTTP with attributes and head command should display {EXPIRATION_EPOCH_HEADER}: {expected_epoch} attr"
        ):
            oid, head_info = self.oid_header_info_for_object(
                file_path=file_path, attributes=attributes, user_container=user_container
            )
            self.validation_for_http_header_attr(head_info=head_info, expected_epoch=expected_epoch)
        with allure.step("Check that object becomes unavailable when epoch is expired"):
            for _ in range(0, epoch_count + 1):
                self.tick_epoch()
            assert (
                get_epoch(self.shell, self.cluster) == expected_epoch + 1
            ), f"Epochs should be equal: {get_epoch(self.shell, self.cluster)} != {expected_epoch + 1}"

            try_to_get_object_and_expect_error(
                cid=user_container,
                oid=oid,
                error_pattern="404 Not Found",
                endpoint=self.cluster.default_http_gate_endpoint,
            )

    @allure.title(
        f"priority of attributes timestamp>Expiration-RFC, timestamp has higher priority and should be converted {EXPIRATION_EPOCH_HEADER}"
    )
    @pytest.mark.parametrize(
        "object_size",
        [pytest.lazy_fixture("simple_object_size"), pytest.lazy_fixture("complex_object_size")],
        ids=["simple object", "complex object"],
    )
    def test_http_attr_priority_timestamp_rfc(
        self, user_container: str, object_size: int, epoch_duration: int
    ):
        self.tick_epoch()
        epoch_count = 2
        expected_epoch = get_epoch(self.shell, self.cluster) + epoch_count
        logger.info(
            f"epoch duration={epoch_duration}, current_epoch= {get_epoch(self.shell, self.cluster)} expected_epoch {expected_epoch}"
        )
        attributes = {
            NEOFS_EXPIRATION_TIMESTAMP: self.epoch_count_into_timestamp(
                epoch_duration=epoch_duration, epoch=2
            ),
            NEOFS_EXIPRATION_RFC3339: self.epoch_count_into_timestamp(
                epoch_duration=epoch_duration, epoch=1, rfc3339=True
            ),
        }
        file_path = generate_file(object_size)
        with allure.step(
            f"Put objects using HTTP with attributes and head command should display {EXPIRATION_EPOCH_HEADER}: {expected_epoch} attr"
        ):
            oid, head_info = self.oid_header_info_for_object(
                file_path=file_path, attributes=attributes, user_container=user_container
            )
            self.validation_for_http_header_attr(head_info=head_info, expected_epoch=expected_epoch)
        with allure.step("Check that object becomes unavailable when epoch is expired"):
            for _ in range(0, epoch_count + 1):
                self.tick_epoch()
            assert (
                get_epoch(self.shell, self.cluster) == expected_epoch + 1
            ), f"Epochs should be equal: {get_epoch(self.shell, self.cluster)} != {expected_epoch + 1}"

            try_to_get_object_and_expect_error(
                cid=user_container,
                oid=oid,
                error_pattern="404 Not Found",
                endpoint=self.cluster.default_http_gate_endpoint,
            )

    @allure.title("Test that object is automatically delete when expiration passed")
    @pytest.mark.parametrize(
        "object_size",
        [pytest.lazy_fixture("simple_object_size"), pytest.lazy_fixture("complex_object_size")],
        ids=["simple object", "complex object"],
    )
    def test_http_rfc_object_unavailable_after_expir(
        self, user_container: str, object_size: int, epoch_duration: int
    ):
        self.tick_epoch()
        epoch_count = 2
        expected_epoch = get_epoch(self.shell, self.cluster) + epoch_count
        logger.info(
            f"epoch duration={epoch_duration}, current_epoch= {get_epoch(self.shell, self.cluster)} expected_epoch {expected_epoch}"
        )
        attributes = {
            NEOFS_EXIPRATION_RFC3339: self.epoch_count_into_timestamp(
                epoch_duration=epoch_duration, epoch=2, rfc3339=True
            )
        }
        file_path = generate_file(object_size)
        with allure.step(
            f"Put objects using HTTP with attributes and head command should display {EXPIRATION_EPOCH_HEADER}: {expected_epoch} attr"
        ):
            oid, head_info = self.oid_header_info_for_object(
                file_path=file_path,
                attributes=attributes,
                user_container=user_container,
            )
            self.validation_for_http_header_attr(head_info=head_info, expected_epoch=expected_epoch)
        with allure.step("Check that object becomes unavailable when epoch is expired"):
            for _ in range(0, epoch_count + 1):
                self.tick_epoch()
            # check that {EXPIRATION_EXPIRATION_RFC} absents in header output
            assert (
                get_epoch(self.shell, self.cluster) == expected_epoch + 1
            ), f"Epochs should be equal: {get_epoch(self.shell, self.cluster)} != {expected_epoch + 1}"
            try_to_get_object_and_expect_error(
                cid=user_container,
                oid=oid,
                error_pattern="404 Not Found",
                endpoint=self.cluster.default_http_gate_endpoint,
            )
