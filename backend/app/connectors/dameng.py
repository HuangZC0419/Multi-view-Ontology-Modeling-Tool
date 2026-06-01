"""达梦数据库连接器 —— 真实连接 + SQLite 模拟双模式"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from app.connectors.base import DataSourceConnector
from app.models import TableInfo, ColumnInfo

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).resolve().parent.parent.parent


class SimDamengConnector(DataSourceConnector):
    """基于 SQLite 的达梦模拟连接器，用于开发测试。"""

    def __init__(self):
        self._conn = None
        self._db_path = BASE_DIR / "projects" / "sim_dameng.db"
        self._current_schema = "BENTI"

    async def connect(self, config: dict) -> bool:
        self._current_schema = config.get("schema", "BENTI")
        if not self._db_path.exists():
            raise FileNotFoundError(f"模拟数据库不存在: {self._db_path}")
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row
        return True

    async def disconnect(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    async def test_connection(self, config: dict) -> bool:
        db_path = config.get("db_path", str(self._db_path))
        path = Path(db_path)
        if not path.exists():
            path = self._db_path
        if not path.exists():
            return False
        try:
            conn = sqlite3.connect(str(path))
            conn.execute("SELECT 1 FROM all_tables LIMIT 1")
            conn.close()
            return True
        except Exception:
            return False

    async def get_tables(self) -> list[TableInfo]:
        if not self._conn:
            return []
        rows = self._conn.execute(
            "SELECT table_name, owner, comments, row_count FROM all_tables WHERE owner = ?",
            (self._current_schema,)
        ).fetchall()
        return [
            TableInfo(
                name=r["table_name"],
                table_schema=r["owner"] or "",
                comment=r["comments"] or "",
                row_count=r["row_count"] or 0
            )
            for r in rows
        ]

    async def get_columns(self, table: str, schema: str = "") -> list[ColumnInfo]:
        if not self._conn:
            return []
        schema = schema or self._current_schema
        rows = self._conn.execute(
            """SELECT column_name, data_type, nullable, is_pk, comments
               FROM all_tab_columns WHERE owner = ? AND table_name = ?""",
            (schema, table)
        ).fetchall()
        return [
            ColumnInfo(
                name=r["column_name"],
                data_type=r["data_type"],
                nullable=bool(r["nullable"]),
                is_pk=bool(r["is_pk"]),
                comment=r["comments"] or ""
            )
            for r in rows
        ]

    async def preview_data(self, table: str, schema: str = "", limit: int = 10) -> list[dict]:
        if not self._conn:
            return []
        schema = schema or self._current_schema
        columns = await self.get_columns(table, schema)
        if not columns:
            return []
        col_names = [c.name for c in columns]
        try:
            rows = self._conn.execute(
                f'SELECT {", ".join(col_names)} FROM {table} LIMIT ?', (limit,)
            ).fetchall()
            return [dict(r) for r in rows]
        except sqlite3.OperationalError:
            return []


class DamengConnector(DataSourceConnector):
    """达梦 DM8 数据库连接器，使用 dmPython 驱动。"""

    def __init__(self):
        self._conn = None
        self._current_schema = ""

    async def connect(self, config: dict) -> bool:
        try:
            import dmPython
        except ImportError:
            raise ImportError("dmPython 未安装，请在 conda benti-py38 中执行: pip install dmPython")
        self._current_schema = config.get("schema", "")
        self._conn = dmPython.connect(
            host=config["host"],
            port=config.get("port", 5236),
            user=config["user"],
            password=config["password"],
            schema=self._current_schema
        )
        return True

    async def disconnect(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    async def test_connection(self, config: dict) -> bool:
        try:
            import dmPython
            conn = dmPython.connect(
                host=config["host"],
                port=config.get("port", 5236),
                user=config["user"],
                password=config["password"],
                schema=config.get("schema", "")
            )
            conn.close()
            return True
        except Exception:
            return False

    async def get_tables(self) -> list[TableInfo]:
        if not self._conn:
            return []
        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT table_name, owner, comments, num_rows FROM all_tables WHERE owner = :owner ORDER BY table_name",
            {"owner": self._current_schema}
        )
        rows = cursor.fetchall()
        cursor.close()
        return [
            TableInfo(name=r[0], table_schema=r[1] or "", comment=r[2] or "", row_count=r[3] or 0)
            for r in rows
        ]

    async def get_columns(self, table: str, schema: str = "") -> list[ColumnInfo]:
        if not self._conn:
            return []
        schema = schema or self._current_schema
        cursor = self._conn.cursor()
        cursor.execute(
            """SELECT c.column_name, c.data_type,
                      CASE WHEN c.nullable = 'Y' THEN 1 ELSE 0 END AS nullable,
                      CASE WHEN pk.column_name IS NOT NULL THEN 1 ELSE 0 END AS is_pk,
                      com.comments
               FROM all_tab_columns c
               LEFT JOIN (
                   SELECT cc.owner, cc.table_name, cc.column_name
                   FROM all_cons_columns cc
                   JOIN all_constraints con ON cc.constraint_name = con.constraint_name
                   WHERE con.constraint_type = 'P' AND cc.owner = :owner
               ) pk ON c.owner = pk.owner AND c.table_name = pk.table_name AND c.column_name = pk.column_name
               LEFT JOIN all_col_comments com ON c.owner = com.owner AND c.table_name = com.table_name AND c.column_name = com.column_name
               WHERE c.owner = :owner AND c.table_name = :table_name
               ORDER BY c.column_id""",
            {"owner": schema, "table_name": table}
        )
        rows = cursor.fetchall()
        cursor.close()
        return [
            ColumnInfo(name=r[0], data_type=r[1], nullable=bool(r[2]),
                      is_pk=bool(r[3]), comment=r[4] or "")
            for r in rows
        ]

    async def preview_data(self, table: str, schema: str = "", limit: int = 10) -> list[dict]:
        if not self._conn:
            return []
        schema = schema or self._current_schema
        cursor = self._conn.cursor()
        try:
            cursor.execute(f'SELECT * FROM "{schema}"."{table}" WHERE ROWNUM <= {limit}')
            col_descs = cursor.description
            rows = cursor.fetchall()
            cursor.close()
            return [
                {col_descs[i][0]: row[i] for i in range(len(col_descs))}
                for row in rows
            ]
        except Exception:
            cursor.close()
            return []
