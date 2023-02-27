import json
import logging
import uuid
from enum import Enum
from time import sleep
from typing import Optional

import allure
from botocore.exceptions import ClientError

from pytest_tests.helpers.cli_helpers import log_command_execution

logger = logging.getLogger("NeoLogger")

# Artificial delay that we add after object deletion and container creation
# Delay is added because sometimes immediately after deletion object still appears
# to be existing (probably because tombstone object takes some time to replicate)
# TODO: remove after https://github.com/nspcc-dev/neofs-s3-gw/issues/610 is fixed
S3_SYNC_WAIT_TIME = 5


class VersioningStatus(Enum):
    ENABLED = "Enabled"
    SUSPENDED = "Suspended"


@allure.step("Create bucket S3")
def create_bucket_s3(
    s3_client,
    object_lock_enabled_for_bucket: Optional[bool] = None,
    acl: Optional[str] = None,
    grant_write: Optional[str] = None,
    grant_read: Optional[str] = None,
    grant_full_control: Optional[str] = None,
    bucket_configuration: Optional[str] = None,
) -> str:
    bucket_name = str(uuid.uuid4())

    try:
        params = {"Bucket": bucket_name}
        if object_lock_enabled_for_bucket is not None:
            params.update({"ObjectLockEnabledForBucket": object_lock_enabled_for_bucket})
        if acl is not None:
            params.update({"ACL": acl})
        elif grant_write or grant_read or grant_full_control:
            if grant_write:
                params.update({"GrantWrite": grant_write})
            elif grant_read:
                params.update({"GrantRead": grant_read})
            elif grant_full_control:
                params.update({"GrantFullControl": grant_full_control})
        if bucket_configuration:
            params.update(
                {"CreateBucketConfiguration": {"LocationConstraint": bucket_configuration}}
            )

        s3_bucket = s3_client.create_bucket(**params)
        log_command_execution(f"Created S3 bucket {bucket_name}", s3_bucket)
        sleep(S3_SYNC_WAIT_TIME)
        return bucket_name
    except ClientError as err:
        raise Exception(
            f'Error Message: {err.response["Error"]["Message"]}\n'
            f'Http status code: {err.response["ResponseMetadata"]["HTTPStatusCode"]}'
        ) from err


@allure.step("List buckets S3")
def list_buckets_s3(s3_client):
    found_buckets = []
    try:
        response = s3_client.list_buckets()
        log_command_execution("S3 List buckets result", response)

        for bucket in response["Buckets"]:
            found_buckets.append(bucket["Name"])

        return found_buckets

    except ClientError as err:
        raise Exception(
            f'Error Message: {err.response["Error"]["Message"]}\n'
            f'Http status code: {err.response["ResponseMetadata"]["HTTPStatusCode"]}'
        ) from err


@allure.step("Delete bucket S3")
def delete_bucket_s3(s3_client, bucket: str):
    try:
        response = s3_client.delete_bucket(Bucket=bucket)
        log_command_execution("S3 Delete bucket result", response)
        sleep(S3_SYNC_WAIT_TIME)
        return response

    except ClientError as err:
        log_command_execution("S3 Delete bucket error", str(err))
        raise Exception(
            f'Error Message: {err.response["Error"]["Message"]}\n'
            f'Http status code: {err.response["ResponseMetadata"]["HTTPStatusCode"]}'
        ) from err


@allure.step("Head bucket S3")
def head_bucket(s3_client, bucket: str):
    try:
        response = s3_client.head_bucket(Bucket=bucket)
        log_command_execution("S3 Head bucket result", response)
        return response

    except ClientError as err:
        log_command_execution("S3 Head bucket error", str(err))
        raise Exception(
            f'Error Message: {err.response["Error"]["Message"]}\n'
            f'Http status code: {err.response["ResponseMetadata"]["HTTPStatusCode"]}'
        ) from err


@allure.step("Set bucket versioning status")
def set_bucket_versioning(s3_client, bucket_name: str, status: VersioningStatus) -> None:
    try:
        response = s3_client.put_bucket_versioning(
            Bucket=bucket_name, VersioningConfiguration={"Status": status.value}
        )
        log_command_execution("S3 Set bucket versioning to", response)

    except ClientError as err:
        raise Exception(f"Got error during set bucket versioning: {err}") from err


@allure.step("Get bucket versioning status")
def get_bucket_versioning_status(s3_client, bucket_name: str) -> str:
    try:
        response = s3_client.get_bucket_versioning(Bucket=bucket_name)
        status = response.get("Status")
        log_command_execution("S3 Got bucket versioning status", response)
        return status
    except ClientError as err:
        raise Exception(f"Got error during get bucket versioning status: {err}") from err


@allure.step("Put bucket tagging")
def put_bucket_tagging(s3_client, bucket_name: str, tags: list):
    try:
        tags = [{"Key": tag_key, "Value": tag_value} for tag_key, tag_value in tags]
        tagging = {"TagSet": tags}
        response = s3_client.put_bucket_tagging(Bucket=bucket_name, Tagging=tagging)
        log_command_execution("S3 Put bucket tagging", response)

    except ClientError as err:
        raise Exception(f"Got error during put bucket tagging: {err}") from err


@allure.step("Get bucket acl")
def get_bucket_acl(s3_client, bucket_name: str) -> list:
    try:
        response = s3_client.get_bucket_acl(Bucket=bucket_name)
        log_command_execution("S3 Get bucket acl", response)
        return response.get("Grants")

    except ClientError as err:
        raise Exception(f"Got error during get bucket tagging: {err}") from err


@allure.step("Get bucket tagging")
def get_bucket_tagging(s3_client, bucket_name: str) -> list:
    try:
        response = s3_client.get_bucket_tagging(Bucket=bucket_name)
        log_command_execution("S3 Get bucket tagging", response)
        return response.get("TagSet")

    except ClientError as err:
        raise Exception(f"Got error during get bucket tagging: {err}") from err


@allure.step("Delete bucket tagging")
def delete_bucket_tagging(s3_client, bucket_name: str) -> None:
    try:
        response = s3_client.delete_bucket_tagging(Bucket=bucket_name)
        log_command_execution("S3 Delete bucket tagging", response)

    except ClientError as err:
        raise Exception(f"Got error during delete bucket tagging: {err}") from err


@allure.step("Put bucket ACL")
def put_bucket_acl_s3(
    s3_client,
    bucket: str,
    acl: Optional[str] = None,
    grant_write: Optional[str] = None,
    grant_read: Optional[str] = None,
) -> list:
    params = {"Bucket": bucket}
    if acl:
        params.update({"ACL": acl})
    elif grant_write or grant_read:
        if grant_write:
            params.update({"GrantWrite": grant_write})
        elif grant_read:
            params.update({"GrantRead": grant_read})

    try:
        response = s3_client.put_bucket_acl(**params)
        log_command_execution("S3 ACL bucket result", response)
        return response.get("Grants")
    except ClientError as err:
        raise Exception(
            f'Error Message: {err.response["Error"]["Message"]}\n'
            f'Http status code: {err.response["ResponseMetadata"]["HTTPStatusCode"]}'
        ) from err


@allure.step("Put object lock configuration")
def put_object_lock_configuration(s3_client, bucket: str, configuration: dict):
    params = {"Bucket": bucket, "ObjectLockConfiguration": configuration}
    try:
        response = s3_client.put_object_lock_configuration(**params)
        log_command_execution("S3 put_object_lock_configuration result", response)
        return response
    except ClientError as err:
        raise Exception(
            f'Error Message: {err.response["Error"]["Message"]}\n'
            f'Http status code: {err.response["ResponseMetadata"]["HTTPStatusCode"]}'
        ) from err


@allure.step("Get object lock configuration")
def get_object_lock_configuration(s3_client, bucket: str):
    params = {"Bucket": bucket}
    try:
        response = s3_client.get_object_lock_configuration(**params)
        log_command_execution("S3 get_object_lock_configuration result", response)
        return response.get("ObjectLockConfiguration")
    except ClientError as err:
        raise Exception(
            f'Error Message: {err.response["Error"]["Message"]}\n'
            f'Http status code: {err.response["ResponseMetadata"]["HTTPStatusCode"]}'
        ) from err


def get_bucket_policy(s3_client, bucket: str):
    params = {"Bucket": bucket}
    try:
        response = s3_client.get_bucket_policy(**params)
        log_command_execution("S3 get_object_lock_configuration result", response)
        return response.get("ObjectLockConfiguration")
    except ClientError as err:
        raise Exception(
            f'Error Message: {err.response["Error"]["Message"]}\n'
            f'Http status code: {err.response["ResponseMetadata"]["HTTPStatusCode"]}'
        ) from err


def put_bucket_policy(s3_client, bucket: str, policy: dict):
    params = {"Bucket": bucket, "Policy": json.dumps(policy)}
    try:
        response = s3_client.put_bucket_policy(**params)
        log_command_execution("S3 put_bucket_policy result", response)
        return response
    except ClientError as err:
        raise Exception(
            f'Error Message: {err.response["Error"]["Message"]}\n'
            f'Http status code: {err.response["ResponseMetadata"]["HTTPStatusCode"]}'
        ) from err


def get_bucket_cors(s3_client, bucket: str):
    params = {"Bucket": bucket}
    try:
        response = s3_client.get_bucket_cors(**params)
        log_command_execution("S3 get_bucket_cors result", response)
        return response.get("CORSRules")
    except ClientError as err:
        raise Exception(
            f'Error Message: {err.response["Error"]["Message"]}\n'
            f'Http status code: {err.response["ResponseMetadata"]["HTTPStatusCode"]}'
        ) from err


def get_bucket_location(s3_client, bucket: str):
    params = {"Bucket": bucket}
    try:
        response = s3_client.get_bucket_location(**params)
        log_command_execution("S3 get_bucket_location result", response)
        return response.get("LocationConstraint")
    except ClientError as err:
        raise Exception(
            f'Error Message: {err.response["Error"]["Message"]}\n'
            f'Http status code: {err.response["ResponseMetadata"]["HTTPStatusCode"]}'
        ) from err


def put_bucket_cors(s3_client, bucket: str, cors_configuration: dict):
    params = {"Bucket": bucket, "CORSConfiguration": cors_configuration}
    try:
        response = s3_client.put_bucket_cors(**params)
        log_command_execution("S3 put_bucket_cors result", response)
        return response
    except ClientError as err:
        raise Exception(
            f'Error Message: {err.response["Error"]["Message"]}\n'
            f'Http status code: {err.response["ResponseMetadata"]["HTTPStatusCode"]}'
        ) from err


def delete_bucket_cors(s3_client, bucket: str):
    params = {"Bucket": bucket}
    try:
        response = s3_client.delete_bucket_cors(**params)
        log_command_execution("S3 delete_bucket_cors result", response)
        return response.get("ObjectLockConfiguration")
    except ClientError as err:
        raise Exception(
            f'Error Message: {err.response["Error"]["Message"]}\n'
            f'Http status code: {err.response["ResponseMetadata"]["HTTPStatusCode"]}'
        ) from err
