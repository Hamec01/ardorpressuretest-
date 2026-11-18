import abc
import errno
import json
import os
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Optional
from services.api.config import settings


@dataclass(frozen=True)
class StagedFileDeletion:
    original_key: str
    staged_key: str


class StorageBackend(abc.ABC):
    @abc.abstractmethod
    def store_file(self, storage_key: str, file_obj: BinaryIO) -> int:
        pass

    @abc.abstractmethod
    def get_file_path(self, storage_key: str) -> Optional[Path]:
        pass

    @abc.abstractmethod
    def file_exists(self, storage_key: str) -> bool:
        pass

    @abc.abstractmethod
    def stage_file_deletion(self, storage_key: str) -> Optional[StagedFileDeletion]:
        pass

    @abc.abstractmethod
    def restore_file_deletion(self, staged: StagedFileDeletion) -> None:
        pass

    @abc.abstractmethod
    def finalize_file_deletion(self, staged: StagedFileDeletion) -> None:
        pass


class LocalFileSystemStorage(StorageBackend):
    def __init__(self, base_path: Optional[Path] = None):
        self.base_path = base_path or settings.storage_dir
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _resolve_path(self, storage_key: str) -> Path:
        return self.base_path / storage_key.lstrip("/\\")

    def store_file(self, storage_key: str, file_obj: BinaryIO) -> int:
        target_path = self._resolve_path(storage_key)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with open(target_path, "wb") as f:
            shutil.copyfileobj(file_obj, f)
        return target_path.stat().st_size

    def get_file_path(self, storage_key: str) -> Optional[Path]:
        target_path = self._resolve_path(storage_key)
        return target_path if target_path.exists() else None

    def file_exists(self, storage_key: str) -> bool:
        return self._resolve_path(storage_key).exists()

    def _resolve_deletion_path(self, storage_key: str) -> Path:
        target_path = self._resolve_path(storage_key)
        root = self.base_path.resolve()
        resolved_target = target_path.resolve()
        if resolved_target == root or not resolved_target.is_relative_to(root):
            raise ValueError("Storage key resolves outside the storage directory.")
        return target_path

    def stage_file_deletion(self, storage_key: str) -> Optional[StagedFileDeletion]:
        source = self._resolve_deletion_path(storage_key)
        if source.is_symlink():
            raise ValueError("Symbolic links cannot be staged for deletion.")
        if not source.exists():
            return None
        if not source.is_file():
            raise ValueError("Storage key does not refer to a file.")

        staged_key = f".deletions/{uuid.uuid4().hex}"
        staged = self._resolve_deletion_path(staged_key)
        staged.parent.mkdir(parents=True, exist_ok=True)
        # Persist the original key before moving the file, so an interrupted request
        # remains recoverable even if its database transaction never commits.
        receipt = staged.with_suffix(".json")
        with receipt.open("x", encoding="utf-8") as receipt_file:
            json.dump({"original_key": storage_key, "staged_key": staged_key}, receipt_file)
            receipt_file.flush()
            os.fsync(receipt_file.fileno())
        try:
            os.replace(source, staged)
        except Exception:
            receipt.unlink(missing_ok=True)
            raise
        return StagedFileDeletion(original_key=storage_key, staged_key=staged_key)

    def restore_file_deletion(self, staged: StagedFileDeletion) -> None:
        source = self._resolve_deletion_path(staged.original_key)
        staged_path = self._resolve_deletion_path(staged.staged_key)
        if not staged_path.exists() and not staged_path.is_symlink():
            return
        if source.exists() or source.is_symlink():
            raise FileExistsError(f"Cannot restore staged file; {staged.original_key} already exists.")
        source.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staged_path, source)
        staged_path.with_suffix(".json").unlink(missing_ok=True)

    def finalize_file_deletion(self, staged: StagedFileDeletion) -> None:
        staged_path = self._resolve_deletion_path(staged.staged_key)
        if staged_path.exists() or staged_path.is_symlink():
            staged_path.unlink()
        staged_path.with_suffix(".json").unlink(missing_ok=True)
        try:
            staged_path.parent.rmdir()
        except OSError as exc:
            if exc.errno not in (errno.ENOTEMPTY, errno.EEXIST, errno.ENOENT):
                raise


storage: StorageBackend = LocalFileSystemStorage()
