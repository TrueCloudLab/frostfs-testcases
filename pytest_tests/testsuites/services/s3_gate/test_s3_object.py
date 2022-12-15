import os
import string
import uuid
from datetime import datetime, timedelta
from random import choices, sample

import allure
import pytest
from aws_cli_client import AwsCliClient
from common import ASSETS_DIR, FREE_STORAGE, WALLET_PASS
from data_formatters import get_wallet_public_key
from file_helper import concat_files, generate_file, generate_file_with_content, get_file_hash
from neofs_testlib.utils.wallet import init_wallet
from python_keywords.payment_neogo import deposit_gas, transfer_gas
from s3_helper import assert_object_lock_mode, check_objects_in_bucket, set_bucket_versioning

from steps import s3_gate_bucket, s3_gate_object
from steps.s3_gate_base import TestS3GateBase


def pytest_generate_tests(metafunc):
    if "s3_client" in metafunc.fixturenames:
        metafunc.parametrize("s3_client", ["aws cli", "boto3"], indirect=True)


@pytest.mark.sanity
@pytest.mark.s3_gate
@pytest.mark.s3_gate_object
class TestS3GateObject(TestS3GateBase):
    @staticmethod
    def object_key_from_file_path(full_path: str) -> str:
        return os.path.basename(full_path)

    @allure.title("Test S3: Copy object")
    def test_s3_copy_object(self, two_buckets, simple_object_size):
        file_path = generate_file(simple_object_size)
        file_name = self.object_key_from_file_path(file_path)
        bucket_1_objects = [file_name]

        bucket_1, bucket_2 = two_buckets

        objects_list = s3_gate_object.list_objects_s3(self.s3_client, bucket_1)
        assert not objects_list, f"Expected empty bucket, got {objects_list}"

        with allure.step("Put object into one bucket"):
            s3_gate_object.put_object_s3(self.s3_client, bucket_1, file_path)

        with allure.step("Copy one object into the same bucket"):
            copy_obj_path = s3_gate_object.copy_object_s3(self.s3_client, bucket_1, file_name)
            bucket_1_objects.append(copy_obj_path)
            check_objects_in_bucket(self.s3_client, bucket_1, bucket_1_objects)

        objects_list = s3_gate_object.list_objects_s3(self.s3_client, bucket_2)
        assert not objects_list, f"Expected empty bucket, got {objects_list}"

        with allure.step("Copy object from first bucket into second"):
            copy_obj_path_b2 = s3_gate_object.copy_object_s3(
                self.s3_client, bucket_1, file_name, bucket_dst=bucket_2
            )
            check_objects_in_bucket(self.s3_client, bucket_1, expected_objects=bucket_1_objects)
            check_objects_in_bucket(self.s3_client, bucket_2, expected_objects=[copy_obj_path_b2])

        with allure.step("Check copied object has the same content"):
            got_copied_file_b2 = s3_gate_object.get_object_s3(
                self.s3_client, bucket_2, copy_obj_path_b2
            )
            assert get_file_hash(file_path) == get_file_hash(
                got_copied_file_b2
            ), "Hashes must be the same"

        with allure.step("Delete one object from first bucket"):
            s3_gate_object.delete_object_s3(self.s3_client, bucket_1, file_name)
            bucket_1_objects.remove(file_name)
            check_objects_in_bucket(self.s3_client, bucket_1, expected_objects=bucket_1_objects)
            check_objects_in_bucket(self.s3_client, bucket_2, expected_objects=[copy_obj_path_b2])

        with allure.step("Copy one object into the same bucket"):
            with pytest.raises(Exception):
                s3_gate_object.copy_object_s3(self.s3_client, bucket_1, file_name)

    @allure.title("Test S3: Copy version of object")
    def test_s3_copy_version_object(self, two_buckets, simple_object_size):
        version_1_content = "Version 1"
        file_name_simple = generate_file_with_content(simple_object_size, content=version_1_content)
        obj_key = os.path.basename(file_name_simple)

        bucket_1, bucket_2 = two_buckets
        set_bucket_versioning(self.s3_client, bucket_1, s3_gate_bucket.VersioningStatus.ENABLED)

        with allure.step("Put object into bucket"):
            s3_gate_object.put_object_s3(self.s3_client, bucket_1, file_name_simple)
            bucket_1_objects = [obj_key]
            check_objects_in_bucket(self.s3_client, bucket_1, [obj_key])

        with allure.step("Copy one object into the same bucket"):
            copy_obj_path = s3_gate_object.copy_object_s3(self.s3_client, bucket_1, obj_key)
            bucket_1_objects.append(copy_obj_path)
            check_objects_in_bucket(self.s3_client, bucket_1, bucket_1_objects)

        set_bucket_versioning(self.s3_client, bucket_2, s3_gate_bucket.VersioningStatus.ENABLED)
        with allure.step("Copy object from first bucket into second"):
            copy_obj_path_b2 = s3_gate_object.copy_object_s3(
                self.s3_client, bucket_1, obj_key, bucket_dst=bucket_2
            )
            check_objects_in_bucket(self.s3_client, bucket_1, expected_objects=bucket_1_objects)
            check_objects_in_bucket(self.s3_client, bucket_2, expected_objects=[copy_obj_path_b2])

        with allure.step("Delete one object from first bucket and check object in bucket"):
            s3_gate_object.delete_object_s3(self.s3_client, bucket_1, obj_key)
            bucket_1_objects.remove(obj_key)
            check_objects_in_bucket(self.s3_client, bucket_1, expected_objects=bucket_1_objects)

        with allure.step("Copy one object into the same bucket"):
            with pytest.raises(Exception):
                s3_gate_object.copy_object_s3(self.s3_client, bucket_1, obj_key)

    @allure.title("Test S3: Checking copy with acl")
    def test_s3_copy_acl(self, bucket, simple_object_size):
        version_1_content = "Version 1"
        file_name_simple = generate_file_with_content(simple_object_size, content=version_1_content)
        obj_key = os.path.basename(file_name_simple)

        set_bucket_versioning(self.s3_client, bucket, s3_gate_bucket.VersioningStatus.ENABLED)

        with allure.step("Put several versions of object into bucket"):
            version_id_1 = s3_gate_object.put_object_s3(self.s3_client, bucket, file_name_simple)
            check_objects_in_bucket(self.s3_client, bucket, [obj_key])

        with allure.step("Copy object and check acl attribute"):
            copy_obj_path = s3_gate_object.copy_object_s3(
                self.s3_client, bucket, obj_key, ACL="public-read-write"
            )
            obj_acl = s3_gate_object.get_object_acl_s3(self.s3_client, bucket, copy_obj_path)
            for control in obj_acl:
                assert (
                    control.get("Permission") == "FULL_CONTROL"
                ), "Permission for all groups is FULL_CONTROL"

    @allure.title("Test S3: Copy object with metadata")
    def test_s3_copy_metadate(self, bucket, simple_object_size):
        object_metadata = {f"{uuid.uuid4()}": f"{uuid.uuid4()}"}
        file_path = generate_file(simple_object_size)
        file_name = self.object_key_from_file_path(file_path)
        bucket_1_objects = [file_name]

        set_bucket_versioning(self.s3_client, bucket, s3_gate_bucket.VersioningStatus.ENABLED)

        with allure.step("Put object into bucket"):
            s3_gate_object.put_object_s3(
                self.s3_client, bucket, file_path, Metadata=object_metadata
            )
            bucket_1_objects = [file_name]
            check_objects_in_bucket(self.s3_client, bucket, bucket_1_objects)

        with allure.step("Copy one object"):
            copy_obj_path = s3_gate_object.copy_object_s3(self.s3_client, bucket, file_name)
            bucket_1_objects.append(copy_obj_path)
            check_objects_in_bucket(self.s3_client, bucket, bucket_1_objects)
            obj_head = s3_gate_object.head_object_s3(self.s3_client, bucket, copy_obj_path)
            assert (
                obj_head.get("Metadata") == object_metadata
            ), f"Metadata must be {object_metadata}"

        with allure.step("Copy one object with metadata"):
            copy_obj_path = s3_gate_object.copy_object_s3(
                self.s3_client, bucket, file_name, metadata_directive="COPY"
            )
            bucket_1_objects.append(copy_obj_path)
            obj_head = s3_gate_object.head_object_s3(self.s3_client, bucket, copy_obj_path)
            assert (
                obj_head.get("Metadata") == object_metadata
            ), f"Metadata must be {object_metadata}"

        with allure.step("Copy one object with new metadata"):
            object_metadata_1 = {f"{uuid.uuid4()}": f"{uuid.uuid4()}"}
            copy_obj_path = s3_gate_object.copy_object_s3(
                self.s3_client,
                bucket,
                file_name,
                metadata_directive="REPLACE",
                metadata=object_metadata_1,
            )
            bucket_1_objects.append(copy_obj_path)
            obj_head = s3_gate_object.head_object_s3(self.s3_client, bucket, copy_obj_path)
            assert (
                obj_head.get("Metadata") == object_metadata_1
            ), f"Metadata must be {object_metadata_1}"

    @allure.title("Test S3: Copy object with tagging")
    def test_s3_copy_tagging(self, bucket, simple_object_size):
        object_tagging = [(f"{uuid.uuid4()}", f"{uuid.uuid4()}")]
        file_path = generate_file(simple_object_size)
        file_name_simple = self.object_key_from_file_path(file_path)
        bucket_1_objects = [file_name_simple]

        set_bucket_versioning(self.s3_client, bucket, s3_gate_bucket.VersioningStatus.ENABLED)

        with allure.step("Put several versions of object into bucket"):
            s3_gate_object.put_object_s3(self.s3_client, bucket, file_path)
            version_id_1 = s3_gate_object.put_object_tagging(
                self.s3_client, bucket, file_name_simple, tags=object_tagging
            )
            bucket_1_objects = [file_name_simple]
            check_objects_in_bucket(self.s3_client, bucket, bucket_1_objects)

        with allure.step("Copy one object without tag"):
            copy_obj_path = s3_gate_object.copy_object_s3(self.s3_client, bucket, file_name_simple)
            got_tags = s3_gate_object.get_object_tagging(self.s3_client, bucket, copy_obj_path)
            assert got_tags, f"Expected tags, got {got_tags}"
            expected_tags = [{"Key": key, "Value": value} for key, value in object_tagging]
            for tag in expected_tags:
                assert tag in got_tags, f"Expected tag {tag} in {got_tags}"

        with allure.step("Copy one object with tag"):
            copy_obj_path_1 = s3_gate_object.copy_object_s3(
                self.s3_client, bucket, file_name_simple, tagging_directive="COPY"
            )
            got_tags = s3_gate_object.get_object_tagging(self.s3_client, bucket, copy_obj_path_1)
            assert got_tags, f"Expected tags, got {got_tags}"
            expected_tags = [{"Key": key, "Value": value} for key, value in object_tagging]
            for tag in expected_tags:
                assert tag in got_tags, f"Expected tag {tag} in {got_tags}"

        with allure.step("Copy one object with new tag"):
            tag_key = "tag1"
            tag_value = uuid.uuid4()
            new_tag = f"{tag_key}={tag_value}"
            copy_obj_path = s3_gate_object.copy_object_s3(
                self.s3_client,
                bucket,
                file_name_simple,
                tagging_directive="REPLACE",
                tagging=new_tag,
            )
            got_tags = s3_gate_object.get_object_tagging(self.s3_client, bucket, copy_obj_path)
            assert got_tags, f"Expected tags, got {got_tags}"
            expected_tags = [{"Key": tag_key, "Value": str(tag_value)}]
            for tag in expected_tags:
                assert tag in got_tags, f"Expected tag {tag} in {got_tags}"

    @allure.title("Test S3: Delete version of object")
    def test_s3_delete_versioning(self, bucket, complex_object_size, simple_object_size):
        version_1_content = "Version 1"
        version_2_content = "Version 2"
        file_name_simple = generate_file_with_content(simple_object_size, content=version_1_content)

        obj_key = os.path.basename(file_name_simple)
        set_bucket_versioning(self.s3_client, bucket, s3_gate_bucket.VersioningStatus.ENABLED)

        with allure.step("Put several versions of object into bucket"):
            version_id_1 = s3_gate_object.put_object_s3(self.s3_client, bucket, file_name_simple)
            file_name_1 = generate_file_with_content(
                simple_object_size, file_path=file_name_simple, content=version_2_content
            )
            version_id_2 = s3_gate_object.put_object_s3(self.s3_client, bucket, file_name_1)

        with allure.step("Check bucket shows all versions"):
            versions = s3_gate_object.list_objects_versions_s3(self.s3_client, bucket)
            obj_versions = {
                version.get("VersionId") for version in versions if version.get("Key") == obj_key
            }
            assert obj_versions == {
                version_id_1,
                version_id_2,
            }, f"Expected object has versions: {version_id_1, version_id_2}"

        with allure.step("Delete 1 version of object"):
            delete_obj = s3_gate_object.delete_object_s3(
                self.s3_client, bucket, obj_key, version_id=version_id_1
            )
            versions = s3_gate_object.list_objects_versions_s3(self.s3_client, bucket)
            obj_versions = {
                version.get("VersionId") for version in versions if version.get("Key") == obj_key
            }
            assert obj_versions == {version_id_2}, f"Expected object has versions: {version_id_2}"
            assert not "DeleteMarkers" in delete_obj.keys(), "Delete markes not found"

        with allure.step("Delete second version of object"):
            delete_obj = s3_gate_object.delete_object_s3(
                self.s3_client, bucket, obj_key, version_id=version_id_2
            )
            versions = s3_gate_object.list_objects_versions_s3(self.s3_client, bucket)
            obj_versions = {
                version.get("VersionId") for version in versions if version.get("Key") == obj_key
            }
            assert not obj_versions, "Expected object not found"
            assert not "DeleteMarkers" in delete_obj.keys(), "Delete markes not found"

        with allure.step("Put new object into bucket"):
            file_name_simple = generate_file(complex_object_size)
            obj_key = os.path.basename(file_name_simple)
            version_id = s3_gate_object.put_object_s3(self.s3_client, bucket, file_name_simple)

        with allure.step("Delete last object"):
            delete_obj = s3_gate_object.delete_object_s3(self.s3_client, bucket, obj_key)
            versions = s3_gate_object.list_objects_versions_s3(self.s3_client, bucket, True)
            assert versions.get("DeleteMarkers", None), f"Expected delete Marker"
            assert "DeleteMarker" in delete_obj.keys(), f"Expected delete Marker"

    @allure.title("Test S3: bulk delete version of object")
    def test_s3_bulk_delete_versioning(self, bucket, simple_object_size):
        version_1_content = "Version 1"
        version_2_content = "Version 2"
        version_3_content = "Version 3"
        version_4_content = "Version 4"
        file_name_1 = generate_file_with_content(simple_object_size, content=version_1_content)

        obj_key = os.path.basename(file_name_1)
        set_bucket_versioning(self.s3_client, bucket, s3_gate_bucket.VersioningStatus.ENABLED)

        with allure.step("Put several versions of object into bucket"):
            version_id_1 = s3_gate_object.put_object_s3(self.s3_client, bucket, file_name_1)
            file_name_2 = generate_file_with_content(
                simple_object_size, file_path=file_name_1, content=version_2_content
            )
            version_id_2 = s3_gate_object.put_object_s3(self.s3_client, bucket, file_name_2)
            file_name_3 = generate_file_with_content(
                simple_object_size, file_path=file_name_1, content=version_3_content
            )
            version_id_3 = s3_gate_object.put_object_s3(self.s3_client, bucket, file_name_3)
            file_name_4 = generate_file_with_content(
                simple_object_size, file_path=file_name_1, content=version_4_content
            )
            version_id_4 = s3_gate_object.put_object_s3(self.s3_client, bucket, file_name_4)
            version_ids = {version_id_1, version_id_2, version_id_3, version_id_4}

        with allure.step("Check bucket shows all versions"):
            versions = s3_gate_object.list_objects_versions_s3(self.s3_client, bucket)
            obj_versions = {
                version.get("VersionId") for version in versions if version.get("Key") == obj_key
            }
            assert obj_versions == version_ids, f"Expected object has versions: {version_ids}"

        with allure.step("Delete two objects from bucket one by one"):
            version_to_delete_b1 = sample(
                [version_id_1, version_id_2, version_id_3, version_id_4], k=2
            )
            version_to_save = list(set(version_ids) - set(version_to_delete_b1))
            for ver in version_to_delete_b1:
                s3_gate_object.delete_object_s3(self.s3_client, bucket, obj_key, ver)

        with allure.step("Check bucket shows all versions"):
            versions = s3_gate_object.list_objects_versions_s3(self.s3_client, bucket)
            obj_versions = [
                version.get("VersionId") for version in versions if version.get("Key") == obj_key
            ]
            assert (
                obj_versions.sort() == version_to_save.sort()
            ), f"Expected object has versions: {version_to_save}"

    @allure.title("Test S3: Get versions of object")
    def test_s3_get_versioning(self, bucket, simple_object_size):
        version_1_content = "Version 1"
        version_2_content = "Version 2"
        file_name_simple = generate_file_with_content(simple_object_size, content=version_1_content)

        obj_key = os.path.basename(file_name_simple)
        set_bucket_versioning(self.s3_client, bucket, s3_gate_bucket.VersioningStatus.ENABLED)
        with allure.step("Put several versions of object into bucket"):
            version_id_1 = s3_gate_object.put_object_s3(self.s3_client, bucket, file_name_simple)
            file_name_1 = generate_file_with_content(
                simple_object_size, file_path=file_name_simple, content=version_2_content
            )
            version_id_2 = s3_gate_object.put_object_s3(self.s3_client, bucket, file_name_1)

        with allure.step("Get first version of object"):
            object_1 = s3_gate_object.get_object_s3(
                self.s3_client, bucket, obj_key, version_id_1, full_output=True
            )
            assert (
                object_1.get("VersionId") == version_id_1
            ), f"Get object with version {version_id_1}"

        with allure.step("Get second version of object"):
            object_2 = s3_gate_object.get_object_s3(
                self.s3_client, bucket, obj_key, version_id_2, full_output=True
            )
            assert (
                object_2.get("VersionId") == version_id_2
            ), f"Get object with version {version_id_2}"

        with allure.step("Get object"):
            object_3 = s3_gate_object.get_object_s3(
                self.s3_client, bucket, obj_key, full_output=True
            )
            assert (
                object_3.get("VersionId") == version_id_2
            ), f"Get object with version {version_id_2}"

    @allure.title("Test S3: Get range")
    def test_s3_get_range(self, bucket, complex_object_size: int, simple_object_size: int):
        file_path = generate_file(complex_object_size)
        file_name = self.object_key_from_file_path(file_path)
        file_hash = get_file_hash(file_path)
        set_bucket_versioning(self.s3_client, bucket, s3_gate_bucket.VersioningStatus.ENABLED)
        with allure.step("Put several versions of object into bucket"):
            version_id_1 = s3_gate_object.put_object_s3(self.s3_client, bucket, file_path)
            file_name_1 = generate_file_with_content(simple_object_size, file_path=file_path)
            version_id_2 = s3_gate_object.put_object_s3(self.s3_client, bucket, file_name_1)

        with allure.step("Get first version of object"):
            object_1_part_1 = s3_gate_object.get_object_s3(
                self.s3_client,
                bucket,
                file_name,
                version_id_1,
                range=[0, int(complex_object_size / 3)],
            )
            object_1_part_2 = s3_gate_object.get_object_s3(
                self.s3_client,
                bucket,
                file_name,
                version_id_1,
                range=[int(complex_object_size / 3) + 1, 2 * int(complex_object_size / 3)],
            )
            object_1_part_3 = s3_gate_object.get_object_s3(
                self.s3_client,
                bucket,
                file_name,
                version_id_1,
                range=[2 * int(complex_object_size / 3) + 1, complex_object_size],
            )
            con_file = concat_files([object_1_part_1, object_1_part_2, object_1_part_3])
            assert get_file_hash(con_file) == file_hash, "Hashes must be the same"

        with allure.step("Get second version of object"):
            object_2_part_1 = s3_gate_object.get_object_s3(
                self.s3_client,
                bucket,
                file_name,
                version_id_2,
                range=[0, int(simple_object_size / 3)],
            )
            object_2_part_2 = s3_gate_object.get_object_s3(
                self.s3_client,
                bucket,
                file_name,
                version_id_2,
                range=[int(simple_object_size / 3) + 1, 2 * int(simple_object_size / 3)],
            )
            object_2_part_3 = s3_gate_object.get_object_s3(
                self.s3_client,
                bucket,
                file_name,
                version_id_2,
                range=[2 * int(simple_object_size / 3) + 1, simple_object_size],
            )
            con_file_1 = concat_files([object_2_part_1, object_2_part_2, object_2_part_3])
            assert get_file_hash(con_file_1) == get_file_hash(
                file_name_1
            ), "Hashes must be the same"

        with allure.step("Get object"):
            object_3_part_1 = s3_gate_object.get_object_s3(
                self.s3_client, bucket, file_name, range=[0, int(simple_object_size / 3)]
            )
            object_3_part_2 = s3_gate_object.get_object_s3(
                self.s3_client,
                bucket,
                file_name,
                range=[int(simple_object_size / 3) + 1, 2 * int(simple_object_size / 3)],
            )
            object_3_part_3 = s3_gate_object.get_object_s3(
                self.s3_client,
                bucket,
                file_name,
                range=[2 * int(simple_object_size / 3) + 1, simple_object_size],
            )
            con_file = concat_files([object_3_part_1, object_3_part_2, object_3_part_3])
            assert get_file_hash(con_file) == get_file_hash(file_name_1), "Hashes must be the same"

    @allure.title("Test S3: Copy object with metadata")
    @pytest.mark.smoke
    def test_s3_head_object(self, bucket, complex_object_size, simple_object_size):
        object_metadata = {f"{uuid.uuid4()}": f"{uuid.uuid4()}"}
        file_path = generate_file(complex_object_size)
        file_name = self.object_key_from_file_path(file_path)
        set_bucket_versioning(self.s3_client, bucket, s3_gate_bucket.VersioningStatus.ENABLED)

        with allure.step("Put several versions of object into bucket"):
            version_id_1 = s3_gate_object.put_object_s3(
                self.s3_client, bucket, file_path, Metadata=object_metadata
            )
            file_name_1 = generate_file_with_content(simple_object_size, file_path=file_path)
            version_id_2 = s3_gate_object.put_object_s3(self.s3_client, bucket, file_name_1)

        with allure.step("Get head of first version of object"):
            response = s3_gate_object.head_object_s3(self.s3_client, bucket, file_name)
            assert "LastModified" in response, "Expected LastModified field"
            assert "ETag" in response, "Expected ETag field"
            assert response.get("Metadata") == {}, "Expected Metadata empty"
            assert (
                response.get("VersionId") == version_id_2
            ), f"Expected VersionId is {version_id_2}"
            assert response.get("ContentLength") != 0, "Expected ContentLength is not zero"

        with allure.step("Get head ob first version of object"):
            response = s3_gate_object.head_object_s3(
                self.s3_client, bucket, file_name, version_id=version_id_1
            )
            assert "LastModified" in response, "Expected LastModified field"
            assert "ETag" in response, "Expected ETag field"
            assert (
                response.get("Metadata") == object_metadata
            ), f"Expected Metadata is {object_metadata}"
            assert (
                response.get("VersionId") == version_id_1
            ), f"Expected VersionId is {version_id_1}"
            assert response.get("ContentLength") != 0, "Expected ContentLength is not zero"

    @allure.title("Test S3: list of object with versions")
    @pytest.mark.parametrize("list_type", ["v1", "v2"])
    def test_s3_list_object(self, list_type: str, bucket, complex_object_size):
        file_path_1 = generate_file(complex_object_size)
        file_name = self.object_key_from_file_path(file_path_1)
        file_path_2 = generate_file(complex_object_size)
        file_name_2 = self.object_key_from_file_path(file_path_2)

        set_bucket_versioning(self.s3_client, bucket, s3_gate_bucket.VersioningStatus.ENABLED)
        with allure.step("Put several versions of object into bucket"):
            s3_gate_object.put_object_s3(self.s3_client, bucket, file_path_1)
            s3_gate_object.put_object_s3(self.s3_client, bucket, file_path_2)

        with allure.step("Get list of object"):
            if list_type == "v1":
                list_obj = s3_gate_object.list_objects_s3(self.s3_client, bucket)
            elif list_type == "v2":
                list_obj = s3_gate_object.list_objects_s3_v2(self.s3_client, bucket)
            assert len(list_obj) == 2, f"bucket have 2 objects"
            assert (
                list_obj.sort() == [file_name, file_name_2].sort()
            ), f"bucket have object key {file_name, file_name_2}"

        with allure.step("Delete object"):
            delete_obj = s3_gate_object.delete_object_s3(self.s3_client, bucket, file_name)
            if list_type == "v1":
                list_obj_1 = s3_gate_object.list_objects_s3(
                    self.s3_client, bucket, full_output=True
                )
            elif list_type == "v2":
                list_obj_1 = s3_gate_object.list_objects_s3_v2(
                    self.s3_client, bucket, full_output=True
                )
            contents = list_obj_1.get("Contents", [])
            assert len(contents) == 1, f"bucket have only 1 object"
            assert contents[0].get("Key") == file_name_2, f"bucket has object key {file_name_2}"
            assert "DeleteMarker" in delete_obj.keys(), f"Expected delete Marker"

    @allure.title("Test S3: put object")
    def test_s3_put_object(self, bucket, complex_object_size, simple_object_size):
        file_path_1 = generate_file(complex_object_size)
        file_name = self.object_key_from_file_path(file_path_1)
        object_1_metadata = {f"{uuid.uuid4()}": f"{uuid.uuid4()}"}
        tag_key_1 = "tag1"
        tag_value_1 = uuid.uuid4()
        tag_1 = f"{tag_key_1}={tag_value_1}"
        object_2_metadata = {f"{uuid.uuid4()}": f"{uuid.uuid4()}"}
        tag_key_2 = "tag2"
        tag_value_2 = uuid.uuid4()
        tag_2 = f"{tag_key_2}={tag_value_2}"
        set_bucket_versioning(self.s3_client, bucket, s3_gate_bucket.VersioningStatus.SUSPENDED)

        with allure.step("Put first object into bucket"):
            s3_gate_object.put_object_s3(
                self.s3_client, bucket, file_path_1, Metadata=object_1_metadata, Tagging=tag_1
            )
            obj_head = s3_gate_object.head_object_s3(self.s3_client, bucket, file_name)
            assert obj_head.get("Metadata") == object_1_metadata, "Matadata must be the same"
            got_tags = s3_gate_object.get_object_tagging(self.s3_client, bucket, file_name)
            assert got_tags, f"Expected tags, got {got_tags}"
            assert got_tags == [
                {"Key": tag_key_1, "Value": str(tag_value_1)}
            ], "Tags must be the same"

        with allure.step("Rewrite file into bucket"):
            file_path_2 = generate_file_with_content(simple_object_size, file_path=file_path_1)
            s3_gate_object.put_object_s3(
                self.s3_client, bucket, file_path_2, Metadata=object_2_metadata, Tagging=tag_2
            )
            obj_head = s3_gate_object.head_object_s3(self.s3_client, bucket, file_name)
            assert obj_head.get("Metadata") == object_2_metadata, "Matadata must be the same"
            got_tags_1 = s3_gate_object.get_object_tagging(self.s3_client, bucket, file_name)
            assert got_tags_1, f"Expected tags, got {got_tags_1}"
            assert got_tags_1 == [
                {"Key": tag_key_2, "Value": str(tag_value_2)}
            ], "Tags must be the same"

        set_bucket_versioning(self.s3_client, bucket, s3_gate_bucket.VersioningStatus.ENABLED)

        file_path_3 = generate_file(complex_object_size)
        file_hash = get_file_hash(file_path_3)
        file_name_3 = self.object_key_from_file_path(file_path_3)
        object_3_metadata = {f"{uuid.uuid4()}": f"{uuid.uuid4()}"}
        tag_key_3 = "tag3"
        tag_value_3 = uuid.uuid4()
        tag_3 = f"{tag_key_3}={tag_value_3}"

        with allure.step("Put third object into bucket"):
            version_id_1 = s3_gate_object.put_object_s3(
                self.s3_client, bucket, file_path_3, Metadata=object_3_metadata, Tagging=tag_3
            )
            obj_head_3 = s3_gate_object.head_object_s3(self.s3_client, bucket, file_name_3)
            assert obj_head_3.get("Metadata") == object_3_metadata, "Matadata must be the same"
            got_tags_3 = s3_gate_object.get_object_tagging(self.s3_client, bucket, file_name_3)
            assert got_tags_3, f"Expected tags, got {got_tags_3}"
            assert got_tags_3 == [
                {"Key": tag_key_3, "Value": str(tag_value_3)}
            ], "Tags must be the same"

        with allure.step("Put new version of file into bucket"):
            file_path_4 = generate_file_with_content(simple_object_size, file_path=file_path_3)
            version_id_2 = s3_gate_object.put_object_s3(self.s3_client, bucket, file_path_4)
            versions = s3_gate_object.list_objects_versions_s3(self.s3_client, bucket)
            obj_versions = {
                version.get("VersionId")
                for version in versions
                if version.get("Key") == file_name_3
            }
            assert obj_versions == {
                version_id_1,
                version_id_2,
            }, f"Expected object has versions: {version_id_1, version_id_2}"
            got_tags_4 = s3_gate_object.get_object_tagging(self.s3_client, bucket, file_name_3)
            assert not got_tags_4, f"No expected tags"

        with allure.step("Get object"):
            object_3 = s3_gate_object.get_object_s3(
                self.s3_client, bucket, file_name_3, full_output=True
            )
            assert (
                object_3.get("VersionId") == version_id_2
            ), f"get object with version {version_id_2}"
            object_3 = s3_gate_object.get_object_s3(self.s3_client, bucket, file_name_3)
            assert get_file_hash(file_path_4) == get_file_hash(object_3), "Hashes must be the same"

        with allure.step("Get first version of object"):
            object_4 = s3_gate_object.get_object_s3(
                self.s3_client, bucket, file_name_3, version_id_1, full_output=True
            )
            assert (
                object_4.get("VersionId") == version_id_1
            ), f"get object with version {version_id_1}"
            object_4 = s3_gate_object.get_object_s3(
                self.s3_client, bucket, file_name_3, version_id_1
            )
            assert file_hash == get_file_hash(object_4), "Hashes must be the same"
            obj_head_3 = s3_gate_object.head_object_s3(
                self.s3_client, bucket, file_name_3, version_id_1
            )
            assert obj_head_3.get("Metadata") == object_3_metadata, "Matadata must be the same"
            got_tags_3 = s3_gate_object.get_object_tagging(
                self.s3_client, bucket, file_name_3, version_id_1
            )
            assert got_tags_3, f"Expected tags, got {got_tags_3}"
            assert got_tags_3 == [
                {"Key": tag_key_3, "Value": str(tag_value_3)}
            ], "Tags must be the same"

    @pytest.fixture
    def prepare_two_wallets(self, default_wallet, client_shell):
        self.main_wallet = default_wallet
        self.main_public_key = get_wallet_public_key(self.main_wallet, WALLET_PASS)
        self.other_wallet = os.path.join(os.getcwd(), ASSETS_DIR, f"{str(uuid.uuid4())}.json")
        init_wallet(self.other_wallet, WALLET_PASS)
        self.other_public_key = get_wallet_public_key(self.other_wallet, WALLET_PASS)

        if not FREE_STORAGE:
            main_chain = self.cluster.main_chain_nodes[0]
            deposit = 30
            transfer_gas(
                shell=client_shell,
                amount=deposit + 1,
                main_chain=main_chain,
                wallet_to_path=self.other_wallet,
                wallet_to_password=WALLET_PASS,
            )
            deposit_gas(
                shell=client_shell,
                main_chain=main_chain,
                amount=deposit,
                wallet_from_path=self.other_wallet,
                wallet_from_password=WALLET_PASS,
            )

    @allure.title("Test S3: put object with ACL")
    @pytest.mark.parametrize("bucket_versioning", ["ENABLED", "SUSPENDED"])
    def test_s3_put_object_acl(
        self,
        prepare_two_wallets,
        bucket_versioning,
        bucket,
        complex_object_size,
        simple_object_size,
    ):
        file_path_1 = generate_file(complex_object_size)
        file_name = self.object_key_from_file_path(file_path_1)
        if bucket_versioning == "ENABLED":
            status = s3_gate_bucket.VersioningStatus.ENABLED
        elif bucket_versioning == "SUSPENDED":
            status = s3_gate_bucket.VersioningStatus.SUSPENDED
        set_bucket_versioning(self.s3_client, bucket, status)

        with allure.step("Put object with acl private"):
            s3_gate_object.put_object_s3(self.s3_client, bucket, file_path_1, ACL="private")
            obj_acl = s3_gate_object.get_object_acl_s3(self.s3_client, bucket, file_name)
            obj_permission = [permission.get("Permission") for permission in obj_acl]
            assert obj_permission == ["FULL_CONTROL"], "Permission for all groups is FULL_CONTROL"
            object_1 = s3_gate_object.get_object_s3(self.s3_client, bucket, file_name)
            assert get_file_hash(file_path_1) == get_file_hash(object_1), "Hashes must be the same"

        with allure.step("Put object with acl public-read"):
            file_path_2 = generate_file_with_content(simple_object_size, file_path=file_path_1)
            s3_gate_object.put_object_s3(self.s3_client, bucket, file_path_2, ACL="public-read")
            obj_acl = s3_gate_object.get_object_acl_s3(self.s3_client, bucket, file_name)
            obj_permission = [permission.get("Permission") for permission in obj_acl]
            assert obj_permission == [
                "FULL_CONTROL",
                "FULL_CONTROL",
            ], "Permission for all groups is FULL_CONTROL"
            object_2 = s3_gate_object.get_object_s3(self.s3_client, bucket, file_name)
            assert get_file_hash(file_path_2) == get_file_hash(object_2), "Hashes must be the same"

        with allure.step("Put object with acl public-read-write"):
            file_path_3 = generate_file_with_content(simple_object_size, file_path=file_path_1)
            s3_gate_object.put_object_s3(
                self.s3_client, bucket, file_path_3, ACL="public-read-write"
            )
            obj_acl = s3_gate_object.get_object_acl_s3(self.s3_client, bucket, file_name)
            obj_permission = [permission.get("Permission") for permission in obj_acl]
            assert obj_permission == [
                "FULL_CONTROL",
                "FULL_CONTROL",
            ], "Permission for all groups is FULL_CONTROL"
            object_3 = s3_gate_object.get_object_s3(self.s3_client, bucket, file_name)
            assert get_file_hash(file_path_3) == get_file_hash(object_3), "Hashes must be the same"

        with allure.step("Put object with acl authenticated-read"):
            file_path_4 = generate_file_with_content(simple_object_size, file_path=file_path_1)
            s3_gate_object.put_object_s3(
                self.s3_client, bucket, file_path_4, ACL="authenticated-read"
            )
            obj_acl = s3_gate_object.get_object_acl_s3(self.s3_client, bucket, file_name)
            obj_permission = [permission.get("Permission") for permission in obj_acl]
            assert obj_permission == [
                "FULL_CONTROL",
                "FULL_CONTROL",
            ], "Permission for all groups is FULL_CONTROL"
            object_4 = s3_gate_object.get_object_s3(self.s3_client, bucket, file_name)
            assert get_file_hash(file_path_4) == get_file_hash(object_4), "Hashes must be the same"

        file_path_5 = generate_file(complex_object_size)
        file_name_5 = self.object_key_from_file_path(file_path_5)

        with allure.step("Put object with --grant-full-control id=mycanonicaluserid"):
            file_path_6 = generate_file_with_content(simple_object_size, file_path=file_path_5)
            s3_gate_object.put_object_s3(
                self.s3_client,
                bucket,
                file_path_6,
                GrantFullControl=f"id={self.other_public_key}",
            )
            obj_acl = s3_gate_object.get_object_acl_s3(self.s3_client, bucket, file_name_5)
            obj_permission = [permission.get("Permission") for permission in obj_acl]
            assert obj_permission == [
                "FULL_CONTROL",
                "FULL_CONTROL",
            ], "Permission for all groups is FULL_CONTROL"
            object_4 = s3_gate_object.get_object_s3(self.s3_client, bucket, file_name_5)
            assert get_file_hash(file_path_5) == get_file_hash(object_4), "Hashes must be the same"

        with allure.step(
            "Put object with --grant-read uri=http://acs.amazonaws.com/groups/global/AllUsers"
        ):
            file_path_7 = generate_file_with_content(simple_object_size, file_path=file_path_5)
            s3_gate_object.put_object_s3(
                self.s3_client,
                bucket,
                file_path_7,
                GrantRead="uri=http://acs.amazonaws.com/groups/global/AllUsers",
            )
            obj_acl = s3_gate_object.get_object_acl_s3(self.s3_client, bucket, file_name_5)
            obj_permission = [permission.get("Permission") for permission in obj_acl]
            assert obj_permission == [
                "FULL_CONTROL",
                "FULL_CONTROL",
            ], "Permission for all groups is FULL_CONTROL"
            object_7 = s3_gate_object.get_object_s3(self.s3_client, bucket, file_name_5)
            assert get_file_hash(file_path_7) == get_file_hash(object_7), "Hashes must be the same"

    @allure.title("Test S3: put object with lock-mode")
    def test_s3_put_object_lock_mode(self, complex_object_size, simple_object_size):

        file_path_1 = generate_file(complex_object_size)
        file_name = self.object_key_from_file_path(file_path_1)
        bucket = s3_gate_bucket.create_bucket_s3(self.s3_client, True)
        set_bucket_versioning(self.s3_client, bucket, s3_gate_bucket.VersioningStatus.ENABLED)

        with allure.step(
            "Put object with lock-mode GOVERNANCE lock-retain-until-date +1day, lock-legal-hold-status"
        ):
            date_obj = datetime.utcnow() + timedelta(days=1)
            s3_gate_object.put_object_s3(
                self.s3_client,
                bucket,
                file_path_1,
                ObjectLockMode="GOVERNANCE",
                ObjectLockRetainUntilDate=date_obj.strftime("%Y-%m-%dT%H:%M:%S"),
                ObjectLockLegalHoldStatus="OFF",
            )
            assert_object_lock_mode(
                self.s3_client, bucket, file_name, "GOVERNANCE", date_obj, "OFF"
            )

        with allure.step(
            "Put new version of object with [--object-lock-mode COMPLIANCE] и [--object-lock-retain-until-date +3days]"
        ):
            date_obj = datetime.utcnow() + timedelta(days=2)
            file_name_1 = generate_file_with_content(simple_object_size, file_path=file_path_1)
            s3_gate_object.put_object_s3(
                self.s3_client,
                bucket,
                file_path_1,
                ObjectLockMode="COMPLIANCE",
                ObjectLockRetainUntilDate=date_obj,
            )
            assert_object_lock_mode(
                self.s3_client, bucket, file_name, "COMPLIANCE", date_obj, "OFF"
            )

        with allure.step(
            "Put new version of object with [--object-lock-mode COMPLIANCE] и [--object-lock-retain-until-date +2days]"
        ):
            date_obj = datetime.utcnow() + timedelta(days=3)
            file_name_1 = generate_file_with_content(simple_object_size, file_path=file_path_1)
            s3_gate_object.put_object_s3(
                self.s3_client,
                bucket,
                file_path_1,
                ObjectLockMode="COMPLIANCE",
                ObjectLockRetainUntilDate=date_obj,
                ObjectLockLegalHoldStatus="ON",
            )
            assert_object_lock_mode(self.s3_client, bucket, file_name, "COMPLIANCE", date_obj, "ON")

        with allure.step("Put object with lock-mode"):
            with pytest.raises(
                Exception,
                match=r".*must both be supplied*",
            ):
                # x-amz-object-lock-retain-until-date and x-amz-object-lock-mode must both be supplied
                s3_gate_object.put_object_s3(
                    self.s3_client, bucket, file_path_1, ObjectLockMode="COMPLIANCE"
                )

        with allure.step("Put object with lock-mode and past date"):
            date_obj = datetime.utcnow() - timedelta(days=3)
            with pytest.raises(
                Exception,
                match=r".*until date must be in the future*",
            ):
                # The retain until date must be in the future
                s3_gate_object.put_object_s3(
                    self.s3_client,
                    bucket,
                    file_path_1,
                    ObjectLockMode="COMPLIANCE",
                    ObjectLockRetainUntilDate=date_obj,
                )

    @allure.title("Test S3 Sync directory")
    @pytest.mark.parametrize("sync_type", ["sync", "cp"])
    def test_s3_sync_dir(self, sync_type, bucket, simple_object_size):
        file_path_1 = os.path.join(os.getcwd(), ASSETS_DIR, "test_sync", "test_file_1")
        file_path_2 = os.path.join(os.getcwd(), ASSETS_DIR, "test_sync", "test_file_2")
        object_metadata = {f"{uuid.uuid4()}": f"{uuid.uuid4()}"}
        key_to_path = {"test_file_1": file_path_1, "test_file_2": file_path_2}

        if not isinstance(self.s3_client, AwsCliClient):
            pytest.skip("This test is not supported with boto3 client")

        generate_file_with_content(simple_object_size, file_path=file_path_1)
        generate_file_with_content(simple_object_size, file_path=file_path_2)
        set_bucket_versioning(self.s3_client, bucket, s3_gate_bucket.VersioningStatus.ENABLED)
        # TODO: return ACL, when https://github.com/nspcc-dev/neofs-s3-gw/issues/685 will be closed
        if sync_type == "sync":
            self.s3_client.sync(
                bucket_name=bucket,
                dir_path=os.path.dirname(file_path_1),
                # ACL="public-read-write",
                Metadata=object_metadata,
            )
        elif sync_type == "cp":
            self.s3_client.cp(
                bucket_name=bucket,
                dir_path=os.path.dirname(file_path_1),
                # ACL="public-read-write",
                Metadata=object_metadata,
            )

        with allure.step("Check objects are synced"):
            objects = s3_gate_object.list_objects_s3(self.s3_client, bucket)
            assert set(key_to_path.keys()) == set(
                objects
            ), f"Expected all abjects saved. Got {objects}"

        with allure.step("Check these are the same objects"):
            for obj_key in objects:
                got_object = s3_gate_object.get_object_s3(self.s3_client, bucket, obj_key)
                assert get_file_hash(got_object) == get_file_hash(
                    key_to_path.get(obj_key)
                ), "Expected hashes are the same"
                obj_head = s3_gate_object.head_object_s3(self.s3_client, bucket, obj_key)
                assert (
                    obj_head.get("Metadata") == object_metadata
                ), f"Metadata of object is {object_metadata}"
                # obj_acl = s3_gate_object.get_object_acl_s3(self.s3_client, bucket, obj_key)
                # obj_permission = [permission.get("Permission") for permission in obj_acl]
                # assert obj_permission == [
                #     "FULL_CONTROL",
                #     "FULL_CONTROL",
                # ], "Permission for all groups is FULL_CONTROL"

    @allure.title("Test S3 Put 10 nested level object")
    def test_s3_put_10_folder(self, bucket, temp_directory, simple_object_size):
        path = "/".join(["".join(choices(string.ascii_letters, k=3)) for _ in range(10)])
        file_path_1 = os.path.join(temp_directory, path, "test_file_1")
        generate_file_with_content(simple_object_size, file_path=file_path_1)
        file_name = self.object_key_from_file_path(file_path_1)
        objects_list = s3_gate_object.list_objects_s3(self.s3_client, bucket)
        assert not objects_list, f"Expected empty bucket, got {objects_list}"

        with allure.step("Put object"):
            s3_gate_object.put_object_s3(self.s3_client, bucket, file_path_1)
            check_objects_in_bucket(self.s3_client, bucket, [file_name])
