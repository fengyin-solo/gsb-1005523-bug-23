"""运营概览汇总落库：SQLite 持久层。

汇总结果按 (统计日期, 片区) 唯一约束存最新一版：
- 当天重复提交/刷新只留最新一版（upsert）；
- 存量回填只补缺、不覆盖（insert_missing），已生成的历史概览保持原口径不动。
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from app.config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS overview_snapshot (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    summary_date TEXT NOT NULL,
    region TEXT NOT NULL,
    criteria_version INTEGER NOT NULL,
    pending INTEGER NOT NULL,
    abnormal INTEGER NOT NULL,
    created INTEGER NOT NULL,
    details TEXT NOT NULL DEFAULT '[]',
    generated_at TEXT NOT NULL,
    UNIQUE (summary_date, region)
);
"""

COLUMNS = ("summary_date", "region", "criteria_version", "pending", "abnormal", "created", "details", "generated_at")


def _resolve_path(db_path: str) -> Path:
    path = Path(db_path)
    if not path.is_absolute():
        path = Path(__file__).resolve().parent.parent / path
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


class SummaryStore:
    """汇总快照的读写都走这里，保证卡片、明细、模块统计读的是同一份落库数据。"""

    def __init__(self, db_path: str | None = None) -> None:
        self._db_path = _resolve_path(db_path or settings.summary_db_path)
        with self._connect() as conn:
            conn.execute(SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _decode(row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        item["details"] = json.loads(item.get("details") or "[]")
        return item

    def replace_day(self, summary_date: str, snapshots: list[dict[str, Any]]) -> None:
        """重算某一天的汇总：整天替换，同一片区一天只留最新一版，已消失的片区不留旧行。"""
        payload = []
        for snapshot in snapshots:
            row = dict(snapshot)
            row["details"] = json.dumps(snapshot.get("details") or [], ensure_ascii=False)
            payload.append(row)
        sql = """
        INSERT INTO overview_snapshot (summary_date, region, criteria_version, pending, abnormal, created, details, generated_at)
        VALUES (:summary_date, :region, :criteria_version, :pending, :abnormal, :created, :details, :generated_at)
        """
        with self._connect() as conn:
            conn.execute("DELETE FROM overview_snapshot WHERE summary_date = ?", (summary_date,))
            conn.executemany(sql, payload)

    def insert_missing(self, snapshot: dict[str, Any]) -> bool:
        """回填专用：已存在的 (日期, 片区) 不动，返回是否真正写入。"""
        sql = """
        INSERT OR IGNORE INTO overview_snapshot
            (summary_date, region, criteria_version, pending, abnormal, created, details, generated_at)
        VALUES (:summary_date, :region, :criteria_version, :pending, :abnormal, :created, :details, :generated_at)
        """
        payload = dict(snapshot)
        payload["details"] = json.dumps(snapshot.get("details") or [], ensure_ascii=False)
        with self._connect() as conn:
            cursor = conn.execute(sql, payload)
            return cursor.rowcount > 0

    def fetch(self, summary_date: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM overview_snapshot WHERE summary_date = ? ORDER BY region",
                (summary_date,),
            ).fetchall()
        return [self._decode(row) for row in rows]

    def fetch_one(self, summary_date: str, region: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM overview_snapshot WHERE summary_date = ? AND region = ?",
                (summary_date, region),
            ).fetchone()
        return self._decode(row) if row else None

    def list_snapshots(self, month: str | None = None) -> list[dict[str, Any]]:
        """列出已落库的汇总（可按月份过滤），不带回明细，供历史概览清单用。"""
        sql = "SELECT id, summary_date, region, criteria_version, pending, abnormal, created, generated_at FROM overview_snapshot"
        params: tuple[Any, ...] = ()
        if month:
            sql += " WHERE summary_date LIKE ?"
            params = (f"{month}-%",)
        sql += " ORDER BY summary_date, region"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]


summary_store = SummaryStore()
