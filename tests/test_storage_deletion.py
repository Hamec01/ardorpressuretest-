"""Filesystem deletion checks using synthetic files in pytest's temporary directory."""
import json

import pytest

from services.api.storage import LocalFileSystemStorage


def test_staged_file_can_be_restored_or_finalized_after_restarting_storage(tmp_path):
    storage = LocalFileSystemStorage(tmp_path)
    original = tmp_path / "photos" / "манометр.png"
    original.parent.mkdir()
    original.write_bytes(b"synthetic photo")
    staged = storage.stage_file_deletion("photos/манометр.png")
    assert not original.exists()
    receipt_path = (tmp_path / staged.staged_key).with_suffix(".json")
    assert json.loads(receipt_path.read_text())["original_key"] == "photos/манометр.png"
    restarted = LocalFileSystemStorage(tmp_path)
    restarted.restore_file_deletion(staged)
    assert original.read_bytes() == b"synthetic photo"
    assert not receipt_path.exists()
    staged = restarted.stage_file_deletion("photos/манометр.png")
    restarted.finalize_file_deletion(staged)
    restarted.finalize_file_deletion(staged)  # Retrying cleanup is harmless.
    assert not original.exists()
    assert not (tmp_path / ".deletions").exists()


@pytest.mark.parametrize("key", ["../outside.txt", "photos/../../outside.txt", "", "."])
def test_cannot_delete_outside_storage_or_storage_root(tmp_path, key):
    root = tmp_path / "storage"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"must survive")
    with pytest.raises(ValueError):
        LocalFileSystemStorage(root).stage_file_deletion(key)
    assert outside.read_bytes() == b"must survive"
    assert root.exists()


def test_cannot_delete_directories_or_symlink_targets(tmp_path):
    root = tmp_path / "storage"
    directory = root / "directory"
    directory.mkdir(parents=True)
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"must survive")
    (root / "link").symlink_to(outside)
    (root / "internal-link").symlink_to(directory)
    storage = LocalFileSystemStorage(root)
    for key in ("directory", "link", "internal-link"):
        with pytest.raises(ValueError):
            storage.stage_file_deletion(key)
    assert outside.read_bytes() == b"must survive"
    assert directory.exists()


def test_failed_file_move_leaves_original_intact(tmp_path, monkeypatch):
    storage = LocalFileSystemStorage(tmp_path)
    original = tmp_path / "photo.jpg"
    original.write_bytes(b"synthetic photo")

    def fail_move(*args):
        raise PermissionError("simulated rename failure")

    monkeypatch.setattr("services.api.storage.os.replace", fail_move)
    with pytest.raises(PermissionError):
        storage.stage_file_deletion("photo.jpg")
    assert original.read_bytes() == b"synthetic photo"
    assert not list((tmp_path / ".deletions").iterdir())


def test_restore_never_overwrites_a_new_file(tmp_path):
    storage = LocalFileSystemStorage(tmp_path)
    original = tmp_path / "photo.jpg"
    original.write_bytes(b"old")
    staged = storage.stage_file_deletion("photo.jpg")
    original.write_bytes(b"new")
    with pytest.raises(FileExistsError):
        storage.restore_file_deletion(staged)
    assert original.read_bytes() == b"new"
    assert (tmp_path / staged.staged_key).read_bytes() == b"old"
