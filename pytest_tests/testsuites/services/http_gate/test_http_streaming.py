import logging

import allure
import pytest
from container import create_container
from file_helper import generate_file
from http_gate import get_object_and_verify_hashes, upload_via_http_gate_curl
from wellknown_acl import PUBLIC_ACL

from steps.cluster_test_base import ClusterTestBase

logger = logging.getLogger("NeoLogger")


@pytest.mark.sanity
@pytest.mark.http_gate
class Test_http_streaming(ClusterTestBase):
    PLACEMENT_RULE = "REP 2 IN X CBF 1 SELECT 4 FROM * AS X"

    @pytest.fixture(scope="class", autouse=True)
    @allure.title("[Class/Autouse]: Prepare wallet and deposit")
    def prepare_wallet(self, default_wallet):
        Test_http_streaming.wallet = default_wallet

    @allure.title("Test Put via pipe (steaming), Get over HTTP and verify hashes")
    @pytest.mark.parametrize(
        "object_size",
        [pytest.lazy_fixture("complex_object_size")],
        ids=["complex object"],
    )
    def test_object_can_be_put_get_by_streaming(self, object_size: int):
        """
        Test that object can be put using gRPC interface and get using HTTP.

        Steps:
        1. Create big object;
        2. Put object using curl with pipe (streaming);
        3. Download object using HTTP gate (https://github.com/nspcc-dev/neofs-http-gw#downloading);
        4. Compare hashes between original and downloaded object;

        Expected result:
        Hashes must be the same.
        """
        with allure.step("Create public container and verify container creation"):
            cid = create_container(
                self.wallet,
                shell=self.shell,
                endpoint=self.cluster.default_rpc_endpoint,
                rule=self.PLACEMENT_RULE,
                basic_acl=PUBLIC_ACL,
            )
        with allure.step("Allocate big object"):
            # Generate file
            file_path = generate_file(object_size)

        with allure.step(
            "Put objects using curl utility and Get object and verify hashes [ get/$CID/$OID ]"
        ):
            oid = upload_via_http_gate_curl(
                cid=cid, filepath=file_path, endpoint=self.cluster.default_http_gate_endpoint
            )
            get_object_and_verify_hashes(
                oid=oid,
                file_name=file_path,
                wallet=self.wallet,
                cid=cid,
                shell=self.shell,
                nodes=self.cluster.storage_nodes,
                endpoint=self.cluster.default_http_gate_endpoint,
            )
