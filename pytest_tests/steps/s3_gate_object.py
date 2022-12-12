import logging
import os
import uuid
from time import sleep
from typing import Optional

import allure
import pytest
import urllib3
from aws_cli_client import AwsCliClient
from botocore.exceptions import ClientError
from cli_helpers import log_command_execution
from s3_gate_bucket import S3_SYNC_WAIT_TIME

##########################################################
# Disabling warnings on self-signed certificate which the
# boto library produces on requests to S3-gate in dev-env.
urllib3.disable_warnings()
##########################################################
logger = logging.getLogger("NeoLogger")

ACL_COPY = [
    "private",
    "public-read",
    "public-read-write",
    "authenticated-read",
    "aws-exec-read",
    "bucket-owner-read",
    "bucket-owner-full-control",
]

ASSETS_DIR = os.getenv("ASSETS_DIR", "TemporaryDir/")


@allure.step("List objects S3 v2")
def list_objects_s3_v2(s3_client, bucket: str, full_output: bool = False) -> list:
    try:
        response = s3_client.list_objects_v2(Bucket=bucket)
        content = response.get("Contents", [])
        log_command_execution("S3 v2 List objects result", response)
        obj_list = []
        for obj in content:
            obj_list.append(obj["Key"])
        logger.info(f"Found s3 objects: {obj_list}")
        return response if full_output else obj_list

    except ClientError as err:
        raise Exception(
            f'Error Message: {err.response["Error"]["Message"]}\n'
            f'Http status code: {err.response["ResponseMetadata"]["HTTPStatusCode"]}'
        ) from err


@allure.step("List objects S3")
def list_objects_s3(s3_client, bucket: str, full_output: bool = False) -> list:
    try:
        response = s3_client.list_objects(Bucket=bucket)
        content = response.get("Contents", [])
        log_command_execution("S3 List objects result", response)
        obj_list = []
        for obj in content:
            obj_list.append(obj["Key"])
        logger.info(f"Found s3 objects: {obj_list}")
        return response if full_output else obj_list

    except ClientError as err:
        raise Exception(
            f'Error Message: {err.response["Error"]["Message"]}\n'
            f'Http status code: {err.response["ResponseMetadata"]["HTTPStatusCode"]}'
        ) from err


@allure.step("List objects versions S3")
def list_objects_versions_s3(s3_client, bucket: str, full_output: bool = False) -> list:
    try:
        response = s3_client.list_object_versions(Bucket=bucket)
        versions = response.get("Versions", [])
        log_command_execution("S3 List objects versions result", response)
        return response if full_output else versions

    except ClientError as err:
        raise Exception(
            f'Error Message: {err.response["Error"]["Message"]}\n'
            f'Http status code: {err.response["ResponseMetadata"]["HTTPStatusCode"]}'
        ) from err


@allure.step("List objects delete markers S3")
def list_objects_delete_markers_s3(s3_client, bucket: str, full_output: bool = False) -> list:
    try:
        response = s3_client.list_object_versions(Bucket=bucket)
        delete_markers = response.get("DeleteMarkers", [])
        log_command_execution("S3 List objects delete markers result", response)
        return response if full_output else delete_markers

    except ClientError as err:
        raise Exception(
            f'Error Message: {err.response["Error"]["Message"]}\n'
            f'Http status code: {err.response["ResponseMetadata"]["HTTPStatusCode"]}'
        ) from err


@allure.step("Put object S3")
def put_object_s3(s3_client, bucket: str, filepath: str, **kwargs):
    filename = os.path.basename(filepath)

    if isinstance(s3_client, AwsCliClient):
        file_content = filepath
    else:
        with open(filepath, "rb") as put_file:
            file_content = put_file.read()

    try:
        params = {"Body": file_content, "Bucket": bucket, "Key": filename}
        if kwargs:
            params = {**params, **kwargs}
        response = s3_client.put_object(**params)
        log_command_execution("S3 Put object result", response)
        return response.get("VersionId")
    except ClientError as err:
        raise Exception(
            f'Error Message: {err.response["Error"]["Message"]}\n'
            f'Http status code: {err.response["ResponseMetadata"]["HTTPStatusCode"]}'
        ) from err


@allure.step("Head object S3")
def head_object_s3(s3_client, bucket: str, object_key: str, version_id: Optional[str] = None):
    try:
        params = {"Bucket": bucket, "Key": object_key}
        if version_id:
            params["VersionId"] = version_id
        response = s3_client.head_object(**params)
        log_command_execution("S3 Head object result", response)
        return response

    except ClientError as err:
        raise Exception(
            f'Error Message: {err.response["Error"]["Message"]}\n'
            f'Http status code: {err.response["ResponseMetadata"]["HTTPStatusCode"]}'
        ) from err


@allure.step("Delete object S3")
def delete_object_s3(
    s3_client, bucket: str, object_key: str, version_id: Optional[str] = None
) -> dict:
    try:
        params = {"Bucket": bucket, "Key": object_key}
        if version_id:
            params["VersionId"] = version_id
        response = s3_client.delete_object(**params)
        log_command_execution("S3 Delete object result", response)
        sleep(S3_SYNC_WAIT_TIME)
        return response

    except ClientError as err:
        raise Exception(
            f'Error Message: {err.response["Error"]["Message"]}\n'
            f'Http status code: {err.response["ResponseMetadata"]["HTTPStatusCode"]}'
        ) from err


@allure.step("Delete objects S3")
def delete_objects_s3(s3_client, bucket: str, object_keys: list):
    try:
        response = s3_client.delete_objects(Bucket=bucket, Delete=_make_objs_dict(object_keys))
        log_command_execution("S3 Delete objects result", response)
        sleep(S3_SYNC_WAIT_TIME)
        return response

    except ClientError as err:
        raise Exception(
            f'Error Message: {err.response["Error"]["Message"]}\n'
            f'Http status code: {err.response["ResponseMetadata"]["HTTPStatusCode"]}'
        ) from err


@allure.step("Delete object versions S3")
def delete_object_versions_s3(s3_client, bucket: str, object_versions: list):
    try:
        # Build deletion list in S3 format
        delete_list = {
            "Objects": [
                {
                    "Key": object_version["Key"],
                    "VersionId": object_version["VersionId"],
                }
                for object_version in object_versions
            ]
        }
        response = s3_client.delete_objects(Bucket=bucket, Delete=delete_list)
        log_command_execution("S3 Delete objects result", response)
        return response

    except ClientError as err:
        raise Exception(
            f'Error Message: {err.response["Error"]["Message"]}\n'
            f'Http status code: {err.response["ResponseMetadata"]["HTTPStatusCode"]}'
        ) from err


@allure.step("Delete object versions S3 without delete markers")
def delete_object_versions_s3_without_dm(s3_client, bucket: str, object_versions: list):
    try:
        # Delete objects without creating delete markers
        for object_version in object_versions:
            params = {
                "Bucket": bucket,
                "Key": object_version["Key"],
                "VersionId": object_version["VersionId"],
            }
            response = s3_client.delete_object(**params)
            log_command_execution("S3 Delete object result", response)
        return response

    except ClientError as err:
        raise Exception(
            f'Error Message: {err.response["Error"]["Message"]}\n'
            f'Http status code: {err.response["ResponseMetadata"]["HTTPStatusCode"]}'
        ) from err


@allure.step("Put object ACL")
def put_object_acl_s3(
    s3_client,
    bucket: str,
    object_key: str,
    acl: Optional[str] = None,
    grant_write: Optional[str] = None,
    grant_read: Optional[str] = None,
) -> list:
    if not isinstance(s3_client, AwsCliClient):
        pytest.skip("Method put_object_acl is not supported by boto3 client")
    params = {"Bucket": bucket, "Key": object_key}
    if acl:
        params.update({"ACL": acl})
    elif grant_write or grant_read:
        if grant_write:
            params.update({"GrantWrite": grant_write})
        elif grant_read:
            params.update({"GrantRead": grant_read})
    try:
        response = s3_client.put_object_acl(**params)
        log_command_execution("S3 ACL objects result", response)
        return response.get("Grants")

    except ClientError as err:
        raise Exception(
            f'Error Message: {err.response["Error"]["Message"]}\n'
            f'Http status code: {err.response["ResponseMetadata"]["HTTPStatusCode"]}'
        ) from err


@allure.step("Get object ACL")
def get_object_acl_s3(
    s3_client, bucket: str, object_key: str, version_id: Optional[str] = None
) -> list:
    params = {"Bucket": bucket, "Key": object_key}
    try:
        if version_id:
            params.update({"VersionId": version_id})
        response = s3_client.get_object_acl(**params)
        log_command_execution("S3 ACL objects result", response)
        return response.get("Grants")

    except ClientError as err:
        raise Exception(
            f'Error Message: {err.response["Error"]["Message"]}\n'
            f'Http status code: {err.response["ResponseMetadata"]["HTTPStatusCode"]}'
        ) from err


@allure.step("Copy object S3")
def copy_object_s3(
    s3_client, bucket: str, object_key: str, bucket_dst: Optional[str] = None, **kwargs
) -> str:
    filename = os.path.join(os.getcwd(), str(uuid.uuid4()))
    try:
        params = {
            "Bucket": bucket_dst or bucket,
            "CopySource": f"{bucket}/{object_key}",
            "Key": filename,
        }
        if "ACL" in kwargs and kwargs["ACL"] in ACL_COPY:
            params.update({"ACL": kwargs["ACL"]})
        if "metadata_directive" in kwargs.keys():
            params.update({"MetadataDirective": kwargs["metadata_directive"]})
        if "metadata_directive" in kwargs.keys() and "metadata" in kwargs.keys():
            params.update({"Metadata": kwargs["metadata"]})
        if "tagging_directive" in kwargs.keys():
            params.update({"TaggingDirective": kwargs["tagging_directive"]})
        if "tagging_directive" in kwargs.keys() and "tagging" in kwargs.keys():
            params.update({"Tagging": kwargs["tagging"]})
        response = s3_client.copy_object(**params)
        log_command_execution("S3 Copy objects result", response)
        return filename

    except ClientError as err:
        raise Exception(
            f'Error Message: {err.response["Error"]["Message"]}\n'
            f'Http status code: {err.response["ResponseMetadata"]["HTTPStatusCode"]}'
        ) from err


@allure.step("Get object S3")
def get_object_s3(
    s3_client,
    bucket: str,
    object_key: str,
    version_id: Optional[str] = None,
    range: Optional[list] = None,
    full_output: bool = False,
):
    filename = os.path.join(os.getcwd(), ASSETS_DIR, str(uuid.uuid4()))
    try:
        params = {"Bucket": bucket, "Key": object_key}
        if version_id:
            params["VersionId"] = version_id

        if isinstance(s3_client, AwsCliClient):
            params["file_path"] = filename

        if range:
            params["Range"] = f"bytes={range[0]}-{range[1]}"

        response = s3_client.get_object(**params)
        log_command_execution("S3 Get objects result", response)

        if not isinstance(s3_client, AwsCliClient):
            with open(f"{filename}", "wb") as get_file:
                chunk = response["Body"].read(1024)
                while chunk:
                    get_file.write(chunk)
                    chunk = response["Body"].read(1024)
        return response if full_output else filename

    except ClientError as err:
        raise Exception(
            f'Error Message: {err.response["Error"]["Message"]}\n'
            f'Http status code: {err.response["ResponseMetadata"]["HTTPStatusCode"]}'
        ) from err


@allure.step("Create multipart upload S3")
def create_multipart_upload_s3(s3_client, bucket_name: str, object_key: str) -> str:
    try:
        response = s3_client.create_multipart_upload(Bucket=bucket_name, Key=object_key)
        log_command_execution("S3 Created multipart upload", response)
        assert response.get("UploadId"), f"Expected UploadId in response:\n{response}"

        return response.get("UploadId")

    except ClientError as err:
        raise Exception(
            f'Error Message: {err.response["Error"]["Message"]}\n'
            f'Http status code: {err.response["ResponseMetadata"]["HTTPStatusCode"]}'
        ) from err


@allure.step("List multipart uploads S3")
def list_multipart_uploads_s3(s3_client, bucket_name: str) -> Optional[list[dict]]:
    try:
        response = s3_client.list_multipart_uploads(Bucket=bucket_name)
        log_command_execution("S3 List multipart upload", response)

        return response.get("Uploads")

    except ClientError as err:
        raise Exception(
            f'Error Message: {err.response["Error"]["Message"]}\n'
            f'Http status code: {err.response["ResponseMetadata"]["HTTPStatusCode"]}'
        ) from err


@allure.step("Abort multipart upload S3")
def abort_multipart_uploads_s3(s3_client, bucket_name: str, object_key: str, upload_id: str):
    try:
        response = s3_client.abort_multipart_upload(
            Bucket=bucket_name, Key=object_key, UploadId=upload_id
        )
        log_command_execution("S3 Abort multipart upload", response)

    except ClientError as err:
        raise Exception(
            f'Error Message: {err.response["Error"]["Message"]}\n'
            f'Http status code: {err.response["ResponseMetadata"]["HTTPStatusCode"]}'
        ) from err


@allure.step("Upload part S3")
def upload_part_s3(
    s3_client, bucket_name: str, object_key: str, upload_id: str, part_num: int, filepath: str
) -> str:
    if isinstance(s3_client, AwsCliClient):
        file_content = filepath
    else:
        with open(filepath, "rb") as put_file:
            file_content = put_file.read()

    try:
        response = s3_client.upload_part(
            UploadId=upload_id,
            Bucket=bucket_name,
            Key=object_key,
            PartNumber=part_num,
            Body=file_content,
        )
        log_command_execution("S3 Upload part", response)
        assert response.get("ETag"), f"Expected ETag in response:\n{response}"

        return response.get("ETag")
    except ClientError as err:
        raise Exception(
            f'Error Message: {err.response["Error"]["Message"]}\n'
            f'Http status code: {err.response["ResponseMetadata"]["HTTPStatusCode"]}'
        ) from err


@allure.step("Upload copy part S3")
def upload_part_copy_s3(
    s3_client, bucket_name: str, object_key: str, upload_id: str, part_num: int, copy_source: str
) -> str:

    try:
        response = s3_client.upload_part_copy(
            UploadId=upload_id,
            Bucket=bucket_name,
            Key=object_key,
            PartNumber=part_num,
            CopySource=copy_source,
        )
        log_command_execution("S3 Upload copy part", response)
        assert response.get("CopyPartResult").get("ETag"), f"Expected ETag in response:\n{response}"

        return response.get("CopyPartResult").get("ETag")
    except ClientError as err:
        raise Exception(
            f'Error Message: {err.response["Error"]["Message"]}\n'
            f'Http status code: {err.response["ResponseMetadata"]["HTTPStatusCode"]}'
        ) from err


@allure.step("List parts S3")
def list_parts_s3(s3_client, bucket_name: str, object_key: str, upload_id: str) -> list[dict]:
    try:
        response = s3_client.list_parts(UploadId=upload_id, Bucket=bucket_name, Key=object_key)
        log_command_execution("S3 List part", response)
        assert response.get("Parts"), f"Expected Parts in response:\n{response}"

        return response.get("Parts")
    except ClientError as err:
        raise Exception(
            f'Error Message: {err.response["Error"]["Message"]}\n'
            f'Http status code: {err.response["ResponseMetadata"]["HTTPStatusCode"]}'
        ) from err


@allure.step("Complete multipart upload S3")
def complete_multipart_upload_s3(
    s3_client, bucket_name: str, object_key: str, upload_id: str, parts: list
):
    try:
        parts = [{"ETag": etag, "PartNumber": part_num} for part_num, etag in parts]
        response = s3_client.complete_multipart_upload(
            Bucket=bucket_name, Key=object_key, UploadId=upload_id, MultipartUpload={"Parts": parts}
        )
        log_command_execution("S3 Complete multipart upload", response)

    except ClientError as err:
        raise Exception(
            f'Error Message: {err.response["Error"]["Message"]}\n'
            f'Http status code: {err.response["ResponseMetadata"]["HTTPStatusCode"]}'
        ) from err


@allure.step("Put object retention")
def put_object_retention(
    s3_client,
    bucket_name: str,
    object_key: str,
    retention: dict,
    version_id: Optional[str] = None,
    bypass_governance_retention: Optional[bool] = None,
):
    try:
        params = {"Bucket": bucket_name, "Key": object_key, "Retention": retention}
        if version_id:
            params.update({"VersionId": version_id})
        if not bypass_governance_retention is None:
            params.update({"BypassGovernanceRetention": bypass_governance_retention})
        s3_client.put_object_retention(**params)
        log_command_execution("S3 Put object retention ", str(retention))

    except ClientError as err:
        raise Exception(f"Got error during put object tagging: {err}") from err


@allure.step("Put object legal hold")
def put_object_legal_hold(
    s3_client, bucket_name: str, object_key: str, legal_hold: str, version_id: Optional[str] = None
):
    try:
        params = {"Bucket": bucket_name, "Key": object_key, "LegalHold": {"Status": legal_hold}}
        if version_id:
            params.update({"VersionId": version_id})
        s3_client.put_object_legal_hold(**params)
        log_command_execution("S3 Put object legal hold ", str(legal_hold))

    except ClientError as err:
        raise Exception(f"Got error during put object tagging: {err}") from err


@allure.step("Put object tagging")
def put_object_tagging(s3_client, bucket_name: str, object_key: str, tags: list):
    try:
        tags = [{"Key": tag_key, "Value": tag_value} for tag_key, tag_value in tags]
        tagging = {"TagSet": tags}
        s3_client.put_object_tagging(Bucket=bucket_name, Key=object_key, Tagging=tagging)
        log_command_execution("S3 Put object tagging", str(tags))

    except ClientError as err:
        raise Exception(f"Got error during put object tagging: {err}") from err


@allure.step("Get object tagging")
def get_object_tagging(
    s3_client, bucket_name: str, object_key: str, version_id: Optional[str] = None
) -> list:
    try:
        params = {"Bucket": bucket_name, "Key": object_key}
        if version_id:
            params.update({"VersionId": version_id})
        response = s3_client.get_object_tagging(**params)
        log_command_execution("S3 Get object tagging", response)
        return response.get("TagSet")

    except ClientError as err:
        raise Exception(f"Got error during get object tagging: {err}") from err


@allure.step("Delete object tagging")
def delete_object_tagging(s3_client, bucket_name: str, object_key: str):
    try:
        response = s3_client.delete_object_tagging(Bucket=bucket_name, Key=object_key)
        log_command_execution("S3 Delete object tagging", response)

    except ClientError as err:
        raise Exception(f"Got error during delete object tagging: {err}") from err


@allure.step("Get object attributes")
def get_object_attributes(
    s3_client,
    bucket_name: str,
    object_key: str,
    *attributes: str,
    version_id: Optional[str] = None,
    max_parts: Optional[int] = None,
    part_number: Optional[int] = None,
    get_full_resp: bool = True,
) -> dict:
    try:
        if not isinstance(s3_client, AwsCliClient):
            logger.warning("Method get_object_attributes is not supported by boto3 client")
            return {}
        response = s3_client.get_object_attributes(
            bucket_name,
            object_key,
            *attributes,
            version_id=version_id,
            max_parts=max_parts,
            part_number=part_number,
        )
        log_command_execution("S3 Get object attributes", response)
        for attr in attributes:
            assert attr in response, f"Expected attribute {attr} in {response}"

        if get_full_resp:
            return response
        else:
            return response.get(attributes[0])

    except ClientError as err:
        raise Exception(f"Got error during get object attributes: {err}") from err


def _make_objs_dict(key_names):
    objs_list = []
    for key in key_names:
        obj_dict = {"Key": key}
        objs_list.append(obj_dict)
    objs_dict = {"Objects": objs_list}
    return objs_dict
