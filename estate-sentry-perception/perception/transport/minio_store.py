"""MinIO-backed frame storage.

The `minio` client is synchronous, so every call is pushed to a worker thread.
That is not incidental tidiness: an un-offloaded blocking upload inside the event
loop stalls *every* other coroutine in the service — the bus subscription, the
dead-air watchdog, every connected viewer — for the duration of the network
round trip. At 5 fps that is a stall several times a second.
"""

from __future__ import annotations

import asyncio
import io
import logging
import os

from minio import Minio
from minio.error import S3Error

from .protocols import FrameStore

logger = logging.getLogger(__name__)

DEFAULT_BUCKET = "estate-sentry"


class MinioFrameStore(FrameStore):
    """Frame bytes in an S3-compatible bucket."""

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        *,
        bucket: str = DEFAULT_BUCKET,
        secure: bool = False,
    ) -> None:
        self._client = Minio(
            endpoint, access_key=access_key, secret_key=secret_key, secure=secure
        )
        self.bucket = bucket

    @classmethod
    def from_env(cls) -> MinioFrameStore:
        """Build from the same variables docker-compose already passes around."""
        return cls(
            endpoint=os.environ.get("MINIO_ENDPOINT", "localhost:9000"),
            access_key=os.environ.get("MINIO_ACCESS_KEY", "minioadmin"),
            secret_key=os.environ.get("MINIO_SECRET_KEY", "minioadmin"),
            bucket=os.environ.get("MINIO_BUCKET", DEFAULT_BUCKET),
            secure=os.environ.get("MINIO_SECURE", "false").lower() == "true",
        )

    async def ensure_bucket(self) -> None:
        """Create the bucket if absent. Safe to call on every startup."""

        def _ensure() -> None:
            if not self._client.bucket_exists(self.bucket):
                self._client.make_bucket(self.bucket)
                logger.info("created bucket %s", self.bucket)

        await asyncio.to_thread(_ensure)

    async def put(self, key: str, data: bytes, content_type: str = "image/jpeg") -> str:
        def _put() -> None:
            self._client.put_object(
                self.bucket,
                key,
                io.BytesIO(data),
                length=len(data),
                content_type=content_type,
            )

        await asyncio.to_thread(_put)
        return key

    async def get(self, key: str) -> bytes:
        def _get() -> bytes:
            response = None
            try:
                response = self._client.get_object(self.bucket, key)
                return response.read()
            except S3Error as exc:
                if exc.code in {"NoSuchKey", "NoSuchObject"}:
                    raise KeyError(f"no object at {key!r}") from None
                raise
            finally:
                # MinIO's client holds the connection open until both are called;
                # skipping this leaks a pooled connection per fetch, which only
                # shows up as exhaustion after a long run.
                if response is not None:
                    response.close()
                    response.release_conn()

        return await asyncio.to_thread(_get)
