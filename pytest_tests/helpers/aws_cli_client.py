import json
import logging
import os
from datetime import datetime
from typing import Optional

import allure

from pytest_tests.helpers.cli_helpers import _cmd_run
from pytest_tests.resources.common import ASSETS_DIR

logger = logging.getLogger("NeoLogger")
REGULAR_TIMEOUT = 90
LONG_TIMEOUT = 240


class AwsCliClient:
    # Flags that we use for all S3 commands: disable SSL verification (as we use self-signed
    # certificate in devenv) and disable automatic pagination in CLI output
    common_flags = "--no-verify-ssl --no-paginate"
    s3gate_endpoint: str

    def __init__(self, s3gate_endpoint) -> None:
        self.s3gate_endpoint = s3gate_endpoint

    def create_bucket(
        self,
        Bucket: str,
        ObjectLockEnabledForBucket: Optional[bool] = None,
        ACL: Optional[str] = None,
        GrantFullControl: Optional[str] = None,
        GrantRead: Optional[str] = None,
        GrantWrite: Optional[str] = None,
        CreateBucketConfiguration: Optional[dict] = None,
    ):
        if ObjectLockEnabledForBucket is None:
            object_lock = ""
        elif ObjectLockEnabledForBucket:
            object_lock = " --object-lock-enabled-for-bucket"
        else:
            object_lock = " --no-object-lock-enabled-for-bucket"
        cmd = (
            f"aws {self.common_flags} s3api create-bucket --bucket {Bucket} "
            f"{object_lock} --endpoint {self.s3gate_endpoint}"
        )
        if ACL:
            cmd += f" --acl {ACL}"
        if GrantFullControl:
            cmd += f" --grant-full-control {GrantFullControl}"
        if GrantWrite:
            cmd += f" --grant-write {GrantWrite}"
        if GrantRead:
            cmd += f" --grant-read {GrantRead}"
        if CreateBucketConfiguration:
            cmd += f" --create-bucket-configuration LocationConstraint={CreateBucketConfiguration['LocationConstraint']}"
        _cmd_run(cmd, REGULAR_TIMEOUT)

    def list_buckets(self) -> dict:
        cmd = f"aws {self.common_flags} s3api list-buckets --endpoint {self.s3gate_endpoint}"
        output = _cmd_run(cmd)
        return self._to_json(output)

    def get_bucket_acl(self, Bucket: str) -> dict:
        cmd = (
            f"aws {self.common_flags} s3api get-bucket-acl --bucket {Bucket} "
            f"--endpoint {self.s3gate_endpoint}"
        )
        output = _cmd_run(cmd, REGULAR_TIMEOUT)
        return self._to_json(output)

    def get_bucket_versioning(self, Bucket: str) -> dict:
        cmd = (
            f"aws {self.common_flags} s3api get-bucket-versioning --bucket {Bucket} "
            f"--endpoint {self.s3gate_endpoint}"
        )
        output = _cmd_run(cmd, REGULAR_TIMEOUT)
        return self._to_json(output)

    def get_bucket_location(self, Bucket: str) -> dict:
        cmd = (
            f"aws {self.common_flags} s3api get-bucket-location --bucket {Bucket} "
            f"--endpoint {self.s3gate_endpoint}"
        )
        output = _cmd_run(cmd, REGULAR_TIMEOUT)
        return self._to_json(output)

    def put_bucket_versioning(self, Bucket: str, VersioningConfiguration: dict) -> dict:
        cmd = (
            f"aws {self.common_flags} s3api put-bucket-versioning --bucket {Bucket} "
            f'--versioning-configuration Status={VersioningConfiguration.get("Status")} '
            f"--endpoint {self.s3gate_endpoint}"
        )
        output = _cmd_run(cmd)
        return self._to_json(output)

    def list_objects(self, Bucket: str) -> dict:
        cmd = (
            f"aws {self.common_flags} s3api list-objects --bucket {Bucket} "
            f"--endpoint {self.s3gate_endpoint}"
        )
        output = _cmd_run(cmd)
        return self._to_json(output)

    def list_objects_v2(self, Bucket: str) -> dict:
        cmd = (
            f"aws {self.common_flags} s3api list-objects-v2 --bucket {Bucket} "
            f"--endpoint {self.s3gate_endpoint}"
        )
        output = _cmd_run(cmd)
        return self._to_json(output)

    def list_object_versions(self, Bucket: str) -> dict:
        cmd = (
            f"aws {self.common_flags} s3api list-object-versions --bucket {Bucket} "
            f"--endpoint {self.s3gate_endpoint}"
        )
        output = _cmd_run(cmd)
        return self._to_json(output)

    def copy_object(
        self,
        Bucket: str,
        CopySource: str,
        Key: str,
        ACL: Optional[str] = None,
        MetadataDirective: Optional[str] = None,
        Metadata: Optional[dict] = None,
        TaggingDirective: Optional[str] = None,
        Tagging: Optional[str] = None,
    ) -> dict:
        cmd = (
            f"aws {self.common_flags} s3api copy-object --copy-source {CopySource} "
            f"--bucket {Bucket} --key {Key} --endpoint {self.s3gate_endpoint}"
        )
        if ACL:
            cmd += f" --acl {ACL}"
        if MetadataDirective:
            cmd += f" --metadata-directive {MetadataDirective}"
        if Metadata:
            cmd += " --metadata "
            for key, value in Metadata.items():
                cmd += f" {key}={value}"
        if TaggingDirective:
            cmd += f" --tagging-directive {TaggingDirective}"
        if Tagging:
            cmd += f" --tagging {Tagging}"
        output = _cmd_run(cmd, LONG_TIMEOUT)
        return self._to_json(output)

    def head_bucket(self, Bucket: str) -> dict:
        cmd = f"aws {self.common_flags} s3api head-bucket --bucket {Bucket} --endpoint {self.s3gate_endpoint}"
        output = _cmd_run(cmd)
        return self._to_json(output)

    def put_object(
        self,
        Body: str,
        Bucket: str,
        Key: str,
        Metadata: Optional[dict] = None,
        Tagging: Optional[str] = None,
        ACL: Optional[str] = None,
        ObjectLockMode: Optional[str] = None,
        ObjectLockRetainUntilDate: Optional[datetime] = None,
        ObjectLockLegalHoldStatus: Optional[str] = None,
        GrantFullControl: Optional[str] = None,
        GrantRead: Optional[str] = None,
    ) -> dict:
        cmd = (
            f"aws {self.common_flags} s3api put-object --bucket {Bucket} --key {Key} "
            f"--body {Body} --endpoint {self.s3gate_endpoint}"
        )
        if Metadata:
            cmd += f" --metadata"
            for key, value in Metadata.items():
                cmd += f" {key}={value}"
        if Tagging:
            cmd += f" --tagging '{Tagging}'"
        if ACL:
            cmd += f" --acl {ACL}"
        if ObjectLockMode:
            cmd += f" --object-lock-mode {ObjectLockMode}"
        if ObjectLockRetainUntilDate:
            cmd += f' --object-lock-retain-until-date "{ObjectLockRetainUntilDate}"'
        if ObjectLockLegalHoldStatus:
            cmd += f" --object-lock-legal-hold-status {ObjectLockLegalHoldStatus}"
        if GrantFullControl:
            cmd += f" --grant-full-control '{GrantFullControl}'"
        if GrantRead:
            cmd += f" --grant-read {GrantRead}"
        output = _cmd_run(cmd, LONG_TIMEOUT)
        return self._to_json(output)

    def head_object(self, Bucket: str, Key: str, VersionId: str = None) -> dict:
        version = f" --version-id {VersionId}" if VersionId else ""
        cmd = (
            f"aws {self.common_flags} s3api head-object --bucket {Bucket} --key {Key} "
            f"{version} --endpoint {self.s3gate_endpoint}"
        )
        output = _cmd_run(cmd)
        return self._to_json(output)

    def get_object(
        self,
        Bucket: str,
        Key: str,
        file_path: str,
        VersionId: Optional[str] = None,
        Range: Optional[str] = None,
    ) -> dict:
        version = f" --version-id {VersionId}" if VersionId else ""
        cmd = (
            f"aws {self.common_flags} s3api get-object --bucket {Bucket} --key {Key} "
            f"{version} {file_path} --endpoint {self.s3gate_endpoint}"
        )
        if Range:
            cmd += f" --range {Range}"
        output = _cmd_run(cmd, REGULAR_TIMEOUT)
        return self._to_json(output)

    def get_object_acl(self, Bucket: str, Key: str, VersionId: Optional[str] = None) -> dict:
        version = f" --version-id {VersionId}" if VersionId else ""
        cmd = (
            f"aws {self.common_flags} s3api get-object-acl --bucket {Bucket} --key {Key} "
            f"{version} --endpoint {self.s3gate_endpoint}"
        )
        output = _cmd_run(cmd, REGULAR_TIMEOUT)
        return self._to_json(output)

    def put_object_acl(
        self,
        Bucket: str,
        Key: str,
        ACL: Optional[str] = None,
        GrantWrite: Optional[str] = None,
        GrantRead: Optional[str] = None,
    ) -> dict:
        cmd = (
            f"aws {self.common_flags} s3api put-object-acl --bucket {Bucket} --key {Key} "
            f" --endpoint {self.s3gate_endpoint}"
        )
        if ACL:
            cmd += f" --acl {ACL}"
        if GrantWrite:
            cmd += f" --grant-write {GrantWrite}"
        if GrantRead:
            cmd += f" --grant-read {GrantRead}"
        output = _cmd_run(cmd, REGULAR_TIMEOUT)
        return self._to_json(output)

    def put_bucket_acl(
        self,
        Bucket: str,
        ACL: Optional[str] = None,
        GrantWrite: Optional[str] = None,
        GrantRead: Optional[str] = None,
    ) -> dict:
        cmd = (
            f"aws {self.common_flags} s3api put-bucket-acl --bucket {Bucket} "
            f" --endpoint {self.s3gate_endpoint}"
        )
        if ACL:
            cmd += f" --acl {ACL}"
        if GrantWrite:
            cmd += f" --grant-write {GrantWrite}"
        if GrantRead:
            cmd += f" --grant-read {GrantRead}"
        output = _cmd_run(cmd, REGULAR_TIMEOUT)
        return self._to_json(output)

    def delete_objects(self, Bucket: str, Delete: dict) -> dict:
        file_path = os.path.join(os.getcwd(), ASSETS_DIR, "delete.json")
        with open(file_path, "w") as out_file:
            out_file.write(json.dumps(Delete))
        logger.info(f"Input file for delete-objects: {json.dumps(Delete)}")

        cmd = (
            f"aws {self.common_flags} s3api delete-objects --bucket {Bucket} "
            f"--delete file://{file_path} --endpoint {self.s3gate_endpoint}"
        )
        output = _cmd_run(cmd, LONG_TIMEOUT)
        return self._to_json(output)

    def delete_object(self, Bucket: str, Key: str, VersionId: str = None) -> dict:
        version = f" --version-id {VersionId}" if VersionId else ""
        cmd = (
            f"aws {self.common_flags} s3api delete-object --bucket {Bucket} "
            f"--key {Key} {version} --endpoint {self.s3gate_endpoint}"
        )
        output = _cmd_run(cmd, LONG_TIMEOUT)
        return self._to_json(output)

    def get_object_attributes(
        self,
        bucket: str,
        key: str,
        *attributes: str,
        version_id: str = None,
        max_parts: int = None,
        part_number: int = None,
    ) -> dict:
        attrs = ",".join(attributes)
        version = f" --version-id {version_id}" if version_id else ""
        parts = f"--max-parts {max_parts}" if max_parts else ""
        part_number = f"--part-number-marker {part_number}" if part_number else ""
        cmd = (
            f"aws {self.common_flags} s3api get-object-attributes --bucket {bucket} "
            f"--key {key} {version} {parts} {part_number} --object-attributes {attrs} "
            f"--endpoint {self.s3gate_endpoint}"
        )
        output = _cmd_run(cmd)
        return self._to_json(output)

    def delete_bucket(self, Bucket: str) -> dict:
        cmd = f"aws {self.common_flags} s3api delete-bucket --bucket {Bucket} --endpoint {self.s3gate_endpoint}"
        output = _cmd_run(cmd, LONG_TIMEOUT)
        return self._to_json(output)

    def get_bucket_tagging(self, Bucket: str) -> dict:
        cmd = (
            f"aws {self.common_flags} s3api get-bucket-tagging --bucket {Bucket} "
            f"--endpoint {self.s3gate_endpoint}"
        )
        output = _cmd_run(cmd)
        return self._to_json(output)

    def get_bucket_policy(self, Bucket: str) -> dict:
        cmd = (
            f"aws {self.common_flags} s3api get-bucket-policy --bucket {Bucket} "
            f"--endpoint {self.s3gate_endpoint}"
        )
        output = _cmd_run(cmd)
        return self._to_json(output)

    def put_bucket_policy(self, Bucket: str, Policy: dict) -> dict:
        cmd = (
            f"aws {self.common_flags} s3api put-bucket-policy --bucket {Bucket} "
            f"--policy {json.dumps(Policy)} --endpoint {self.s3gate_endpoint}"
        )
        output = _cmd_run(cmd)
        return self._to_json(output)

    def get_bucket_cors(self, Bucket: str) -> dict:
        cmd = (
            f"aws {self.common_flags} s3api get-bucket-cors --bucket {Bucket} "
            f"--endpoint {self.s3gate_endpoint}"
        )
        output = _cmd_run(cmd)
        return self._to_json(output)

    def put_bucket_cors(self, Bucket: str, CORSConfiguration: dict) -> dict:
        cmd = (
            f"aws {self.common_flags} s3api put-bucket-cors --bucket {Bucket} "
            f"--cors-configuration '{json.dumps(CORSConfiguration)}' --endpoint {self.s3gate_endpoint}"
        )
        output = _cmd_run(cmd)
        return self._to_json(output)

    def delete_bucket_cors(self, Bucket: str) -> dict:
        cmd = (
            f"aws {self.common_flags} s3api delete-bucket-cors --bucket {Bucket} "
            f"--endpoint {self.s3gate_endpoint}"
        )
        output = _cmd_run(cmd)
        return self._to_json(output)

    def put_bucket_tagging(self, Bucket: str, Tagging: dict) -> dict:
        cmd = (
            f"aws {self.common_flags} s3api put-bucket-tagging --bucket {Bucket} "
            f"--tagging '{json.dumps(Tagging)}' --endpoint {self.s3gate_endpoint}"
        )
        output = _cmd_run(cmd)
        return self._to_json(output)

    def delete_bucket_tagging(self, Bucket: str) -> dict:
        cmd = (
            f"aws {self.common_flags} s3api delete-bucket-tagging --bucket {Bucket} "
            f"--endpoint {self.s3gate_endpoint}"
        )
        output = _cmd_run(cmd)
        return self._to_json(output)

    def put_object_retention(
        self, Bucket: str, Key: str, Retention: dict, VersionId: Optional[str] = None
    ) -> dict:
        version = f" --version-id {VersionId}" if VersionId else ""
        cmd = (
            f"aws {self.common_flags} s3api put-object-retention --bucket {Bucket} --key {Key} "
            f"{version} --retention '{json.dumps(Retention, indent=4, sort_keys=True, default=str)}' --endpoint {self.s3gate_endpoint}"
        )
        output = _cmd_run(cmd)
        return self._to_json(output)

    def put_object_legal_hold(
        self, Bucket: str, Key: str, LegalHold: dict, VersionId: Optional[str] = None
    ) -> dict:
        version = f" --version-id {VersionId}" if VersionId else ""
        cmd = (
            f"aws {self.common_flags} s3api  put-object-legal-hold --bucket {Bucket} --key {Key} "
            f"{version} --legal-hold '{json.dumps(LegalHold)}' --endpoint {self.s3gate_endpoint}"
        )
        output = _cmd_run(cmd)
        return self._to_json(output)

    def put_object_retention(
        self,
        Bucket: str,
        Key: str,
        Retention: dict,
        VersionId: Optional[str] = None,
        BypassGovernanceRetention: Optional[bool] = None,
    ) -> dict:
        version = f" --version-id {VersionId}" if VersionId else ""
        cmd = (
            f"aws {self.common_flags} s3api put-object-retention --bucket {Bucket} --key {Key} "
            f"{version} --retention '{json.dumps(Retention, indent=4, sort_keys=True, default=str)}' --endpoint {self.s3gate_endpoint}"
        )
        if not BypassGovernanceRetention is None:
            cmd += " --bypass-governance-retention"
        output = _cmd_run(cmd)
        return self._to_json(output)

    def put_object_legal_hold(
        self, Bucket: str, Key: str, LegalHold: dict, VersionId: Optional[str] = None
    ) -> dict:
        version = f" --version-id {VersionId}" if VersionId else ""
        cmd = (
            f"aws {self.common_flags} s3api  put-object-legal-hold --bucket {Bucket} --key {Key} "
            f"{version} --legal-hold '{json.dumps(LegalHold)}' --endpoint {self.s3gate_endpoint}"
        )
        output = _cmd_run(cmd)
        return self._to_json(output)

    def put_object_tagging(self, Bucket: str, Key: str, Tagging: dict) -> dict:
        cmd = (
            f"aws {self.common_flags} s3api put-object-tagging --bucket {Bucket} --key {Key} "
            f"--tagging '{json.dumps(Tagging)}' --endpoint {self.s3gate_endpoint}"
        )
        output = _cmd_run(cmd)
        return self._to_json(output)

    def get_object_tagging(self, Bucket: str, Key: str, VersionId: Optional[str] = None) -> dict:
        version = f" --version-id {VersionId}" if VersionId else ""
        cmd = (
            f"aws {self.common_flags} s3api get-object-tagging --bucket {Bucket} --key {Key} "
            f"{version}  --endpoint {self.s3gate_endpoint}"
        )
        output = _cmd_run(cmd, REGULAR_TIMEOUT)
        return self._to_json(output)

    def delete_object_tagging(self, Bucket: str, Key: str) -> dict:
        cmd = (
            f"aws {self.common_flags} s3api delete-object-tagging --bucket {Bucket} "
            f"--key {Key} --endpoint {self.s3gate_endpoint}"
        )
        output = _cmd_run(cmd)
        return self._to_json(output)

    @allure.step("Sync directory S3")
    def sync(
        self,
        bucket_name: str,
        dir_path: str,
        ACL: Optional[str] = None,
        Metadata: Optional[dict] = None,
    ) -> dict:
        cmd = (
            f"aws {self.common_flags} s3 sync {dir_path}  s3://{bucket_name} "
            f"--endpoint-url {self.s3gate_endpoint}"
        )
        if Metadata:
            cmd += f" --metadata"
            for key, value in Metadata.items():
                cmd += f" {key}={value}"
        if ACL:
            cmd += f" --acl {ACL}"
        output = _cmd_run(cmd, LONG_TIMEOUT)
        return self._to_json(output)

    @allure.step("CP directory S3")
    def cp(
        self,
        bucket_name: str,
        dir_path: str,
        ACL: Optional[str] = None,
        Metadata: Optional[dict] = None,
    ) -> dict:
        cmd = (
            f"aws {self.common_flags} s3 cp {dir_path}  s3://{bucket_name} "
            f"--endpoint-url {self.s3gate_endpoint}  --recursive"
        )
        if Metadata:
            cmd += f" --metadata"
            for key, value in Metadata.items():
                cmd += f" {key}={value}"
        if ACL:
            cmd += f" --acl {ACL}"
        output = _cmd_run(cmd, LONG_TIMEOUT)
        return self._to_json(output)

    def create_multipart_upload(self, Bucket: str, Key: str) -> dict:
        cmd = (
            f"aws {self.common_flags} s3api create-multipart-upload --bucket {Bucket} "
            f"--key {Key} --endpoint-url {self.s3gate_endpoint}"
        )
        output = _cmd_run(cmd)
        return self._to_json(output)

    def list_multipart_uploads(self, Bucket: str) -> dict:
        cmd = (
            f"aws {self.common_flags} s3api list-multipart-uploads --bucket {Bucket} "
            f"--endpoint-url {self.s3gate_endpoint}"
        )
        output = _cmd_run(cmd)
        return self._to_json(output)

    def abort_multipart_upload(self, Bucket: str, Key: str, UploadId: str) -> dict:
        cmd = (
            f"aws {self.common_flags} s3api abort-multipart-upload  --bucket {Bucket} "
            f"--key {Key} --upload-id {UploadId} --endpoint-url {self.s3gate_endpoint}"
        )
        output = _cmd_run(cmd)
        return self._to_json(output)

    def upload_part(self, UploadId: str, Bucket: str, Key: str, PartNumber: int, Body: str) -> dict:
        cmd = (
            f"aws {self.common_flags} s3api upload-part --bucket {Bucket} --key {Key} "
            f"--upload-id {UploadId} --part-number {PartNumber} --body {Body} "
            f"--endpoint-url {self.s3gate_endpoint}"
        )
        output = _cmd_run(cmd, LONG_TIMEOUT)
        return self._to_json(output)

    def upload_part_copy(
        self, UploadId: str, Bucket: str, Key: str, PartNumber: int, CopySource: str
    ) -> dict:
        cmd = (
            f"aws {self.common_flags} s3api upload-part-copy --bucket {Bucket} --key {Key} "
            f"--upload-id {UploadId} --part-number {PartNumber} --copy-source {CopySource} "
            f"--endpoint-url {self.s3gate_endpoint}"
        )
        output = _cmd_run(cmd, LONG_TIMEOUT)
        return self._to_json(output)

    def list_parts(self, UploadId: str, Bucket: str, Key: str) -> dict:
        cmd = (
            f"aws {self.common_flags} s3api list-parts --bucket {Bucket} --key {Key} "
            f"--upload-id {UploadId} --endpoint-url {self.s3gate_endpoint}"
        )
        output = _cmd_run(cmd)
        return self._to_json(output)

    def complete_multipart_upload(
        self, Bucket: str, Key: str, UploadId: str, MultipartUpload: dict
    ) -> dict:
        file_path = os.path.join(os.getcwd(), ASSETS_DIR, "parts.json")
        with open(file_path, "w") as out_file:
            out_file.write(json.dumps(MultipartUpload))
        logger.info(f"Input file for complete-multipart-upload: {json.dumps(MultipartUpload)}")

        cmd = (
            f"aws {self.common_flags} s3api complete-multipart-upload --bucket {Bucket} "
            f"--key {Key}  --upload-id {UploadId} --multipart-upload file://{file_path} "
            f"--endpoint-url {self.s3gate_endpoint}"
        )
        output = _cmd_run(cmd)
        return self._to_json(output)

    def put_object_lock_configuration(self, Bucket, ObjectLockConfiguration):
        cmd = (
            f"aws {self.common_flags} s3api put-object-lock-configuration --bucket {Bucket} "
            f"--object-lock-configuration '{json.dumps(ObjectLockConfiguration)}' --endpoint-url {self.s3gate_endpoint}"
        )
        output = _cmd_run(cmd)
        return self._to_json(output)

    def get_object_lock_configuration(self, Bucket):
        cmd = (
            f"aws {self.common_flags} s3api get-object-lock-configuration --bucket {Bucket} "
            f"--endpoint-url {self.s3gate_endpoint}"
        )
        output = _cmd_run(cmd)
        return self._to_json(output)

    @staticmethod
    def _to_json(output: str) -> dict:
        json_output = {}
        try:
            json_output = json.loads(output)
        except Exception:
            if "{" not in output and "}" not in output:
                logger.warning(f"Could not parse json from output {output}")
                return json_output
            json_output = json.loads(output[output.index("{") :])

        return json_output
