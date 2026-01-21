# =============================================================================
# S3 Client for SGA Inventory
# =============================================================================
# Client for all S3 operations in the inventory management module.
#
# Features:
# - Presigned URL generation for secure uploads/downloads
# - Organized directory structure for NFs, evidences, inventories
# - Temporary upload staging with auto-cleanup
# - Content type detection
#
# CRITICAL: Lazy imports for cold start optimization (<30s limit)
#
# VERSION: 2026-01-06T04:00:00Z - SigV4 fix for presigned URLs
# MUST use signature_version='s3v4' - S3 in us-east-2 rejects SigV2
# =============================================================================

from typing import Optional, Dict, Any, List
from datetime import datetime
import logging
import os

from shared.debug_utils import debug_error

logger = logging.getLogger(__name__)


# =============================================================================
# Custom Exception Classes (Phase 1 - Secure File Ingestion)
# =============================================================================


class S3ClientError(Exception):
    """Base exception for S3 client operations."""
    pass


class S3AccessError(S3ClientError):
    """Raised when S3 access is denied (permissions, bucket policy)."""
    pass


class S3FileNotFoundError(S3ClientError):
    """Raised when requested S3 object does not exist."""
    pass


class S3UploadError(S3ClientError):
    """Raised when file upload fails."""
    pass

# Module version for deployment tracking
_MODULE_VERSION = "2026-01-21T18:00:00Z"
logger.info("[S3Client] Module loaded - version %s", _MODULE_VERSION)

# Lazy imports - boto3 imported only when needed
# CRITICAL: Reset to None on each cold start to ensure SigV4 config is applied
_s3_client = None


def _get_s3_client():
    """
    Get S3 client with lazy initialization.

    CRITICAL: Must use signature_version='s3v4' for presigned URLs.
    S3 buckets in us-east-2 require SigV4 - SigV2 URLs return 400 Bad Request.

    Returns:
        boto3 S3 client configured for us-east-2 with SigV4
    """
    global _s3_client
    if _s3_client is None:
        import boto3
        from botocore.config import Config

        # DEBUG: Log to CloudWatch to verify this code path is executed
        logger.info("[S3Client] Creating NEW S3 client with SigV4 config - 2026-01-06T03:50:00Z")

        # CRITICAL: Configure S3 client for SigV4 presigned URLs
        # Without this, presigned URLs use SigV2 which fails with 400 Bad Request
        # See CLAUDE.md "S3 Presigned URL Issues - CORS 307 Redirect (CRITICAL)"
        config = Config(
            signature_version='s3v4',
            s3={'addressing_style': 'virtual'}
        )
        _s3_client = boto3.client(
            's3',
            region_name='us-east-2',
            config=config
        )
        logger.info("[S3Client] Client created with config: signature_version=s3v4, region=us-east-2")
    return _s3_client


def _get_bucket_name() -> str:
    """Get documents bucket name from environment."""
    return os.environ.get("DOCUMENTS_BUCKET", "faiston-one-sga-documents-prod")


# =============================================================================
# S3 Client Class
# =============================================================================


class SGAS3Client:
    """
    S3 client for SGA Inventory document management.

    Directory Structure:
    - notas-fiscais/{YYYY}/{MM}/{nf_id}/ - NF files
    - evidences/{movement_id}/ - Movement evidence
    - inventories/{campaign_id}/ - Inventory campaign files
    - temp/uploads/ - Temporary upload staging

    Example:
        client = SGAS3Client()
        url = client.generate_upload_url("temp/uploads/doc.pdf", "application/pdf")
    """

    def __init__(self, bucket_name: Optional[str] = None):
        """
        Initialize the S3 client.

        Args:
            bucket_name: Override bucket name (for testing)
        """
        self._bucket = bucket_name or _get_bucket_name()

    @property
    def bucket(self) -> str:
        """Get bucket name."""
        return self._bucket

    @property
    def client(self):
        """Get S3 client with lazy loading."""
        return _get_s3_client()

    # =========================================================================
    # Presigned URL Generation
    # =========================================================================

    def generate_upload_url(
        self,
        key: str,
        content_type: str = "application/octet-stream",
        expires_in: int = 3600,
        metadata: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Generate a presigned URL for file upload.

        Args:
            key: S3 object key (path)
            content_type: MIME type of the file
            expires_in: URL expiration in seconds (default 1 hour)
            metadata: Optional metadata to attach

        Returns:
            Dict with upload_url and key
        """
        try:
            params = {
                "Bucket": self._bucket,
                "Key": key,
                "ContentType": content_type,
            }

            if metadata:
                params["Metadata"] = metadata

            url = self.client.generate_presigned_url(
                "put_object",
                Params=params,
                ExpiresIn=expires_in,
            )

            # DEBUG: Log URL format to verify SigV4 is being used
            has_sigv4 = "X-Amz-Algorithm" in url
            has_sigv2 = "AWSAccessKeyId" in url
            logger.debug("[S3Client] generate_upload_url: SigV4=%s, SigV2=%s", has_sigv4, has_sigv2)
            logger.debug("[S3Client] URL prefix: %s...", url[:100])

            return {
                "success": True,
                "upload_url": url,
                "key": key,
                "bucket": self._bucket,
                "content_type": content_type,
                "expires_in": expires_in,
            }
        except Exception as e:
            debug_error(e, "s3_generate_upload_url", {"key": key, "content_type": content_type})
            return {
                "success": False,
                "error": str(e),
            }

    def generate_download_url(
        self,
        key: str,
        expires_in: int = 3600,
        filename: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate a presigned URL for file download.

        Args:
            key: S3 object key (path)
            expires_in: URL expiration in seconds (default 1 hour)
            filename: Optional filename for Content-Disposition

        Returns:
            Dict with download_url and key
        """
        try:
            params = {
                "Bucket": self._bucket,
                "Key": key,
            }

            if filename:
                params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'

            url = self.client.generate_presigned_url(
                "get_object",
                Params=params,
                ExpiresIn=expires_in,
            )

            return {
                "success": True,
                "download_url": url,
                "key": key,
                "expires_in": expires_in,
            }
        except Exception as e:
            debug_error(e, "s3_generate_download_url", {"key": key})
            return {
                "success": False,
                "error": str(e),
            }

    def generate_presigned_post(
        self,
        key: str,
        content_type: str = "application/octet-stream",
        expires_in: int = 300,
        content_length_range: tuple = (1, 104857600),
        metadata: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Generate a presigned POST URL for browser-based file uploads.

        This method creates a presigned POST form that allows direct uploads
        to S3 from browsers with server-side validation of file size and type.

        Args:
            key: S3 object key (path) where the file will be stored.
            content_type: MIME type of the file (e.g., "text/csv", "application/pdf").
            expires_in: URL expiration in seconds (default 300 = 5 minutes).
            content_length_range: Tuple of (min_bytes, max_bytes) for file size
                validation. Default is (1, 104857600) = 1 byte to 100 MB.
            metadata: Optional dict of custom metadata to attach to the object.
                Keys will be prefixed with "x-amz-meta-" automatically.

        Returns:
            Dict with the following keys on success:
            - success: True
            - url: The S3 endpoint URL for POST
            - fields: Dict of form fields to include in the upload
            - key: The S3 object key
            - bucket: The bucket name
            - expires_in: Expiration time in seconds
            - expires_at: ISO 8601 timestamp when URL expires
            - max_file_size_bytes: Maximum allowed file size
            - temp_cleanup_warning: Warning about auto-deletion policy

            On failure:
            - success: False
            - error: Error message string
        """
        try:
            from datetime import timedelta

            # Build conditions for the POST policy
            conditions = [
                {"bucket": self._bucket},
                ["starts-with", "$key", key.rsplit("/", 1)[0] + "/" if "/" in key else ""],
                ["content-length-range", content_length_range[0], content_length_range[1]],
                {"Content-Type": content_type},
            ]

            # Build fields
            fields = {
                "Content-Type": content_type,
            }

            # Add metadata if provided
            if metadata:
                for meta_key, meta_value in metadata.items():
                    amz_key = f"x-amz-meta-{meta_key}"
                    fields[amz_key] = meta_value
                    conditions.append({amz_key: meta_value})

            # Generate presigned POST
            response = self.client.generate_presigned_post(
                Bucket=self._bucket,
                Key=key,
                Fields=fields,
                Conditions=conditions,
                ExpiresIn=expires_in,
            )

            # Calculate expiration timestamp
            expires_at = (datetime.utcnow() + timedelta(seconds=expires_in)).isoformat() + "Z"

            # DEBUG: Log URL format to verify SigV4 is being used
            logger.debug("[S3Client] generate_presigned_post: key=%s, expires_in=%s", key, expires_in)

            return {
                "success": True,
                "url": response["url"],
                "fields": response["fields"],
                "key": key,
                "bucket": self._bucket,
                "expires_in": expires_in,
                "expires_at": expires_at,
                "max_file_size_bytes": content_length_range[1],
                "temp_cleanup_warning": "File will be auto-deleted after 24 hours if not processed",
            }

        except Exception as e:
            debug_error(e, "s3_generate_presigned_post", {
                "key": key,
                "content_type": content_type,
                "content_length_range": content_length_range,
            })
            return {
                "success": False,
                "error": str(e),
            }

    def get_file_metadata(
        self,
        key: str,
        retry_count: int = 3,
        retry_delay: float = 1.0,
    ) -> Dict[str, Any]:
        """
        Get metadata for an S3 object with retry logic and exponential backoff.

        This method uses head_object to retrieve file metadata without downloading
        the file content. Includes retry logic for eventual consistency scenarios
        (e.g., file just uploaded may not be immediately visible).

        Args:
            key: S3 object key (path) to check.
            retry_count: Number of retry attempts for 404 errors (default 3).
            retry_delay: Initial delay between retries in seconds (default 1.0).
                Uses exponential backoff: 1s, 2s, 4s, etc.

        Returns:
            Dict with the following keys on success:
            - success: True
            - exists: True
            - key: The S3 object key
            - content_type: MIME type of the file
            - content_length: File size in bytes
            - file_size_human: Human-readable file size (e.g., "2.5 MB")
            - last_modified: ISO 8601 timestamp of last modification
            - etag: S3 ETag (MD5 hash for non-multipart uploads)
            - metadata: Dict of custom metadata (x-amz-meta-* headers)

            On file not found (after retries):
            - success: True
            - exists: False
            - key: The S3 object key
            - error: "File not found after N retries"

            On other errors:
            - success: False
            - error: Error message string
        """
        import time

        def _format_file_size(size_bytes: int) -> str:
            """Convert bytes to human-readable format."""
            for unit in ["B", "KB", "MB", "GB", "TB"]:
                if size_bytes < 1024:
                    return f"{size_bytes:.1f} {unit}" if unit != "B" else f"{size_bytes} {unit}"
                size_bytes /= 1024
            return f"{size_bytes:.1f} PB"

        last_error = None
        current_delay = retry_delay

        for attempt in range(retry_count):
            try:
                response = self.client.head_object(
                    Bucket=self._bucket,
                    Key=key,
                )

                # Extract metadata
                content_type = response.get("ContentType", "application/octet-stream")
                content_length = response.get("ContentLength", 0)
                last_modified = response.get("LastModified")
                etag = response.get("ETag", "").strip('"')
                custom_metadata = response.get("Metadata", {})

                return {
                    "success": True,
                    "exists": True,
                    "key": key,
                    "content_type": content_type,
                    "content_length": content_length,
                    "file_size_human": _format_file_size(content_length),
                    "last_modified": last_modified.isoformat() if last_modified else None,
                    "etag": etag,
                    "metadata": custom_metadata,
                }

            except self.client.exceptions.NoSuchKey:
                last_error = "NoSuchKey"
                if attempt < retry_count - 1:
                    logger.debug(
                        "[S3Client] get_file_metadata: File not found (attempt %d/%d), "
                        "retrying in %.1fs...",
                        attempt + 1, retry_count, current_delay
                    )
                    time.sleep(current_delay)
                    current_delay *= 2  # Exponential backoff

            except Exception as e:
                # Check if it's a 404 from ClientError
                error_code = getattr(e, "response", {}).get("Error", {}).get("Code", "")
                if error_code == "404" or "Not Found" in str(e):
                    last_error = "404"
                    if attempt < retry_count - 1:
                        logger.debug(
                            "[S3Client] get_file_metadata: 404 error (attempt %d/%d), "
                            "retrying in %.1fs...",
                            attempt + 1, retry_count, current_delay
                        )
                        time.sleep(current_delay)
                        current_delay *= 2
                else:
                    # Non-retryable error
                    debug_error(e, "s3_get_file_metadata", {"key": key, "attempt": attempt + 1})
                    return {
                        "success": False,
                        "error": str(e),
                    }

        # All retries exhausted - file not found
        logger.warning(
            "[S3Client] get_file_metadata: File not found after %d retries: %s",
            retry_count, key
        )
        return {
            "success": True,
            "exists": False,
            "key": key,
            "error": f"File not found after {retry_count} retries",
        }

    # =========================================================================
    # Direct File Operations
    # =========================================================================

    def upload_file(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
        metadata: Optional[Dict[str, str]] = None,
    ) -> bool:
        """
        Upload file data directly to S3.

        Args:
            key: S3 object key (path)
            data: File data as bytes
            content_type: MIME type
            metadata: Optional metadata

        Returns:
            True if successful
        """
        try:
            params = {
                "Bucket": self._bucket,
                "Key": key,
                "Body": data,
                "ContentType": content_type,
            }

            if metadata:
                params["Metadata"] = metadata

            self.client.put_object(**params)
            return True
        except Exception as e:
            debug_error(e, "s3_upload_file", {"key": key, "content_type": content_type})
            return False

    def download_file(self, key: str) -> Optional[bytes]:
        """
        Download file data from S3.

        Args:
            key: S3 object key (path)

        Returns:
            File data as bytes, or None if error
        """
        try:
            response = self.client.get_object(
                Bucket=self._bucket,
                Key=key,
            )
            return response["Body"].read()
        except Exception as e:
            debug_error(e, "s3_download_file", {"key": key})
            return None

    def delete_file(self, key: str) -> bool:
        """
        Delete a file from S3.

        Args:
            key: S3 object key (path)

        Returns:
            True if successful
        """
        try:
            self.client.delete_object(
                Bucket=self._bucket,
                Key=key,
            )
            return True
        except Exception as e:
            debug_error(e, "s3_delete_file", {"key": key})
            return False

    def copy_file(self, source_key: str, dest_key: str) -> bool:
        """
        Copy a file within the bucket.

        Args:
            source_key: Source object key
            dest_key: Destination object key

        Returns:
            True if successful
        """
        try:
            self.client.copy_object(
                Bucket=self._bucket,
                CopySource={"Bucket": self._bucket, "Key": source_key},
                Key=dest_key,
            )
            return True
        except Exception as e:
            debug_error(e, "s3_copy_file", {"source_key": source_key, "dest_key": dest_key})
            return False

    def move_file(self, source_key: str, dest_key: str) -> bool:
        """
        Move a file (copy then delete).

        Args:
            source_key: Source object key
            dest_key: Destination object key

        Returns:
            True if successful
        """
        if self.copy_file(source_key, dest_key):
            return self.delete_file(source_key)
        return False

    def list_files(
        self,
        prefix: str,
        max_keys: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        List files with a given prefix.

        Args:
            prefix: Key prefix to filter
            max_keys: Maximum files to return

        Returns:
            List of file info dicts
        """
        try:
            response = self.client.list_objects_v2(
                Bucket=self._bucket,
                Prefix=prefix,
                MaxKeys=max_keys,
            )

            files = []
            for obj in response.get("Contents", []):
                files.append({
                    "key": obj["Key"],
                    "size": obj["Size"],
                    "last_modified": obj["LastModified"].isoformat(),
                })

            return files
        except Exception as e:
            debug_error(e, "s3_list_files", {"prefix": prefix})
            return []

    def file_exists(self, key: str) -> bool:
        """
        Check if a file exists.

        Args:
            key: S3 object key

        Returns:
            True if file exists
        """
        try:
            self.client.head_object(Bucket=self._bucket, Key=key)
            return True
        except Exception:
            return False

    # =========================================================================
    # Path Generation Helpers
    # =========================================================================

    def get_nf_path(
        self,
        nf_id: str,
        filename: str,
        year_month: Optional[str] = None,
    ) -> str:
        """
        Generate path for NF file.

        Args:
            nf_id: NF identifier
            filename: File name (e.g., "original.pdf")
            year_month: Optional YYYY/MM, defaults to current

        Returns:
            S3 key path
        """
        if not year_month:
            now = datetime.utcnow()
            year_month = f"{now.year}/{now.month:02d}"

        return f"notas-fiscais/{year_month}/{nf_id}/{filename}"

    def get_evidence_path(
        self,
        movement_id: str,
        evidence_type: str,
        filename: str,
    ) -> str:
        """
        Generate path for movement evidence.

        Args:
            movement_id: Movement identifier
            evidence_type: Type (photos, signatures, documents)
            filename: File name

        Returns:
            S3 key path
        """
        return f"evidences/{movement_id}/{evidence_type}/{filename}"

    def get_inventory_path(
        self,
        campaign_id: str,
        file_type: str,
        filename: str,
    ) -> str:
        """
        Generate path for inventory campaign file.

        Args:
            campaign_id: Campaign identifier
            file_type: Type (photos, exports)
            filename: File name

        Returns:
            S3 key path
        """
        return f"inventories/{campaign_id}/{file_type}/{filename}"

    def get_temp_path(self, filename: str) -> str:
        """
        Generate path for temporary upload.

        Files in temp/ are auto-deleted after 24 hours.

        Args:
            filename: File name

        Returns:
            S3 key path in temp folder
        """
        import uuid
        import unicodedata

        unique = str(uuid.uuid4())[:8]
        # NFC normalize filename to prevent S3 NoSuchKey errors
        # macOS/browsers may use NFD (decomposed), S3 treats keys as raw bytes
        normalized_filename = unicodedata.normalize("NFC", filename)
        return f"temp/uploads/{unique}_{normalized_filename}"

    def move_from_temp(self, temp_key: str, final_key: str) -> bool:
        """
        Move file from temp staging to final location.

        Args:
            temp_key: Temporary key (from get_temp_path)
            final_key: Final destination key

        Returns:
            True if successful
        """
        return self.move_file(temp_key, final_key)

    # =========================================================================
    # NF Specific Operations
    # =========================================================================

    def upload_nf_xml(
        self,
        nf_id: str,
        xml_content: str,
        year_month: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Upload NF XML file.

        Args:
            nf_id: NF identifier
            xml_content: XML content as string
            year_month: Optional YYYY/MM

        Returns:
            Dict with success status and key
        """
        key = self.get_nf_path(nf_id, "original.xml", year_month)
        success = self.upload_file(
            key=key,
            data=xml_content.encode("utf-8"),
            content_type="application/xml",
        )
        return {
            "success": success,
            "key": key if success else None,
        }

    def upload_nf_extraction(
        self,
        nf_id: str,
        extraction: Dict[str, Any],
        year_month: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Upload NF extraction result as JSON.

        Args:
            nf_id: NF identifier
            extraction: Extraction dict
            year_month: Optional YYYY/MM

        Returns:
            Dict with success status and key
        """
        import json

        key = self.get_nf_path(nf_id, "extraction.json", year_month)
        success = self.upload_file(
            key=key,
            data=json.dumps(extraction, ensure_ascii=False, indent=2).encode("utf-8"),
            content_type="application/json",
        )
        return {
            "success": success,
            "key": key if success else None,
        }

    def get_nf_files(self, nf_id: str) -> List[Dict[str, Any]]:
        """
        List all files for an NF.

        Args:
            nf_id: NF identifier

        Returns:
            List of file info dicts
        """
        # Search in recent months
        files = []
        now = datetime.utcnow()

        for months_ago in range(12):  # Search last 12 months
            month = now.month - months_ago
            year = now.year
            while month <= 0:
                month += 12
                year -= 1

            prefix = f"notas-fiscais/{year}/{month:02d}/{nf_id}/"
            month_files = self.list_files(prefix)

            if month_files:
                files.extend(month_files)
                break  # Found files, stop searching

        return files


# =============================================================================
# Equipment Documentation Client (for Bedrock Knowledge Base)
# =============================================================================


class EquipmentDocsS3Client:
    """
    S3 client for equipment documentation storage.

    Stores documents in a structure optimized for Bedrock Knowledge Base:
    - equipment-docs/{part_number}/{doc_type}/{filename}
    - equipment-docs/{part_number}/{doc_type}/{filename}.metadata.json

    The .metadata.json sidecar files contain KB indexing metadata:
    - part_number, manufacturer, description, document_type
    - source_url, download_timestamp

    Example:
        client = EquipmentDocsS3Client()
        result = client.upload_equipment_document(
            part_number="ABC-123",
            document_type="manual",
            filename="user_manual.pdf",
            content=pdf_bytes,
            metadata={"manufacturer": "Cisco", "source_url": "..."}
        )
    """

    # Default bucket for equipment documentation
    DEFAULT_BUCKET = "faiston-one-sga-equipment-docs-prod"

    def __init__(self, bucket_name: Optional[str] = None):
        """
        Initialize the equipment docs client.

        Args:
            bucket_name: Override bucket name (for testing)
        """
        self._bucket = bucket_name or os.environ.get(
            "EQUIPMENT_DOCS_BUCKET",
            self.DEFAULT_BUCKET
        )

    @property
    def bucket(self) -> str:
        """Get bucket name."""
        return self._bucket

    @property
    def client(self):
        """Get S3 client with lazy loading."""
        return _get_s3_client()

    # =========================================================================
    # Path Generation
    # =========================================================================

    def get_doc_path(
        self,
        part_number: str,
        doc_type: str,
        filename: str,
    ) -> str:
        """
        Generate S3 key for equipment document.

        Structure: equipment-docs/{part_number}/{doc_type}/{filename}

        Args:
            part_number: Equipment part number
            doc_type: Type (manual, datasheet, spec, guide, firmware, driver)
            filename: Document filename

        Returns:
            S3 key path
        """
        # Sanitize part number for use as path component
        safe_pn = part_number.replace("/", "_").replace("\\", "_").strip()
        safe_doc_type = doc_type.lower().replace(" ", "_")
        return f"equipment-docs/{safe_pn}/{safe_doc_type}/{filename}"

    def get_metadata_path(self, doc_key: str) -> str:
        """
        Get metadata sidecar path for a document.

        Args:
            doc_key: Document S3 key

        Returns:
            Metadata JSON key path
        """
        return f"{doc_key}.metadata.json"

    # =========================================================================
    # Document Upload
    # =========================================================================

    def upload_equipment_document(
        self,
        part_number: str,
        document_type: str,
        filename: str,
        content: bytes,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Upload equipment document with KB metadata.

        Creates both the document file and a .metadata.json sidecar
        file that Bedrock Knowledge Base uses for indexing.

        Args:
            part_number: Equipment part number
            document_type: Type (manual, datasheet, spec, etc.)
            filename: Document filename
            content: File content as bytes
            metadata: Additional metadata (manufacturer, source_url, etc.)

        Returns:
            Dict with success, doc_key, metadata_key, s3_uri
        """
        import json

        try:
            # Generate paths
            doc_key = self.get_doc_path(part_number, document_type, filename)
            meta_key = self.get_metadata_path(doc_key)

            # Determine content type
            content_type = self._get_content_type(filename)

            # Upload document
            self.client.put_object(
                Bucket=self._bucket,
                Key=doc_key,
                Body=content,
                ContentType=content_type,
            )

            # Build KB metadata
            kb_metadata = {
                "part_number": part_number,
                "document_type": document_type,
                "filename": filename,
                "content_type": content_type,
                "file_size_bytes": len(content),
                "upload_timestamp": datetime.utcnow().isoformat() + "Z",
            }

            # Merge additional metadata
            if metadata:
                kb_metadata.update(metadata)

            # Upload metadata sidecar
            self.client.put_object(
                Bucket=self._bucket,
                Key=meta_key,
                Body=json.dumps(kb_metadata, ensure_ascii=False, indent=2).encode("utf-8"),
                ContentType="application/json",
            )

            logger.info("[EquipmentDocs] Uploaded: %s", doc_key)

            return {
                "success": True,
                "doc_key": doc_key,
                "metadata_key": meta_key,
                "s3_uri": f"s3://{self._bucket}/{doc_key}",
                "bucket": self._bucket,
            }

        except Exception as e:
            debug_error(e, "equipment_docs_upload", {"part_number": part_number, "doc_type": document_type, "filename": filename})
            return {
                "success": False,
                "error": str(e),
            }

    def _get_content_type(self, filename: str) -> str:
        """Get MIME type from filename."""
        ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
        content_types = {
            "pdf": "application/pdf",
            "doc": "application/msword",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "xls": "application/vnd.ms-excel",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "txt": "text/plain",
            "html": "text/html",
            "htm": "text/html",
            "xml": "application/xml",
            "json": "application/json",
            "zip": "application/zip",
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
        }
        return content_types.get(ext, "application/octet-stream")

    # =========================================================================
    # Document Retrieval
    # =========================================================================

    def list_documents_for_part(
        self,
        part_number: str,
        doc_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        List all documents for a part number.

        Args:
            part_number: Equipment part number
            doc_type: Optional filter by document type

        Returns:
            List of document info dicts
        """
        safe_pn = part_number.replace("/", "_").replace("\\", "_").strip()

        if doc_type:
            prefix = f"equipment-docs/{safe_pn}/{doc_type.lower()}/"
        else:
            prefix = f"equipment-docs/{safe_pn}/"

        try:
            response = self.client.list_objects_v2(
                Bucket=self._bucket,
                Prefix=prefix,
                MaxKeys=100,
            )

            documents = []
            for obj in response.get("Contents", []):
                key = obj["Key"]
                # Skip metadata sidecar files
                if key.endswith(".metadata.json"):
                    continue

                documents.append({
                    "key": key,
                    "s3_uri": f"s3://{self._bucket}/{key}",
                    "size": obj["Size"],
                    "last_modified": obj["LastModified"].isoformat(),
                    "filename": key.rsplit("/", 1)[-1],
                })

            return documents

        except Exception as e:
            debug_error(e, "equipment_docs_list", {"part_number": part_number, "doc_type": doc_type})
            return []

    def get_document_metadata(self, doc_key: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a document.

        Args:
            doc_key: Document S3 key

        Returns:
            Metadata dict or None
        """
        import json

        try:
            meta_key = self.get_metadata_path(doc_key)
            response = self.client.get_object(
                Bucket=self._bucket,
                Key=meta_key,
            )
            return json.loads(response["Body"].read().decode("utf-8"))
        except Exception as e:
            debug_error(e, "equipment_docs_get_metadata", {"doc_key": doc_key})
            return None

    def generate_download_url(
        self,
        doc_key: str,
        expires_in: int = 3600,
    ) -> Optional[str]:
        """
        Generate presigned download URL for a document.

        Args:
            doc_key: Document S3 key
            expires_in: URL expiration in seconds

        Returns:
            Presigned URL or None
        """
        try:
            url = self.client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": self._bucket,
                    "Key": doc_key,
                },
                ExpiresIn=expires_in,
            )
            return url
        except Exception as e:
            debug_error(e, "equipment_docs_generate_url", {"doc_key": doc_key})
            return None

    def generate_download_url_from_uri(
        self,
        s3_uri: str,
        expires_in: int = 3600,
    ) -> Optional[str]:
        """
        Generate presigned download URL from S3 URI.

        Args:
            s3_uri: S3 URI (s3://bucket/key)
            expires_in: URL expiration in seconds

        Returns:
            Presigned URL or None
        """
        # Parse S3 URI
        if not s3_uri.startswith("s3://"):
            return None

        parts = s3_uri[5:].split("/", 1)
        if len(parts) != 2:
            return None

        bucket, key = parts

        try:
            url = self.client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": bucket,
                    "Key": key,
                },
                ExpiresIn=expires_in,
            )
            return url
        except Exception as e:
            debug_error(e, "equipment_docs_url_from_uri", {"s3_uri": s3_uri})
            return None

    # =========================================================================
    # Deletion
    # =========================================================================

    def delete_document(self, doc_key: str) -> bool:
        """
        Delete a document and its metadata.

        Args:
            doc_key: Document S3 key

        Returns:
            True if successful
        """
        try:
            # Delete document
            self.client.delete_object(Bucket=self._bucket, Key=doc_key)

            # Delete metadata sidecar
            meta_key = self.get_metadata_path(doc_key)
            self.client.delete_object(Bucket=self._bucket, Key=meta_key)

            logger.info("[EquipmentDocs] Deleted: %s", doc_key)
            return True

        except Exception as e:
            debug_error(e, "equipment_docs_delete", {"doc_key": doc_key})
            return False

    def document_exists(self, part_number: str, doc_type: str, filename: str) -> bool:
        """
        Check if a document already exists.

        Args:
            part_number: Equipment part number
            doc_type: Document type
            filename: Document filename

        Returns:
            True if exists
        """
        doc_key = self.get_doc_path(part_number, doc_type, filename)
        try:
            self.client.head_object(Bucket=self._bucket, Key=doc_key)
            return True
        except Exception:
            return False
