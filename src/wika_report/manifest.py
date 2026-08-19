import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from wika_report.models import ArtifactItem, RevisionManifest

logger = logging.getLogger("wika_report")


def calculate_sha256(file_path: Path) -> str:
    """Вычисляет SHA-256 хеш файла."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def create_artifact_item(
    file_path: Path,
    base_dir: Path,
    file_type: str,
    category: Optional[str] = None
) -> ArtifactItem:
    """Создаёт элемент артефакта с расчётом размера и SHA-256."""
    size_bytes = file_path.stat().st_size
    sha256_hash = calculate_sha256(file_path)
    rel_path = file_path.relative_to(base_dir).as_posix()
    return ArtifactItem(
        name=file_path.name,
        relative_path=rel_path,
        file_type=file_type,
        size_bytes=size_bytes,
        sha256=sha256_hash,
        category=category
    )


def write_manifest(
    manifest_path: Path,
    log_no: str,
    revision_id: str,
    metadata: Dict[str, Any],
    metrics: Dict[str, Any],
    artifacts: List[ArtifactItem],
    created_by: str = "operator"
) -> RevisionManifest:
    """Записывает manifest.json в каталог ревизии."""
    manifest = RevisionManifest(
        manifest_version="1.0",
        core_version="1.0.0",
        log_no=log_no,
        revision_id=revision_id,
        created_at_utc=datetime.now(timezone.utc).isoformat(),
        created_by=created_by,
        metadata=metadata,
        metrics=metrics,
        artifacts=artifacts
    )
    
    data = {
        "manifest_version": manifest.manifest_version,
        "core_version": manifest.core_version,
        "log_no": manifest.log_no,
        "revision_id": manifest.revision_id,
        "created_at_utc": manifest.created_at_utc,
        "created_by": manifest.created_by,
        "metadata": manifest.metadata,
        "metrics": manifest.metrics,
        "artifacts": [
            {
                "name": a.name,
                "relative_path": a.relative_path,
                "file_type": a.file_type,
                "size_bytes": a.size_bytes,
                "sha256": a.sha256,
                "category": a.category
            }
            for a in manifest.artifacts
        ]
    }
    
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        
    logger.info(f"Created revision manifest: {manifest_path}")
    return manifest
