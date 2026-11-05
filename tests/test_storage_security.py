import importlib
from urllib.parse import parse_qs, urlsplit

import pytest


@pytest.fixture
def storage(tmp_path, monkeypatch):
    from vps_local import storage_shim
    monkeypatch.setattr(storage_shim, "STORAGE_ROOT", tmp_path.resolve())
    return storage_shim


@pytest.mark.parametrize("name", ["../outside.txt", "/outside.txt", "nested/../../outside.txt", "a\\..\\outside", "", "."])
def test_blob_rejects_paths_outside_bucket(storage, name):
    with pytest.raises(ValueError):
        storage.Client().bucket("qa").blob(name)


@pytest.mark.parametrize("name", ["../escape", "/escape", "", ".", "a/b", "a\\b"])
def test_bucket_rejects_paths_outside_storage(storage, name):
    with pytest.raises(ValueError):
        storage.Client().bucket(name)


def test_storage_roundtrip_and_download_url(storage):
    bucket = storage.Client().create_bucket("qa")
    blob = bucket.blob("nested/QA & CV.txt")
    blob.upload_from_string("Synthetic resume")
    assert blob.download_as_text() == "Synthetic resume"
    query = parse_qs(urlsplit(blob.generate_signed_url()).query)
    assert query == {"file_path": ["gs://qa/nested/QA & CV.txt"]}
    assert [b.name for b in bucket.list_blobs(prefix="nested/")] == [blob.name]
    blob.delete()
    assert not blob.exists()


def test_list_rejects_parent_prefix(storage):
    bucket = storage.Client().create_bucket("qa")
    with pytest.raises(ValueError):
        list(bucket.list_blobs(prefix="../"))


def test_existing_blob_rechecks_symlink_boundary(storage, tmp_path):
    bucket = storage.Client().create_bucket("qa")
    blob = bucket.blob("swap/outside.txt")
    outside = tmp_path / "unrelated"
    outside.mkdir()
    try:
        (bucket._root / "swap").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Symlink creation is unavailable in this environment")
    with pytest.raises(ValueError):
        blob.upload_from_string("must not escape")
    assert not (outside / "outside.txt").exists()
