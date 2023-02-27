import allure
import pytest

from pytest_tests.helpers.file_helper import generate_file, get_file_hash, split_file
from pytest_tests.helpers.s3_helper import (
    check_objects_in_bucket,
    object_key_from_file_path,
    set_bucket_versioning,
)
from pytest_tests.steps import s3_gate_bucket, s3_gate_object
from pytest_tests.steps.s3_gate_base import TestS3GateBase

PART_SIZE = 5 * 1024 * 1024


def pytest_generate_tests(metafunc):
    if "s3_client" in metafunc.fixturenames:
        metafunc.parametrize("s3_client", ["aws cli", "boto3"], indirect=True)


@pytest.mark.sanity
@pytest.mark.s3_gate
@pytest.mark.s3_gate_multipart
class TestS3GateMultipart(TestS3GateBase):
    @allure.title("Test S3 Object Multipart API")
    def test_s3_object_multipart(self):
        bucket = s3_gate_bucket.create_bucket_s3(self.s3_client)
        set_bucket_versioning(self.s3_client, bucket, s3_gate_bucket.VersioningStatus.ENABLED)
        parts_count = 5
        file_name_large = generate_file(PART_SIZE * parts_count)  # 5Mb - min part
        object_key = object_key_from_file_path(file_name_large)
        part_files = split_file(file_name_large, parts_count)
        parts = []

        with allure.step("Upload first part"):
            upload_id = s3_gate_object.create_multipart_upload_s3(
                self.s3_client, bucket, object_key
            )
            uploads = s3_gate_object.list_multipart_uploads_s3(self.s3_client, bucket)
            etag = s3_gate_object.upload_part_s3(
                self.s3_client, bucket, object_key, upload_id, 1, part_files[0]
            )
            parts.append((1, etag))
            got_parts = s3_gate_object.list_parts_s3(self.s3_client, bucket, object_key, upload_id)
            assert len(got_parts) == 1, f"Expected {1} parts, got\n{got_parts}"

        with allure.step("Upload last parts"):
            for part_id, file_path in enumerate(part_files[1:], start=2):
                etag = s3_gate_object.upload_part_s3(
                    self.s3_client, bucket, object_key, upload_id, part_id, file_path
                )
                parts.append((part_id, etag))
            got_parts = s3_gate_object.list_parts_s3(self.s3_client, bucket, object_key, upload_id)
            s3_gate_object.complete_multipart_upload_s3(
                self.s3_client, bucket, object_key, upload_id, parts
            )
            assert len(got_parts) == len(
                part_files
            ), f"Expected {parts_count} parts, got\n{got_parts}"

        with allure.step("Check upload list is empty"):
            uploads = s3_gate_object.list_multipart_uploads_s3(self.s3_client, bucket)
            assert not uploads, f"Expected there is no uploads in bucket {bucket}"

        with allure.step("Check we can get whole object from bucket"):
            got_object = s3_gate_object.get_object_s3(self.s3_client, bucket, object_key)
            assert get_file_hash(got_object) == get_file_hash(file_name_large)

    @allure.title("Test S3 Multipart abord")
    def test_s3_abort_multipart(self):
        bucket = s3_gate_bucket.create_bucket_s3(self.s3_client)
        set_bucket_versioning(self.s3_client, bucket, s3_gate_bucket.VersioningStatus.ENABLED)
        parts_count = 5
        file_name_large = generate_file(PART_SIZE * parts_count)  # 5Mb - min part
        object_key = object_key_from_file_path(file_name_large)
        part_files = split_file(file_name_large, parts_count)
        parts = []

        with allure.step("Upload first part"):
            upload_id = s3_gate_object.create_multipart_upload_s3(
                self.s3_client, bucket, object_key
            )
            uploads = s3_gate_object.list_multipart_uploads_s3(self.s3_client, bucket)
            etag = s3_gate_object.upload_part_s3(
                self.s3_client, bucket, object_key, upload_id, 1, part_files[0]
            )
            parts.append((1, etag))
            got_parts = s3_gate_object.list_parts_s3(self.s3_client, bucket, object_key, upload_id)
            assert len(got_parts) == 1, f"Expected {1} parts, got\n{got_parts}"

        with allure.step("Abort multipart upload"):
            s3_gate_object.abort_multipart_uploads_s3(self.s3_client, bucket, object_key, upload_id)
            uploads = s3_gate_object.list_multipart_uploads_s3(self.s3_client, bucket)
            assert not uploads, f"Expected there is no uploads in bucket {bucket}"

    @allure.title("Test S3 Upload Part Copy")
    def test_s3_multipart_copy(self):
        bucket = s3_gate_bucket.create_bucket_s3(self.s3_client)
        set_bucket_versioning(self.s3_client, bucket, s3_gate_bucket.VersioningStatus.ENABLED)
        parts_count = 3
        file_name_large = generate_file(PART_SIZE * parts_count)  # 5Mb - min part
        object_key = object_key_from_file_path(file_name_large)
        part_files = split_file(file_name_large, parts_count)
        parts = []
        objs = []

        with allure.step(f"Put {parts_count} objec in bucket"):
            for part in part_files:
                s3_gate_object.put_object_s3(self.s3_client, bucket, part)
                objs.append(object_key_from_file_path(part))
            check_objects_in_bucket(self.s3_client, bucket, objs)

        with allure.step("Create multipart upload object"):
            upload_id = s3_gate_object.create_multipart_upload_s3(
                self.s3_client, bucket, object_key
            )
            uploads = s3_gate_object.list_multipart_uploads_s3(self.s3_client, bucket)
            assert uploads, f"Expected there are uploads in bucket {bucket}"

        with allure.step("Start multipart upload"):
            for part_id, obj_key in enumerate(objs, start=1):
                etag = s3_gate_object.upload_part_copy_s3(
                    self.s3_client, bucket, object_key, upload_id, part_id, f"{bucket}/{obj_key}"
                )
                parts.append((part_id, etag))
            got_parts = s3_gate_object.list_parts_s3(self.s3_client, bucket, object_key, upload_id)
            s3_gate_object.complete_multipart_upload_s3(
                self.s3_client, bucket, object_key, upload_id, parts
            )
            assert len(got_parts) == len(
                part_files
            ), f"Expected {parts_count} parts, got\n{got_parts}"

        with allure.step("Check we can get whole object from bucket"):
            got_object = s3_gate_object.get_object_s3(self.s3_client, bucket, object_key)
            assert get_file_hash(got_object) == get_file_hash(file_name_large)
