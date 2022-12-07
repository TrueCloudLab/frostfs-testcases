import time
from datetime import datetime, timedelta

import allure
import pytest
from file_helper import generate_file, generate_file_with_content
from s3_helper import assert_object_lock_mode, check_objects_in_bucket, object_key_from_file_path

from steps import s3_gate_bucket, s3_gate_object
from steps.s3_gate_base import TestS3GateBase


def pytest_generate_tests(metafunc):
    if "s3_client" in metafunc.fixturenames:
        metafunc.parametrize("s3_client", ["aws cli", "boto3"], indirect=True)


@pytest.mark.sanity
@pytest.mark.s3_gate
@pytest.mark.s3_gate_locking
@pytest.mark.parametrize("version_id", [None, "second"])
class TestS3GateLocking(TestS3GateBase):
    @allure.title("Test S3: Checking the operation of retention period & legal lock on the object")
    def test_s3_object_locking(self, version_id, simple_object_size):
        file_path = generate_file(simple_object_size)
        file_name = object_key_from_file_path(file_path)
        retention_period = 2

        bucket = s3_gate_bucket.create_bucket_s3(self.s3_client, True)

        with allure.step("Put several versions of object into bucket"):
            s3_gate_object.put_object_s3(self.s3_client, bucket, file_path)
            file_name_1 = generate_file_with_content(simple_object_size, file_path=file_path)
            version_id_2 = s3_gate_object.put_object_s3(self.s3_client, bucket, file_name_1)
            check_objects_in_bucket(self.s3_client, bucket, [file_name])
            if version_id:
                version_id = version_id_2

        with allure.step(f"Put retention period {retention_period}min to object {file_name}"):
            date_obj = datetime.utcnow() + timedelta(minutes=retention_period)
            retention = {
                "Mode": "COMPLIANCE",
                "RetainUntilDate": date_obj,
            }
            s3_gate_object.put_object_retention(
                self.s3_client, bucket, file_name, retention, version_id
            )
            assert_object_lock_mode(
                self.s3_client, bucket, file_name, "COMPLIANCE", date_obj, "OFF"
            )

        with allure.step(f"Put legal hold to object {file_name}"):
            s3_gate_object.put_object_legal_hold(
                self.s3_client, bucket, file_name, "ON", version_id
            )
            assert_object_lock_mode(self.s3_client, bucket, file_name, "COMPLIANCE", date_obj, "ON")

        with allure.step(f"Fail with deleting object with legal hold and retention period"):
            if version_id:
                with pytest.raises(Exception):
                    # An error occurred (AccessDenied) when calling the DeleteObject operation (reached max retries: 0): Access Denied.
                    s3_gate_object.delete_object_s3(self.s3_client, bucket, file_name, version_id)

        with allure.step(f"Check retention period is no longer set on the uploaded object"):
            time.sleep((retention_period + 1) * 60)
            assert_object_lock_mode(self.s3_client, bucket, file_name, "COMPLIANCE", date_obj, "ON")

        with allure.step(f"Fail with deleting object with legal hold and retention period"):
            if version_id:
                with pytest.raises(Exception):
                    # An error occurred (AccessDenied) when calling the DeleteObject operation (reached max retries: 0): Access Denied.
                    s3_gate_object.delete_object_s3(self.s3_client, bucket, file_name, version_id)
            else:
                s3_gate_object.delete_object_s3(self.s3_client, bucket, file_name, version_id)

    @allure.title("Test S3: Checking the impossibility to change the retention mode COMPLIANCE")
    def test_s3_mode_compliance(self, version_id, simple_object_size):
        file_path = generate_file(simple_object_size)
        file_name = object_key_from_file_path(file_path)
        retention_period = 2
        retention_period_1 = 1

        bucket = s3_gate_bucket.create_bucket_s3(self.s3_client, True)

        with allure.step("Put object into bucket"):
            obj_version = s3_gate_object.put_object_s3(self.s3_client, bucket, file_path)
            if version_id:
                version_id = obj_version
            check_objects_in_bucket(self.s3_client, bucket, [file_name])

        with allure.step(f"Put retention period {retention_period}min to object {file_name}"):
            date_obj = datetime.utcnow() + timedelta(minutes=retention_period)
            retention = {
                "Mode": "COMPLIANCE",
                "RetainUntilDate": date_obj,
            }
            s3_gate_object.put_object_retention(
                self.s3_client, bucket, file_name, retention, version_id
            )
            assert_object_lock_mode(
                self.s3_client, bucket, file_name, "COMPLIANCE", date_obj, "OFF"
            )

        with allure.step(
            f"Try to change retention period {retention_period_1}min to object {file_name}"
        ):
            date_obj = datetime.utcnow() + timedelta(minutes=retention_period_1)
            retention = {
                "Mode": "COMPLIANCE",
                "RetainUntilDate": date_obj,
            }
            with pytest.raises(Exception):
                s3_gate_object.put_object_retention(
                    self.s3_client, bucket, file_name, retention, version_id
                )

    @allure.title("Test S3: Checking the ability to change retention mode GOVERNANCE")
    def test_s3_mode_governance(self, version_id, simple_object_size):
        file_path = generate_file(simple_object_size)
        file_name = object_key_from_file_path(file_path)
        retention_period = 3
        retention_period_1 = 2
        retention_period_2 = 5

        bucket = s3_gate_bucket.create_bucket_s3(self.s3_client, True)

        with allure.step("Put object into bucket"):
            obj_version = s3_gate_object.put_object_s3(self.s3_client, bucket, file_path)
            if version_id:
                version_id = obj_version
            check_objects_in_bucket(self.s3_client, bucket, [file_name])

        with allure.step(f"Put retention period {retention_period}min to object {file_name}"):
            date_obj = datetime.utcnow() + timedelta(minutes=retention_period)
            retention = {
                "Mode": "GOVERNANCE",
                "RetainUntilDate": date_obj,
            }
            s3_gate_object.put_object_retention(
                self.s3_client, bucket, file_name, retention, version_id
            )
            assert_object_lock_mode(
                self.s3_client, bucket, file_name, "GOVERNANCE", date_obj, "OFF"
            )

        with allure.step(
            f"Try to change retention period {retention_period_1}min to object {file_name}"
        ):
            date_obj = datetime.utcnow() + timedelta(minutes=retention_period_1)
            retention = {
                "Mode": "GOVERNANCE",
                "RetainUntilDate": date_obj,
            }
            with pytest.raises(Exception):
                s3_gate_object.put_object_retention(
                    self.s3_client, bucket, file_name, retention, version_id
                )

        with allure.step(
            f"Try to change retention period {retention_period_1}min to object {file_name}"
        ):
            date_obj = datetime.utcnow() + timedelta(minutes=retention_period_1)
            retention = {
                "Mode": "GOVERNANCE",
                "RetainUntilDate": date_obj,
            }
            with pytest.raises(Exception):
                s3_gate_object.put_object_retention(
                    self.s3_client, bucket, file_name, retention, version_id
                )

        with allure.step(f"Put new retention period {retention_period_2}min to object {file_name}"):
            date_obj = datetime.utcnow() + timedelta(minutes=retention_period_2)
            retention = {
                "Mode": "GOVERNANCE",
                "RetainUntilDate": date_obj,
            }
            s3_gate_object.put_object_retention(
                self.s3_client, bucket, file_name, retention, version_id, True
            )
            assert_object_lock_mode(
                self.s3_client, bucket, file_name, "GOVERNANCE", date_obj, "OFF"
            )

    @allure.title("Test S3: Checking if an Object Cannot Be Locked")
    def test_s3_legal_hold(self, version_id, simple_object_size):
        file_path = generate_file(simple_object_size)
        file_name = object_key_from_file_path(file_path)

        bucket = s3_gate_bucket.create_bucket_s3(self.s3_client, False)

        with allure.step("Put object into bucket"):
            obj_version = s3_gate_object.put_object_s3(self.s3_client, bucket, file_path)
            if version_id:
                version_id = obj_version
            check_objects_in_bucket(self.s3_client, bucket, [file_name])

        with allure.step(f"Put legal hold to object {file_name}"):
            with pytest.raises(Exception):
                s3_gate_object.put_object_legal_hold(
                    self.s3_client, bucket, file_name, "ON", version_id
                )


@pytest.mark.s3_gate
class TestS3GateLockingBucket(TestS3GateBase):
    @allure.title("Test S3: Bucket Lock")
    def test_s3_bucket_lock(self, simple_object_size):
        file_path = generate_file(simple_object_size)
        file_name = object_key_from_file_path(file_path)
        configuration = {"Rule": {"DefaultRetention": {"Mode": "COMPLIANCE", "Days": 1}}}

        bucket = s3_gate_bucket.create_bucket_s3(self.s3_client, True)

        with allure.step("PutObjectLockConfiguration with ObjectLockEnabled=False"):
            s3_gate_bucket.put_object_lock_configuration(self.s3_client, bucket, configuration)

        with allure.step("PutObjectLockConfiguration with ObjectLockEnabled=True"):
            configuration["ObjectLockEnabled"] = "Enabled"
            s3_gate_bucket.put_object_lock_configuration(self.s3_client, bucket, configuration)

        with allure.step("GetObjectLockConfiguration"):
            config = s3_gate_bucket.get_object_lock_configuration(self.s3_client, bucket)
            configuration["Rule"]["DefaultRetention"]["Years"] = 0
            assert config == configuration, f"Configurations must be equal {configuration}"

        with allure.step("Put object into bucket"):
            s3_gate_object.put_object_s3(self.s3_client, bucket, file_path)
            assert_object_lock_mode(self.s3_client, bucket, file_name, "COMPLIANCE", None, "OFF", 1)
