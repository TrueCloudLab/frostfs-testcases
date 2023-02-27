from datetime import datetime, timedelta

import allure
import pytest

from pytest_tests.helpers.file_helper import generate_file
from pytest_tests.helpers.s3_helper import (
    assert_object_lock_mode,
    assert_s3_acl,
    check_objects_in_bucket,
    object_key_from_file_path,
)
from pytest_tests.steps import s3_gate_bucket, s3_gate_object
from pytest_tests.steps.s3_gate_base import TestS3GateBase


def pytest_generate_tests(metafunc):
    if "s3_client" in metafunc.fixturenames:
        metafunc.parametrize("s3_client", ["aws cli", "boto3"], indirect=True)


@pytest.mark.sanity
@pytest.mark.s3_gate
@pytest.mark.s3_gate_bucket
class TestS3GateBucket(TestS3GateBase):
    @allure.title("Test S3: Create Bucket with different ACL")
    def test_s3_create_bucket_with_ACL(self):

        with allure.step("Create bucket with ACL private"):
            bucket = s3_gate_bucket.create_bucket_s3(self.s3_client, True, acl="private")
            bucket_acl = s3_gate_bucket.get_bucket_acl(self.s3_client, bucket)
            assert_s3_acl(acl_grants=bucket_acl, permitted_users="CanonicalUser")

        with allure.step("Create bucket with ACL = public-read"):
            bucket_1 = s3_gate_bucket.create_bucket_s3(self.s3_client, True, acl="public-read")
            bucket_acl_1 = s3_gate_bucket.get_bucket_acl(self.s3_client, bucket_1)
            assert_s3_acl(acl_grants=bucket_acl_1, permitted_users="AllUsers")

        with allure.step("Create bucket with ACL public-read-write"):
            bucket_2 = s3_gate_bucket.create_bucket_s3(
                self.s3_client, True, acl="public-read-write"
            )
            bucket_acl_2 = s3_gate_bucket.get_bucket_acl(self.s3_client, bucket_2)
            assert_s3_acl(acl_grants=bucket_acl_2, permitted_users="AllUsers")

        with allure.step("Create bucket with ACL = authenticated-read"):
            bucket_3 = s3_gate_bucket.create_bucket_s3(
                self.s3_client, True, acl="authenticated-read"
            )
            bucket_acl_3 = s3_gate_bucket.get_bucket_acl(self.s3_client, bucket_3)
            assert_s3_acl(acl_grants=bucket_acl_3, permitted_users="AllUsers")

    @allure.title("Test S3: Create Bucket with different ACL by grand")
    def test_s3_create_bucket_with_grands(self):

        with allure.step("Create bucket with  --grant-read"):
            bucket = s3_gate_bucket.create_bucket_s3(
                self.s3_client,
                True,
                grant_read="uri=http://acs.amazonaws.com/groups/global/AllUsers",
            )
            bucket_acl = s3_gate_bucket.get_bucket_acl(self.s3_client, bucket)
            assert_s3_acl(acl_grants=bucket_acl, permitted_users="AllUsers")

        with allure.step("Create bucket with --grant-wtite"):
            bucket_1 = s3_gate_bucket.create_bucket_s3(
                self.s3_client,
                True,
                grant_write="uri=http://acs.amazonaws.com/groups/global/AllUsers",
            )
            bucket_acl_1 = s3_gate_bucket.get_bucket_acl(self.s3_client, bucket_1)
            assert_s3_acl(acl_grants=bucket_acl_1, permitted_users="AllUsers")

        with allure.step("Create bucket with --grant-full-control"):
            bucket_2 = s3_gate_bucket.create_bucket_s3(
                self.s3_client,
                True,
                grant_full_control="uri=http://acs.amazonaws.com/groups/global/AllUsers",
            )
            bucket_acl_2 = s3_gate_bucket.get_bucket_acl(self.s3_client, bucket_2)
            assert_s3_acl(acl_grants=bucket_acl_2, permitted_users="AllUsers")

    @allure.title("Test S3: create bucket with object lock")
    def test_s3_bucket_object_lock(self, simple_object_size):
        file_path = generate_file(simple_object_size)
        file_name = object_key_from_file_path(file_path)

        with allure.step("Create bucket with --no-object-lock-enabled-for-bucket"):
            bucket = s3_gate_bucket.create_bucket_s3(self.s3_client, False)
            date_obj = datetime.utcnow() + timedelta(days=1)
            with pytest.raises(
                Exception, match=r".*Object Lock configuration does not exist for this bucket.*"
            ):
                # An error occurred (ObjectLockConfigurationNotFoundError) when calling the PutObject operation (reached max retries: 0):
                # Object Lock configuration does not exist for this bucket
                s3_gate_object.put_object_s3(
                    self.s3_client,
                    bucket,
                    file_path,
                    ObjectLockMode="COMPLIANCE",
                    ObjectLockRetainUntilDate=date_obj.strftime("%Y-%m-%dT%H:%M:%S"),
                )
        with allure.step("Create bucket with --object-lock-enabled-for-bucket"):
            bucket_1 = s3_gate_bucket.create_bucket_s3(self.s3_client, True)
            date_obj_1 = datetime.utcnow() + timedelta(days=1)
            s3_gate_object.put_object_s3(
                self.s3_client,
                bucket_1,
                file_path,
                ObjectLockMode="COMPLIANCE",
                ObjectLockRetainUntilDate=date_obj_1.strftime("%Y-%m-%dT%H:%M:%S"),
                ObjectLockLegalHoldStatus="ON",
            )
            assert_object_lock_mode(
                self.s3_client, bucket_1, file_name, "COMPLIANCE", date_obj_1, "ON"
            )

    @allure.title("Test S3: delete bucket")
    def test_s3_delete_bucket(self, simple_object_size):
        file_path_1 = generate_file(simple_object_size)
        file_name_1 = object_key_from_file_path(file_path_1)
        file_path_2 = generate_file(simple_object_size)
        file_name_2 = object_key_from_file_path(file_path_2)
        bucket = s3_gate_bucket.create_bucket_s3(self.s3_client)

        with allure.step("Put two objects into bucket"):
            s3_gate_object.put_object_s3(self.s3_client, bucket, file_path_1)
            s3_gate_object.put_object_s3(self.s3_client, bucket, file_path_2)
            check_objects_in_bucket(self.s3_client, bucket, [file_name_1, file_name_2])

        with allure.step("Try to delete not empty bucket and get error"):
            with pytest.raises(Exception, match=r".*The bucket you tried to delete is not empty.*"):
                s3_gate_bucket.delete_bucket_s3(self.s3_client, bucket)

        with allure.step("Delete object in bucket"):
            s3_gate_object.delete_object_s3(self.s3_client, bucket, file_name_1)
            s3_gate_object.delete_object_s3(self.s3_client, bucket, file_name_2)
            check_objects_in_bucket(self.s3_client, bucket, [])

        with allure.step(f"Delete empty bucket"):
            s3_gate_bucket.delete_bucket_s3(self.s3_client, bucket)
            with pytest.raises(Exception, match=r".*Not Found.*"):
                s3_gate_bucket.head_bucket(self.s3_client, bucket)
