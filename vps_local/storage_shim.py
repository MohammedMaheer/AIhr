"""
storage_shim — drop-in replacement for `google.cloud.storage`.

Backs onto a local directory (default: /app/storage/resumes).
Maps gs://<bucket>/<key> → <SMARTHR_STORAGE_ROOT>/<bucket>/<key>.
Implements the small subset of the GCS Python SDK that main.py actually uses:
  - storage.Client()  -> Client
  - client.bucket(name) -> Bucket
  - client.create_bucket(bucket, location=...) -> Bucket
  - client.list_blobs(bucket_or_name, prefix=..., max_results=...) -> Iterator[Blob]
  - bucket.exists() -> bool
  - bucket.blob(name) -> Blob
  - blob.exists() -> bool
  - blob.upload_from_string(data, content_type=...)
  - blob.upload_from_file(file_obj, content_type=...)
  - blob.download_as_bytes() -> bytes
  - blob.download_as_text() -> str
  - blob.generate_signed_url(...) -> URL  (returns local /api/download-resume URL)
  - blob.public_url, blob.name, blob.size, blob.content_type
"""
from __future__ import annotations
import os
import shutil
import mimetypes
from pathlib import Path
from typing import Iterator, Optional, Union, BinaryIO
from urllib.parse import quote

# Root for local "GCS" storage. Buckets become subdirectories.
STORAGE_ROOT = Path(os.environ.get("SMARTHR_STORAGE_ROOT", "/app/storage")).resolve()
STORAGE_ROOT.mkdir(parents=True, exist_ok=True)


class _NotFound(Exception):
    pass


class Blob:
    def __init__(self, bucket: "Bucket", name: str):
        self.bucket = bucket
        self.name = name
        self._path = (bucket._root / name).resolve()

    # Properties / metadata
    @property
    def size(self) -> Optional[int]:
        try:
            return self._path.stat().st_size
        except FileNotFoundError:
            return None

    @property
    def content_type(self) -> Optional[str]:
        ctype, _ = mimetypes.guess_type(self.name)
        return ctype

    @property
    def public_url(self) -> str:
        # Local mode: serve via app endpoint. main.py /api/download-resume
        # accepts ?path=<filename>, so generate a relative URL to it.
        return f"/api/download-resume?path={quote(self.name)}"

    @property
    def media_link(self) -> str:
        return self.public_url

    # Existence
    def exists(self, client=None) -> bool:
        return self._path.is_file()

    # Uploads
    def upload_from_string(self, data, content_type: Optional[str] = None, **kwargs):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, str):
            data = data.encode("utf-8")
        self._path.write_bytes(data)

    def upload_from_file(self, file_obj: BinaryIO, content_type: Optional[str] = None,
                         rewind: bool = False, size: Optional[int] = None, **kwargs):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if rewind and hasattr(file_obj, "seek"):
            file_obj.seek(0)
        with self._path.open("wb") as f:
            shutil.copyfileobj(file_obj, f)

    def upload_from_filename(self, filename: str, content_type: Optional[str] = None, **kwargs):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(filename, self._path)

    # Downloads
    def download_as_bytes(self, client=None, **kwargs) -> bytes:
        if not self._path.is_file():
            raise _NotFound(f"Blob not found: {self.name}")
        return self._path.read_bytes()

    def download_as_string(self, client=None, **kwargs) -> bytes:
        return self.download_as_bytes()

    def download_as_text(self, client=None, encoding: str = "utf-8", **kwargs) -> str:
        return self.download_as_bytes().decode(encoding)

    def download_to_filename(self, filename: str, client=None, **kwargs):
        if not self._path.is_file():
            raise _NotFound(f"Blob not found: {self.name}")
        shutil.copy2(self._path, filename)

    def delete(self, client=None, **kwargs):
        try:
            self._path.unlink()
        except FileNotFoundError:
            pass

    def generate_signed_url(self, *args, **kwargs) -> str:
        # No real signing; return local download URL.
        return self.public_url

    def reload(self, client=None, **kwargs):
        # No metadata to refresh.
        return self

    def patch(self, client=None, **kwargs):
        return self


class Bucket:
    def __init__(self, client: "Client", name: str):
        self.client = client
        self.name = name
        self._root = (STORAGE_ROOT / name).resolve()

    def exists(self, client=None) -> bool:
        return self._root.is_dir()

    def blob(self, name: str) -> Blob:
        return Blob(self, name)

    def create(self, location=None, **kwargs):
        self._root.mkdir(parents=True, exist_ok=True)
        return self

    def list_blobs(self, prefix: Optional[str] = None,
                   max_results: Optional[int] = None,
                   **kwargs) -> Iterator[Blob]:
        return self.client.list_blobs(self, prefix=prefix, max_results=max_results)

    def delete(self, force: bool = False, **kwargs):
        if force and self._root.exists():
            shutil.rmtree(self._root)


class Client:
    def __init__(self, project=None, credentials=None, **kwargs):
        self.project = project or os.environ.get("SMARTHR_PROJECT_ID", "smarthr-local")
        STORAGE_ROOT.mkdir(parents=True, exist_ok=True)

    def bucket(self, name: str) -> Bucket:
        return Bucket(self, name)

    def get_bucket(self, name: str) -> Bucket:
        b = Bucket(self, name)
        if not b.exists():
            raise _NotFound(f"Bucket not found: {name}")
        return b

    def create_bucket(self, bucket_or_name, location=None, project=None, **kwargs) -> Bucket:
        name = bucket_or_name.name if isinstance(bucket_or_name, Bucket) else bucket_or_name
        b = Bucket(self, name)
        b.create()
        return b

    def list_blobs(self, bucket_or_name, prefix: Optional[str] = None,
                   max_results: Optional[int] = None, **kwargs) -> Iterator[Blob]:
        bucket = bucket_or_name if isinstance(bucket_or_name, Bucket) else self.bucket(bucket_or_name)
        if not bucket._root.is_dir():
            return iter([])
        prefix_path = bucket._root / prefix if prefix else bucket._root
        # Walk the bucket; yield blobs whose relative path matches the prefix.
        results = []
        if prefix and not prefix_path.exists():
            # Prefix could be a path-prefix (not full directory) — fall back to filtering.
            for p in bucket._root.rglob("*"):
                if p.is_file():
                    rel = str(p.relative_to(bucket._root))
                    if rel.startswith(prefix):
                        results.append(Blob(bucket, rel))
                        if max_results and len(results) >= max_results:
                            break
        else:
            base = prefix_path if prefix else bucket._root
            for p in base.rglob("*"):
                if p.is_file():
                    rel = str(p.relative_to(bucket._root))
                    results.append(Blob(bucket, rel))
                    if max_results and len(results) >= max_results:
                        break
        return iter(results)

    def list_buckets(self, **kwargs) -> Iterator[Bucket]:
        if not STORAGE_ROOT.is_dir():
            return iter([])
        return iter([Bucket(self, p.name) for p in STORAGE_ROOT.iterdir() if p.is_dir()])


# Module-level exception type, mimicking google.cloud.exceptions
class NotFound(Exception):
    pass


# Convenience aliases the SDK exposes
def get_default_credentials():
    return None, "smarthr-local"
