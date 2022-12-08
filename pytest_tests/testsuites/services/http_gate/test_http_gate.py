import logging
import os

import allure
import pytest
from epoch import get_epoch, tick_epoch
from file_helper import generate_file, get_file_hash
from python_keywords.container import create_container
from python_keywords.http_gate import (
    attr_into_header,
    get_object_and_verify_hashes,
    get_object_by_attr_and_verify_hashes,
    get_via_http_curl,
    get_via_http_gate,
    get_via_zip_http_gate,
    try_to_get_object_and_expect_error,
    upload_via_http_gate,
    upload_via_http_gate_curl,
)
from python_keywords.neofs_verbs import put_object_to_random_node
from utility import wait_for_gc_pass_on_storage_nodes
from wellknown_acl import PUBLIC_ACL

from steps.cluster_test_base import ClusterTestBase

logger = logging.getLogger("NeoLogger")
OBJECT_NOT_FOUND_ERROR = "not found"


@allure.link(
    "https://github.com/nspcc-dev/neofs-http-gw#neofs-http-gateway", name="neofs-http-gateway"
)
@allure.link("https://github.com/nspcc-dev/neofs-http-gw#uploading", name="uploading")
@allure.link("https://github.com/nspcc-dev/neofs-http-gw#downloading", name="downloading")
@pytest.mark.sanity
@pytest.mark.http_gate
class TestHttpGate(ClusterTestBase):
    PLACEMENT_RULE_1 = "REP 1 IN X CBF 1 SELECT 1 FROM * AS X"
    PLACEMENT_RULE_2 = "REP 2 IN X CBF 2 SELECT 2 FROM * AS X"

    @pytest.fixture(scope="class", autouse=True)
    @allure.title("[Class/Autouse]: Prepare wallet and deposit")
    def prepare_wallet(self, default_wallet):
        TestHttpGate.wallet = default_wallet

    @allure.title("Test Put over gRPC, Get over HTTP")
    def test_put_grpc_get_http(self, complex_object_size, simple_object_size):
        """
        Test that object can be put using gRPC interface and get using HTTP.

        Steps:
        1. Create simple and large objects.
        2. Put objects using gRPC (neofs-cli).
        3. Download objects using HTTP gate (https://github.com/nspcc-dev/neofs-http-gw#downloading).
        4. Get objects using gRPC (neofs-cli).
        5. Compare hashes for got objects.
        6. Compare hashes for got and original objects.

        Expected result:
        Hashes must be the same.
        """
        cid = create_container(
            self.wallet,
            shell=self.shell,
            endpoint=self.cluster.default_rpc_endpoint,
            rule=self.PLACEMENT_RULE_1,
            basic_acl=PUBLIC_ACL,
        )
        file_path_simple, file_path_large = generate_file(simple_object_size), generate_file(
            complex_object_size
        )

        with allure.step("Put objects using gRPC"):
            oid_simple = put_object_to_random_node(
                wallet=self.wallet,
                path=file_path_simple,
                cid=cid,
                shell=self.shell,
                cluster=self.cluster,
            )
            oid_large = put_object_to_random_node(
                wallet=self.wallet,
                path=file_path_large,
                cid=cid,
                shell=self.shell,
                cluster=self.cluster,
            )

        for oid, file_path in ((oid_simple, file_path_simple), (oid_large, file_path_large)):
            get_object_and_verify_hashes(
                oid=oid,
                file_name=file_path,
                wallet=self.wallet,
                cid=cid,
                shell=self.shell,
                nodes=self.cluster.storage_nodes,
                endpoint=self.cluster.default_http_gate_endpoint,
            )

    @allure.link("https://github.com/nspcc-dev/neofs-http-gw#uploading", name="uploading")
    @allure.link("https://github.com/nspcc-dev/neofs-http-gw#downloading", name="downloading")
    @allure.title("Test Put over HTTP, Get over HTTP")
    @pytest.mark.smoke
    def test_put_http_get_http(self, complex_object_size, simple_object_size):
        """
        Test that object can be put and get using HTTP interface.

        Steps:
        1. Create simple and large objects.
        2. Upload objects using HTTP (https://github.com/nspcc-dev/neofs-http-gw#uploading).
        3. Download objects using HTTP gate (https://github.com/nspcc-dev/neofs-http-gw#downloading).
        4. Compare hashes for got and original objects.

        Expected result:
        Hashes must be the same.
        """
        cid = create_container(
            self.wallet,
            shell=self.shell,
            endpoint=self.cluster.default_rpc_endpoint,
            rule=self.PLACEMENT_RULE_2,
            basic_acl=PUBLIC_ACL,
        )
        file_path_simple, file_path_large = generate_file(simple_object_size), generate_file(
            complex_object_size
        )

        with allure.step("Put objects using HTTP"):
            oid_simple = upload_via_http_gate(
                cid=cid, path=file_path_simple, endpoint=self.cluster.default_http_gate_endpoint
            )
            oid_large = upload_via_http_gate(
                cid=cid, path=file_path_large, endpoint=self.cluster.default_http_gate_endpoint
            )

        for oid, file_path in ((oid_simple, file_path_simple), (oid_large, file_path_large)):
            get_object_and_verify_hashes(
                oid=oid,
                file_name=file_path,
                wallet=self.wallet,
                cid=cid,
                shell=self.shell,
                nodes=self.cluster.storage_nodes,
                endpoint=self.cluster.default_http_gate_endpoint,
            )

    @allure.link(
        "https://github.com/nspcc-dev/neofs-http-gw#by-attributes", name="download by attributes"
    )
    @allure.title("Test Put over HTTP, Get over HTTP with headers")
    @pytest.mark.parametrize(
        "attributes",
        [
            {"fileName": "simple_obj_filename"},
            {"file-Name": "simple obj filename"},
            {"cat%jpeg": "cat%jpeg"},
        ],
        ids=["simple", "hyphen", "percent"],
    )
    def test_put_http_get_http_with_headers(self, attributes: dict, simple_object_size):
        """
        Test that object can be downloaded using different attributes in HTTP header.

        Steps:
        1. Create simple and large objects.
        2. Upload objects using HTTP with particular attributes in the header.
        3. Download objects by attributes using HTTP gate (https://github.com/nspcc-dev/neofs-http-gw#by-attributes).
        4. Compare hashes for got and original objects.

        Expected result:
        Hashes must be the same.
        """
        cid = create_container(
            self.wallet,
            shell=self.shell,
            endpoint=self.cluster.default_rpc_endpoint,
            rule=self.PLACEMENT_RULE_2,
            basic_acl=PUBLIC_ACL,
        )
        file_path = generate_file(simple_object_size)

        with allure.step("Put objects using HTTP with attribute"):
            headers = attr_into_header(attributes)
            oid = upload_via_http_gate(
                cid=cid,
                path=file_path,
                headers=headers,
                endpoint=self.cluster.default_http_gate_endpoint,
            )

        get_object_by_attr_and_verify_hashes(
            oid=oid,
            file_name=file_path,
            cid=cid,
            attrs=attributes,
            endpoint=self.cluster.default_http_gate_endpoint,
        )

    @allure.title("Test Expiration-Epoch in HTTP header")
    def test_expiration_epoch_in_http(self, simple_object_size):
        endpoint = self.cluster.default_rpc_endpoint
        http_endpoint = self.cluster.default_http_gate_endpoint

        cid = create_container(
            self.wallet,
            shell=self.shell,
            endpoint=endpoint,
            rule=self.PLACEMENT_RULE_2,
            basic_acl=PUBLIC_ACL,
        )
        file_path = generate_file(simple_object_size)
        oids = []

        curr_epoch = get_epoch(self.shell, self.cluster)
        epochs = (curr_epoch, curr_epoch + 1, curr_epoch + 2, curr_epoch + 100)

        for epoch in epochs:
            headers = {"X-Attribute-Neofs-Expiration-Epoch": str(epoch)}

            with allure.step("Put objects using HTTP with attribute Expiration-Epoch"):
                oids.append(
                    upload_via_http_gate(
                        cid=cid, path=file_path, headers=headers, endpoint=http_endpoint
                    )
                )

        assert len(oids) == len(epochs), "Expected all objects have been put successfully"

        with allure.step("All objects can be get"):
            for oid in oids:
                get_via_http_gate(cid=cid, oid=oid, endpoint=http_endpoint)

        for expired_objects, not_expired_objects in [(oids[:1], oids[1:]), (oids[:2], oids[2:])]:
            tick_epoch(self.shell, self.cluster)

            # Wait for GC, because object with expiration is counted as alive until GC removes it
            wait_for_gc_pass_on_storage_nodes()

            for oid in expired_objects:
                try_to_get_object_and_expect_error(
                    cid=cid,
                    oid=oid,
                    error_pattern=OBJECT_NOT_FOUND_ERROR,
                    endpoint=self.cluster.default_http_gate_endpoint,
                )

            with allure.step("Other objects can be get"):
                for oid in not_expired_objects:
                    get_via_http_gate(cid=cid, oid=oid, endpoint=http_endpoint)

    @allure.title("Test Zip in HTTP header")
    def test_zip_in_http(self, complex_object_size, simple_object_size):
        cid = create_container(
            self.wallet,
            shell=self.shell,
            endpoint=self.cluster.default_rpc_endpoint,
            rule=self.PLACEMENT_RULE_2,
            basic_acl=PUBLIC_ACL,
        )
        file_path_simple, file_path_large = generate_file(simple_object_size), generate_file(
            complex_object_size
        )
        common_prefix = "my_files"

        headers1 = {"X-Attribute-FilePath": f"{common_prefix}/file1"}
        headers2 = {"X-Attribute-FilePath": f"{common_prefix}/file2"}

        upload_via_http_gate(
            cid=cid,
            path=file_path_simple,
            headers=headers1,
            endpoint=self.cluster.default_http_gate_endpoint,
        )
        upload_via_http_gate(
            cid=cid,
            path=file_path_large,
            headers=headers2,
            endpoint=self.cluster.default_http_gate_endpoint,
        )

        dir_path = get_via_zip_http_gate(
            cid=cid, prefix=common_prefix, endpoint=self.cluster.default_http_gate_endpoint
        )

        with allure.step("Verify hashes"):
            assert get_file_hash(f"{dir_path}/file1") == get_file_hash(file_path_simple)
            assert get_file_hash(f"{dir_path}/file2") == get_file_hash(file_path_large)

    @pytest.mark.long
    @allure.title("Test Put over HTTP/Curl, Get over HTTP/Curl for large object")
    def test_put_http_get_http_large_file(self, complex_object_size):
        """
        This test checks upload and download using curl with 'large' object.
        Large is object with size up to 20Mb.
        """
        cid = create_container(
            self.wallet,
            shell=self.shell,
            endpoint=self.cluster.default_rpc_endpoint,
            rule=self.PLACEMENT_RULE_2,
            basic_acl=PUBLIC_ACL,
        )

        obj_size = int(os.getenv("BIG_OBJ_SIZE", complex_object_size))
        file_path = generate_file(obj_size)

        with allure.step("Put objects using HTTP"):
            oid_gate = upload_via_http_gate(
                cid=cid, path=file_path, endpoint=self.cluster.default_http_gate_endpoint
            )
            oid_curl = upload_via_http_gate_curl(
                cid=cid,
                filepath=file_path,
                large_object=True,
                endpoint=self.cluster.default_http_gate_endpoint,
            )

        get_object_and_verify_hashes(
            oid=oid_gate,
            file_name=file_path,
            wallet=self.wallet,
            cid=cid,
            shell=self.shell,
            nodes=self.cluster.storage_nodes,
            endpoint=self.cluster.default_http_gate_endpoint,
        )
        get_object_and_verify_hashes(
            oid=oid_curl,
            file_name=file_path,
            wallet=self.wallet,
            cid=cid,
            shell=self.shell,
            nodes=self.cluster.storage_nodes,
            endpoint=self.cluster.default_http_gate_endpoint,
            object_getter=get_via_http_curl,
        )

    @allure.title("Test Put/Get over HTTP using Curl utility")
    def test_put_http_get_http_curl(self, complex_object_size, simple_object_size):
        """
        Test checks upload and download over HTTP using curl utility.
        """
        cid = create_container(
            self.wallet,
            shell=self.shell,
            endpoint=self.cluster.default_rpc_endpoint,
            rule=self.PLACEMENT_RULE_2,
            basic_acl=PUBLIC_ACL,
        )
        file_path_simple, file_path_large = generate_file(simple_object_size), generate_file(
            complex_object_size
        )

        with allure.step("Put objects using curl utility"):
            oid_simple = upload_via_http_gate_curl(
                cid=cid, filepath=file_path_simple, endpoint=self.cluster.default_http_gate_endpoint
            )
            oid_large = upload_via_http_gate_curl(
                cid=cid, filepath=file_path_large, endpoint=self.cluster.default_http_gate_endpoint
            )

        for oid, file_path in ((oid_simple, file_path_simple), (oid_large, file_path_large)):
            get_object_and_verify_hashes(
                oid=oid,
                file_name=file_path,
                wallet=self.wallet,
                cid=cid,
                shell=self.shell,
                nodes=self.cluster.storage_nodes,
                endpoint=self.cluster.default_http_gate_endpoint,
                object_getter=get_via_http_curl,
            )
