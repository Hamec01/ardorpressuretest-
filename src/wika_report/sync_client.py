import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import httpx

import os
from wika_report.sync_queue import QueueItem, SyncQueue, sync_queue
from wika_report.config import load_config

logger = logging.getLogger("wika_report")


def get_default_server_url() -> str:
    """Определяет базовый URL сервера с приоритетом: env -> config.json -> default fallback."""
    if os.environ.get("ARDOR_SERVER_URL"):
        return os.environ["ARDOR_SERVER_URL"].strip()
    try:
        cfg = load_config(Path("config.json"))
        if cfg.get("server_url"):
            return str(cfg["server_url"]).strip()
    except Exception:
        pass
    return "http://127.0.0.1:8080"


class SyncClient:
    """Клиент для синхронизации локальных ревизий и статусов PipeCloud с FastAPI бэкендом."""

    def __init__(self, base_url: Optional[str] = None, timeout: float = 30.0):
        self.base_url = (base_url or get_default_server_url()).rstrip("/")
        self.timeout = timeout

    def check_health(self) -> bool:
        """Проверяет доступность сервера."""
        try:
            with httpx.Client(base_url=self.base_url, timeout=5.0) as client:
                res = client.get("/api/v1/health")
                return res.status_code == 200 and res.json().get("status") == "ok"
        except Exception as e:
            logger.warning(f"Server health check failed: {e}")
            return False

    def sync_item(self, item: QueueItem, queue: Optional[SyncQueue] = None) -> Dict[str, Any]:
        """Синхронизирует один элемент очереди с сервером."""
        target_queue = queue or sync_queue
        target_queue.update_status(item.operation_id, status="uploading")

        # -------------------------------------------------------------
        # 1. Синхронизация статуса PipeCloud
        # -------------------------------------------------------------
        if getattr(item, "operation_type", "revision_upload") == "pipecloud_status_update":
            try:
                payload = json.loads(item.payload_json or "{}")
                with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
                    res = client.patch(
                        f"/api/v1/tests/{item.log_no}/pipecloud",
                        json={
                            "added": bool(payload.get("added", False)),
                            "idempotency_key": item.operation_id
                        }
                    )
                    res.raise_for_status()
                    data = res.json()
                    receipt_id = f"pc_{item.log_no}_{data.get('pipecloud_added')}"
                    target_queue.update_status(item.operation_id, status="synced", receipt_id=receipt_id)
                    logger.info(f"Successfully synced PipeCloud status for Log {item.log_no}")
                    return data
            except Exception as e:
                err_str = str(e)
                logger.error(f"PipeCloud sync failed for operation {item.operation_id}: {err_str}")
                target_queue.update_status(item.operation_id, status="failed", error=err_str)
                raise

        # -------------------------------------------------------------
        # 2. Синхронизация ревизии лога (Revision Upload)
        # -------------------------------------------------------------
        manifest_path = Path(item.manifest_path) if item.manifest_path else None
        if not manifest_path or not manifest_path.exists():
            err = f"Manifest file not found: {manifest_path}"
            target_queue.update_status(item.operation_id, status="failed", error=err)
            raise FileNotFoundError(err)

        log_dir = manifest_path.parent

        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest_data = json.load(f)

        try:
            with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
                # А. Регистрация сессии синхронизации
                session_payload = {
                    "idempotency_key": item.operation_id,
                    "manifest": manifest_data
                }
                res = client.post("/api/v1/sync/sessions", json=session_payload)
                res.raise_for_status()
                session_resp = res.json()

                if session_resp["status"] == "already_synced":
                    receipt_id = session_resp.get("receipt_id", "already_synced")
                    target_queue.update_status(item.operation_id, status="synced", receipt_id=receipt_id)
                    return {"status": "synced", "receipt_id": receipt_id}

                # Б. Загрузка недостающих артефактов
                missing_shas = set(session_resp.get("missing_artifacts", []))
                for art in manifest_data.get("artifacts", []):
                    if art.get("sha256") in missing_shas:
                        file_path = log_dir / art["relative_path"]
                        if not file_path.exists():
                            raise FileNotFoundError(f"Artifact not found on disk: {file_path}")

                        with open(file_path, "rb") as af:
                            upload_data = {
                                "log_no": item.log_no,
                                "relative_path": art["relative_path"],
                                "sha256": art["sha256"]
                            }
                            files = {"file": (file_path.name, af, "application/octet-stream")}
                            up_res = client.post(
                                f"/api/v1/sync/sessions/{item.revision_id}/upload",
                                data=upload_data,
                                files=files
                            )
                            up_res.raise_for_status()

                # В. Фиксация ревизии (Completion)
                complete_res = client.post(
                    f"/api/v1/sync/sessions/{item.revision_id}/complete",
                    json=session_payload
                )
                complete_res.raise_for_status()
                complete_data = complete_res.json()

                receipt_id = complete_data.get("receipt_id", "receipt_ok")
                target_queue.update_status(item.operation_id, status="synced", receipt_id=receipt_id)
                logger.info(f"Successfully synced Log {item.log_no} (Receipt: {receipt_id})")
                return complete_data

        except Exception as e:
            err_str = str(e)
            logger.error(f"Sync failed for operation {item.operation_id}: {err_str}")
            target_queue.update_status(item.operation_id, status="failed", error=err_str)
            raise

    def sync_all_pending(self, queue: Optional[SyncQueue] = None) -> Dict[str, int]:
        """Синхронизирует все элементы, находящиеся в статусе pending или failed."""
        target_queue = queue or sync_queue
        items = target_queue.get_pending_items()
        summary = {"total": len(items), "synced": 0, "failed": 0}

        for it in items:
            try:
                self.sync_item(it, queue=target_queue)
                summary["synced"] += 1
            except Exception:
                summary["failed"] += 1

        return summary
