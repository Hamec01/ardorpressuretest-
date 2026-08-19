import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional


from contextlib import contextmanager


@dataclass
class QueueItem:
    id: int
    operation_id: str
    log_no: str
    revision_id: str
    manifest_path: str
    status: str  # "pending", "uploading", "synced", "failed"
    attempts: int
    last_error: Optional[str]
    receipt_id: Optional[str]
    created_at: str
    synced_at: Optional[str]


class SyncQueue:
    """Локальная SQLite-очередь для офлайн-накопления и синхронизации испытаний."""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            db_path = Path("output") / "sync_queue.db"
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sync_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    operation_id TEXT UNIQUE NOT NULL,
                    log_no TEXT NOT NULL,
                    revision_id TEXT NOT NULL,
                    manifest_path TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT,
                    receipt_id TEXT,
                    created_at TEXT NOT NULL,
                    synced_at TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS ix_sync_queue_status ON sync_queue(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS ix_sync_queue_log_no ON sync_queue(log_no)")
            conn.commit()

    def enqueue_revision(self, log_no: str, revision_id: str, manifest_path: Path) -> str:
        """Добавляет ревизию в очередь на синхронизацию."""
        operation_id = f"op_{log_no}_{revision_id}_{uuid.uuid4().hex[:8]}"
        created_at = datetime.now(timezone.utc).isoformat()
        
        with self._get_connection() as conn:
            # Если такой манифест уже в очереди, возвращаем существующий ID
            row = conn.execute(
                "SELECT operation_id FROM sync_queue WHERE log_no = ? AND revision_id = ?",
                (log_no, revision_id)
            ).fetchone()
            if row:
                return row["operation_id"]

            conn.execute("""
                INSERT INTO sync_queue (
                    operation_id, log_no, revision_id, manifest_path, status, attempts, created_at
                ) VALUES (?, ?, ?, ?, 'pending', 0, ?)
            """, (operation_id, log_no, revision_id, str(manifest_path), created_at))
            conn.commit()

        return operation_id

    def get_pending_items(self) -> List[QueueItem]:
        """Возвращает список всех записей, ожидающих синхронизации (pending или failed)."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM sync_queue WHERE status IN ('pending', 'failed') ORDER BY id ASC"
            ).fetchall()
            return [self._row_to_item(r) for r in rows]

    def get_all_items(self) -> List[QueueItem]:
        """Возвращает все записи в очереди."""
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM sync_queue ORDER BY id DESC").fetchall()
            return [self._row_to_item(r) for r in rows]

    def update_status(
        self,
        operation_id: str,
        status: str,
        error: Optional[str] = None,
        receipt_id: Optional[str] = None
    ) -> None:
        """Обновляет статус операции в очереди."""
        synced_at = datetime.now(timezone.utc).isoformat() if status == "synced" else None
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE sync_queue
                SET status = ?,
                    attempts = attempts + 1,
                    last_error = ?,
                    receipt_id = COALESCE(?, receipt_id),
                    synced_at = COALESCE(?, synced_at)
                WHERE operation_id = ?
            """, (status, error, receipt_id, synced_at, operation_id))
            conn.commit()

    def get_summary(self) -> Dict[str, int]:
        """Возвращает сводную статистику очереди синхронизации."""
        with self._get_connection() as conn:
            rows = conn.execute("SELECT status, COUNT(*) as cnt FROM sync_queue GROUP BY status").fetchall()
            stats = {"pending": 0, "synced": 0, "failed": 0, "uploading": 0, "total": 0}
            for r in rows:
                stats[r["status"]] = r["cnt"]
                stats["total"] += r["cnt"]
            return stats

    @staticmethod
    def _row_to_item(r: sqlite3.Row) -> QueueItem:
        return QueueItem(
            id=r["id"],
            operation_id=r["operation_id"],
            log_no=r["log_no"],
            revision_id=r["revision_id"],
            manifest_path=r["manifest_path"],
            status=r["status"],
            attempts=r["attempts"],
            last_error=r["last_error"],
            receipt_id=r["receipt_id"],
            created_at=r["created_at"],
            synced_at=r["synced_at"]
        )


sync_queue = SyncQueue()
