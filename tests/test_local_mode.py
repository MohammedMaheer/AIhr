"""Smoke tests for the SMARTHR_LOCAL_MODE shim layer.

These verify that when ``SMARTHR_LOCAL_MODE=1`` is set, the ``vps_local``
package transparently replaces the Google Cloud SDKs with local backends.
The tests run in-process (no VPS or Postgres required) and are safe to run
in CI.

Run with::

    SMARTHR_LOCAL_MODE=1 pytest tests/test_local_mode.py
"""
from __future__ import annotations

import importlib
import os
import sys

import pytest


@pytest.fixture(autouse=True)
def _enable_local_mode(monkeypatch, tmp_path):
    """Set the env flags ``vps_local`` reads on import."""
    monkeypatch.setenv("SMARTHR_LOCAL_MODE", "1")
    monkeypatch.setenv("SMARTHR_STORAGE_ROOT", str(tmp_path))
    # Drop any cached modules so the shim's sys.modules patching runs cleanly
    for mod in list(sys.modules):
        if mod.startswith(("google.cloud", "vertexai", "vps_local")):
            sys.modules.pop(mod, None)
    yield


def test_shim_replaces_google_cloud_storage():
    """`from google.cloud import storage` must yield the shim, not the real SDK."""
    importlib.import_module("vps_local")
    from google.cloud import storage  # type: ignore

    # The shim module name lives under vps_local.*
    assert storage.__name__.startswith("vps_local"), (
        f"expected vps_local.* shim, got {storage.__name__}"
    )
    # The shim exposes a Client class
    assert hasattr(storage, "Client"), "shim missing Client"


def test_shim_replaces_discoveryengine():
    """The Discovery Engine SDK is shimmed to pgvector."""
    importlib.import_module("vps_local")
    from google.cloud import discoveryengine_v1  # type: ignore

    assert discoveryengine_v1.__name__.startswith("vps_local"), (
        f"expected vps_local.* shim, got {discoveryengine_v1.__name__}"
    )


def test_shim_replaces_vertexai():
    """The Vertex AI SDK is shimmed."""
    importlib.import_module("vps_local")
    import vertexai  # type: ignore

    assert vertexai.__name__.startswith("vps_local"), (
        f"expected vps_local.* shim, got {vertexai.__name__}"
    )


def test_storage_bucket_writes_to_filesystem(tmp_path, monkeypatch):
    """Uploading a blob via the shimmed Storage client writes a real file."""
    monkeypatch.setenv("SMARTHR_STORAGE_ROOT", str(tmp_path))
    importlib.import_module("vps_local")
    from google.cloud import storage  # type: ignore

    client = storage.Client()
    bucket = client.bucket("test-bucket")
    blob = bucket.blob("resumes/hello.txt")
    blob.upload_from_string("hello world")

    # The shim layout is documented: storage_root/<bucket>/<blob_path>
    candidates = list(tmp_path.rglob("hello.txt"))
    assert candidates, f"shim did not create any file under {tmp_path}"
    assert candidates[0].read_text() == "hello world"


def test_setup_gcs_credentials_skips_in_local_mode(monkeypatch):
    """``main.setup_gcs_credentials`` returns True silently in local mode.

    We import lazily because main.py is heavyweight; if the import fails
    (e.g. missing optional dep on a CI box) we skip rather than fail this
    smoke test — its purpose is to verify the local-mode path, not import
    cleanliness of every transitive dependency.
    """
    importlib.import_module("vps_local")
    try:
        import main  # noqa: F401
    except Exception as e:  # pragma: no cover - env-dependent
        pytest.skip(f"main.py not importable in this env: {e}")
    assert main.setup_gcs_credentials() is True
