import abc
import shutil
from pathlib import Path
from typing import BinaryIO, Optional
from services.api.config import settings


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


storage: StorageBackend = LocalFileSystemStorage()
