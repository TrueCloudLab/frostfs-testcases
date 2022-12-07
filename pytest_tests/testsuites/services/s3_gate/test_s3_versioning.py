import os

import allure
import pytest
from file_helper import generate_file, generate_file_with_content
from s3_helper import set_bucket_versioning

from steps import s3_gate_bucket, s3_gate_object
from steps.s3_gate_base import TestS3GateBase


def pytest_generate_tests(metafunc):
    if "s3_client" in metafunc.fixturenames:
        metafunc.parametrize("s3_client", ["aws cli", "boto3"], indirect=True)


@pytest.mark.sanity
@pytest.mark.s3_gate
@pytest.mark.s3_gate_versioning
class TestS3GateVersioning(TestS3GateBase):
    @staticmethod
    def object_key_from_file_path(full_path: str) -> str:
        return os.path.basename(full_path)

    @allure.title("Test S3: try to disable versioning")
    def test_s3_version_off(self):

        bucket = s3_gate_bucket.create_bucket_s3(self.s3_client, True)
        with pytest.raises(Exception):
            set_bucket_versioning(self.s3_client, bucket, s3_gate_bucket.VersioningStatus.SUSPENDED)

    @allure.title("Test S3: Enable and disable versioning")
    def test_s3_version(self, simple_object_size):
        file_path = generate_file(simple_object_size)
        file_name = self.object_key_from_file_path(file_path)
        bucket_objects = [file_name]
        bucket = s3_gate_bucket.create_bucket_s3(self.s3_client, False)
        set_bucket_versioning(self.s3_client, bucket, s3_gate_bucket.VersioningStatus.SUSPENDED)

        with allure.step("Put object into bucket"):
            s3_gate_object.put_object_s3(self.s3_client, bucket, file_path)
            objects_list = s3_gate_object.list_objects_s3(self.s3_client, bucket)
            assert (
                objects_list == bucket_objects
            ), f"Expected list with single objects in bucket, got {objects_list}"
            object_version = s3_gate_object.list_objects_versions_s3(self.s3_client, bucket)
            actual_version = [
                version.get("VersionId")
                for version in object_version
                if version.get("Key") == file_name
            ]
            assert actual_version == [
                "null"
            ], f"Expected version is null in list-object-versions, got {object_version}"
            object_0 = s3_gate_object.head_object_s3(self.s3_client, bucket, file_name)
            assert (
                object_0.get("VersionId") == "null"
            ), f"Expected version is null in head-object, got {object_0.get('VersionId')}"

        set_bucket_versioning(self.s3_client, bucket, s3_gate_bucket.VersioningStatus.ENABLED)

        with allure.step("Put several versions of object into bucket"):
            version_id_1 = s3_gate_object.put_object_s3(self.s3_client, bucket, file_path)
            file_name_1 = generate_file_with_content(simple_object_size, file_path=file_path)
            version_id_2 = s3_gate_object.put_object_s3(self.s3_client, bucket, file_name_1)

        with allure.step("Check bucket shows all versions"):
            versions = s3_gate_object.list_objects_versions_s3(self.s3_client, bucket)
            obj_versions = [
                version.get("VersionId") for version in versions if version.get("Key") == file_name
            ]
            assert (
                obj_versions.sort() == [version_id_1, version_id_2, "null"].sort()
            ), f"Expected object has versions: {version_id_1, version_id_2, 'null'}"

        with allure.step("Get object"):
            object_1 = s3_gate_object.get_object_s3(
                self.s3_client, bucket, file_name, full_output=True
            )
            assert (
                object_1.get("VersionId") == version_id_2
            ), f"Get object with version {version_id_2}"

        with allure.step("Get first version of object"):
            object_2 = s3_gate_object.get_object_s3(
                self.s3_client, bucket, file_name, version_id_1, full_output=True
            )
            assert (
                object_2.get("VersionId") == version_id_1
            ), f"Get object with version {version_id_1}"

        with allure.step("Get second version of object"):
            object_3 = s3_gate_object.get_object_s3(
                self.s3_client, bucket, file_name, version_id_2, full_output=True
            )
            assert (
                object_3.get("VersionId") == version_id_2
            ), f"Get object with version {version_id_2}"
