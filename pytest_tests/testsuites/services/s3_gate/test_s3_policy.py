import os

import allure
import pytest
from file_helper import generate_file
from python_keywords.container import search_container_by_name
from python_keywords.storage_policy import get_simple_object_copies
from s3_helper import check_objects_in_bucket, object_key_from_file_path, set_bucket_versioning

from steps import s3_gate_bucket, s3_gate_object
from steps.s3_gate_base import TestS3GateBase


def pytest_generate_tests(metafunc):
    policy = f"{os.getcwd()}/robot/resources/files/policy.json"
    if "s3_client" in metafunc.fixturenames:
        metafunc.parametrize(
            "s3_client",
            [("aws cli", policy), ("boto3", policy)],
            indirect=True,
            ids=["aws cli", "boto3"],
        )


@pytest.mark.s3_gate
class TestS3GatePolicy(TestS3GateBase):
    @allure.title("Test S3: Verify bucket creation with retention policy applied")
    def test_s3_bucket_location(self, simple_object_size):
        file_path_1 = generate_file(simple_object_size)
        file_name_1 = object_key_from_file_path(file_path_1)
        file_path_2 = generate_file(simple_object_size)
        file_name_2 = object_key_from_file_path(file_path_2)

        with allure.step("Create two buckets with different bucket configuration"):
            bucket_1 = s3_gate_bucket.create_bucket_s3(
                self.s3_client, bucket_configuration="complex"
            )
            set_bucket_versioning(self.s3_client, bucket_1, s3_gate_bucket.VersioningStatus.ENABLED)
            bucket_2 = s3_gate_bucket.create_bucket_s3(self.s3_client, bucket_configuration="rep-3")
            set_bucket_versioning(self.s3_client, bucket_2, s3_gate_bucket.VersioningStatus.ENABLED)
            list_buckets = s3_gate_bucket.list_buckets_s3(self.s3_client)
            assert (
                bucket_1 in list_buckets and bucket_2 in list_buckets
            ), f"Expected two buckets {bucket_1, bucket_2}, got {list_buckets}"

            # with allure.step("Check head buckets"):
            head_1 = s3_gate_bucket.head_bucket(self.s3_client, bucket_1)
            head_2 = s3_gate_bucket.head_bucket(self.s3_client, bucket_2)
            assert head_1 == {} or head_1.get("HEAD") == None, "Expected head is empty"
            assert head_2 == {} or head_2.get("HEAD") == None, "Expected head is empty"

        with allure.step("Put objects into buckets"):
            version_id_1 = s3_gate_object.put_object_s3(self.s3_client, bucket_1, file_path_1)
            version_id_2 = s3_gate_object.put_object_s3(self.s3_client, bucket_2, file_path_2)
            check_objects_in_bucket(self.s3_client, bucket_1, [file_name_1])
            check_objects_in_bucket(self.s3_client, bucket_2, [file_name_2])

        with allure.step("Check bucket location"):
            bucket_loc_1 = s3_gate_bucket.get_bucket_location(self.s3_client, bucket_1)
            bucket_loc_2 = s3_gate_bucket.get_bucket_location(self.s3_client, bucket_2)
            assert bucket_loc_1 == "complex"
            assert bucket_loc_2 == "rep-3"

        with allure.step("Check object policy"):
            cid_1 = search_container_by_name(
                self.wallet, bucket_1, shell=self.shell, endpoint=self.cluster.default_rpc_endpoint
            )
            copies_1 = get_simple_object_copies(
                wallet=self.wallet,
                cid=cid_1,
                oid=version_id_1,
                shell=self.shell,
                nodes=self.cluster.storage_nodes,
            )
            assert copies_1 == 1
            cid_2 = search_container_by_name(
                self.wallet, bucket_2, shell=self.shell, endpoint=self.cluster.default_rpc_endpoint
            )
            copies_2 = get_simple_object_copies(
                wallet=self.wallet,
                cid=cid_2,
                oid=version_id_2,
                shell=self.shell,
                nodes=self.cluster.storage_nodes,
            )
            assert copies_2 == 3

    @allure.title("Test S3: bucket policy ")
    def test_s3_bucket_policy(self):
        with allure.step("Create bucket with default policy"):
            bucket = s3_gate_bucket.create_bucket_s3(self.s3_client)
            set_bucket_versioning(self.s3_client, bucket, s3_gate_bucket.VersioningStatus.ENABLED)

        with allure.step("GetBucketPolicy"):
            s3_gate_bucket.get_bucket_policy(self.s3_client, bucket)

        with allure.step("Put new policy"):
            custom_policy = f"file://{os.getcwd()}/robot/resources/files/bucket_policy.json"
            custom_policy = {
                "Version": "2008-10-17",
                "Id": "aaaa-bbbb-cccc-dddd",
                "Statement": [
                    {
                        "Sid": "AddPerm",
                        "Effect": "Allow",
                        "Principal": {"AWS": "*"},
                        "Action": ["s3:GetObject"],
                        "Resource": [f"arn:aws:s3:::{bucket}/*"],
                    }
                ],
            }

            s3_gate_bucket.put_bucket_policy(self.s3_client, bucket, custom_policy)
        with allure.step("GetBucketPolicy"):
            policy_1 = s3_gate_bucket.get_bucket_policy(self.s3_client, bucket)
            print(policy_1)

    @allure.title("Test S3: bucket policy ")
    def test_s3_cors(self):
        with allure.step("Create bucket without cors"):
            bucket = s3_gate_bucket.create_bucket_s3(self.s3_client)
            set_bucket_versioning(self.s3_client, bucket, s3_gate_bucket.VersioningStatus.ENABLED)

        with pytest.raises(Exception):
            bucket_cors = s3_gate_bucket.get_bucket_cors(self.s3_client, bucket)

        with allure.step("Put bucket cors"):
            cors = {
                "CORSRules": [
                    {
                        "AllowedOrigins": ["http://www.example.com"],
                        "AllowedHeaders": ["*"],
                        "AllowedMethods": ["PUT", "POST", "DELETE"],
                        "MaxAgeSeconds": 3000,
                        "ExposeHeaders": ["x-amz-server-side-encryption"],
                    },
                    {
                        "AllowedOrigins": ["*"],
                        "AllowedHeaders": ["Authorization"],
                        "AllowedMethods": ["GET"],
                        "MaxAgeSeconds": 3000,
                    },
                ]
            }
            s3_gate_bucket.put_bucket_cors(self.s3_client, bucket, cors)
            bucket_cors = s3_gate_bucket.get_bucket_cors(self.s3_client, bucket)
            assert bucket_cors == cors.get(
                "CORSRules"
            ), f"Expected corsrules must be {cors.get('CORSRules')}"

        with allure.step("delete bucket cors"):
            s3_gate_bucket.delete_bucket_cors(self.s3_client, bucket)

        with pytest.raises(Exception):
            bucket_cors = s3_gate_bucket.get_bucket_cors(self.s3_client, bucket)
