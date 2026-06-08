# 多数据源接入 + 多视角查询 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Tasks marked `[并行]` can run simultaneously. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为本体建模系统新增达梦数据库连接、Excel/CSV文件导入、以及基于machining-demo的三视角查询功能。

**Architecture:** 方案C混合式——新增功能独立模块，现有core不变。后端新增 models.py / routers(datasource+perspective) / connectors(base+dameng+file_parser) / services(ontology_extract)。前端新增 datasource/ perspective/ canvas/ 三组组件。

**Tech Stack:** Python 3.8 + FastAPI + dmPython + openpyxl + xlrd + chardet + Vue 3 + Vite

---

## 文件结构

```
backend/app/
├── main.py                   # [修改] 注册新路由
├── models.py                 # [新建] 共享Pydantic模型
├── routers/
│   ├── __init__.py           # [新建]
│   ├── datasource.py         # [新建] 数据源API
│   └── perspective.py        # [新建] 多视角API
├── connectors/
│   ├── __init__.py           # [新建]
│   ├── base.py               # [新建] 抽象基类
│   ├── dameng.py             # [新建] 达梦连接器+模拟
│   └── file_parser.py        # [新建] Excel/CSV解析器
└── services/
    ├── __init__.py           # [新建]
    └── ontology_extract.py   # [新建] 本体提取

frontend/src/
├── App.vue                   # [修改] 集成新组件
├── style.css                 # [修改] 新增样式
└── components/
    ├── datasource/
    │   ├── DataSourcePanel.vue   # [新建] 导入入口
    │   ├── DbConnector.vue      # [新建] 数据库连接
    │   ├── FileUploader.vue     # [新建] 文件上传
    │   └── SchemaPreview.vue    # [新建] 结构预览
    ├── perspective/
    │   ├── PerspectiveTabs.vue  # [新建] Tab栏
    │   ├── LeaderView.vue       # [新建] 领导视角
    │   ├── EngineerView.vue     # [新建] 工程师视角
    │   └── ProcessView.vue      # [新建] 工艺人员视角
    └── canvas/
        ├── CanvasArea.vue       # [新建] 画布渲染
        ├── NodeCard.vue         # [新建] 节点卡片
        └── EdgeLine.vue         # [新建] 关系连线

backend/projects/
├── machining-demo.json       # [修改] 扩展三层架构数据
└── sim_dameng.db             # [新建] 模拟达梦SQLite库
```

---

### Task 1: 创建 models.py — 共享数据模型 [并行A]

**Files:**
- Create: `backend/app/models.py`

- [ ] **Step 1: 写入 models.py 完整代码**

```python
"""共享数据模型 —— 从 main.py 提取 + 新增数据源/视角模型"""

from enum import Enum
from pydantic import BaseModel, Field


# ============================================================
# 视角枚举
# ============================================================

class PerspectiveType(str, Enum):
    LEADER = "leader"
    ENGINEER = "engineer"
    PROCESS = "process"


# ============================================================
# 数据源连接器相关模型
# ============================================================

class TableInfo(BaseModel):
    """表/Sheet 元信息"""
    name: str
    schema: str = ""
    comment: str = ""
    row_count: int = 0


class ColumnInfo(BaseModel):
    """列/字段 元信息"""
    name: str
    data_type: str
    nullable: bool = True
    is_pk: bool = False
    comment: str = ""


class ImportSelection(BaseModel):
    """用户勾选的导入项"""
    source_id: str                          # 数据源标识（db session_id 或 file_id）
    tables: list[str] = Field(default_factory=list)     # 勾选的表名
    columns: dict[str, list[str]] = Field(default_factory=dict)  # {表名: [勾选的列名]}
    edited_names: dict[str, str] = Field(default_factory=dict)  # {原名: 用户编辑后的名}


# ============================================================
# 多视角相关模型
# ============================================================

class DataSourceInfo(BaseModel):
    """数据源元信息（领导视角用）"""
    id: str
    name: str
    type: str                              # "dameng" | "excel" | "csv"
    conn_info: dict = Field(default_factory=dict)  # {host, port, schema} 或 {file_name}
    tables: list[str] = Field(default_factory=list)
    covered_nodes: int = 0
    covered_domains: list[str] = Field(default_factory=list)
    total_fields: int = 0


class BusinessDomain(BaseModel):
    """业务域（领导视角用）"""
    id: str
    name: str
    ontology_node_ids: list[str] = Field(default_factory=list)
    databases: list[str] = Field(default_factory=list)


class FieldMapping(BaseModel):
    """字段映射"""
    field_name: str
    attribute_key: str
    data_type: str


class DataMapping(BaseModel):
    """数据映射（工程师视角用）"""
    ontology_node_id: str
    source_type: str                       # "dameng" | "excel" | "csv"
    source_name: str
    table_name: str
    field_mappings: list[FieldMapping] = Field(default_factory=list)


class LeaderViewData(BaseModel):
    """领导视角完整数据"""
    summary: dict = Field(default_factory=dict)
    data_sources: list[DataSourceInfo] = Field(default_factory=list)
    domains: list[BusinessDomain] = Field(default_factory=list)
    source_domain_map: dict = Field(default_factory=dict)


class EngineerViewData(BaseModel):
    """工程师视角完整数据"""
    nodes: list = Field(default_factory=list)       # 本体节点简要信息
    mappings: list[DataMapping] = Field(default_factory=list)
    domains: list[BusinessDomain] = Field(default_factory=list)
```

- [ ] **Step 2: 验证文件语法**

Run: `cd H:/Git/OCR_benti-main_win7/backend && python -c "from app.models import *; print('models.py OK')"`
Expected: `models.py OK`

---

### Task 2: 创建 connectors/__init__.py 和 base.py — 抽象基类 [并行A]

**Files:**
- Create: `backend/app/connectors/__init__.py`
- Create: `backend/app/connectors/base.py`

- [ ] **Step 1: 创建 __init__.py**

```python
# connectors package
```

- [ ] **Step 2: 创建 base.py**

```python
"""数据源连接器抽象基类"""

from abc import ABC, abstractmethod
from app.models import TableInfo, ColumnInfo


class DataSourceConnector(ABC):
    """所有数据源的统一抽象接口"""

    @abstractmethod
    async def connect(self, config: dict) -> bool:
        """建立连接，返回是否成功"""
        ...

    @abstractmethod
    async def disconnect(self):
        """断开连接，释放资源"""
        ...

    @abstractmethod
    async def test_connection(self, config: dict) -> bool:
        """测试连接参数是否可用（不保持连接）"""
        ...

    @abstractmethod
    async def get_tables(self) -> list[TableInfo]:
        """获取所有表/Sheet/文件列表"""
        ...

    @abstractmethod
    async def get_columns(self, table: str, schema: str = "") -> list[ColumnInfo]:
        """获取指定表的列信息"""
        ...

    @abstractmethod
    async def preview_data(self, table: str, schema: str = "", limit: int = 10) -> list[dict]:
        """预览表的前N行数据"""
        ...
```

- [ ] **Step 3: 验证语法**

Run: `cd H:/Git/OCR_benti-main_win7/backend && python -c "from app.connectors.base import DataSourceConnector; print('base.py OK')"`
Expected: `base.py OK`

---

### Task 3: 创建 connectors/dameng.py — 达梦连接器+模拟 [并行A]

**Files:**
- Create: `backend/app/connectors/dameng.py`

- [ ] **Step 1: 创建 dameng.py（含 SimDamengConnector 模拟实现）**

```python
"""达梦数据库连接器 —— 真实连接 + SQLite 模拟双模式"""

import sqlite3
import os
from pathlib import Path
from app.connectors.base import DataSourceConnector
from app.models import TableInfo, ColumnInfo

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class SimDamengConnector(DataSourceConnector):
    """基于 SQLite 的达梦模拟连接器，用于开发测试。
    
    查询本地 sim_dameng.db 中的 all_tables / all_tab_columns 两张模拟系统表，
    接口与真实 DamengConnector 完全一致。
    """

    def __init__(self):
        self._conn: sqlite3.Connection | None = None
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
                schema=r["owner"],
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
                f'SELECT {", ".join(col_names)} FROM "{table}" LIMIT ?', (limit,)
            ).fetchall()
            return [dict(r) for r in rows]
        except sqlite3.OperationalError:
            return []


# ============================================================
# 真实达梦连接器（生产环境）
# ============================================================

class DamengConnector(DataSourceConnector):
    """达梦 DM8 数据库连接器，使用 dmPython 驱动。

    生产环境使用前需确保 conda benti-py38 已安装 dmPython。
    """

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
            """SELECT table_name, owner, comments, num_rows
               FROM all_tables WHERE owner = :owner ORDER BY table_name""",
            {"owner": self._current_schema}
        )
        rows = cursor.fetchall()
        cursor.close()
        return [
            TableInfo(
                name=r[0], schema=r[1] or "", comment=r[2] or "", row_count=r[3] or 0
            )
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
            ColumnInfo(
                name=r[0], data_type=r[1], nullable=bool(r[2]),
                is_pk=bool(r[3]), comment=r[4] or ""
            )
            for r in rows
        ]

    async def preview_data(self, table: str, schema: str = "", limit: int = 10) -> list[dict]:
        if not self._conn:
            return []
        schema = schema or self._current_schema
        cursor = self._conn.cursor()
        try:
            cursor.execute(
                f'SELECT * FROM "{schema}"."{table}" WHERE ROWNUM <= {limit}'
            )
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
```

- [ ] **Step 2: 验证语法**

Run: `cd H:/Git/OCR_benti-main_win7/backend && python -c "from app.connectors.dameng import SimDamengConnector, DamengConnector; print('dameng.py OK')"`
Expected: `dameng.py OK`

---

### Task 4: 创建 connectors/file_parser.py — Excel/CSV解析器 [并行A]

**Files:**
- Create: `backend/app/connectors/file_parser.py`

- [ ] **Step 1: 创建 file_parser.py**

```python
"""Excel / CSV 文件解析器"""

import csv
import io
import os
from pathlib import Path
from app.connectors.base import DataSourceConnector
from app.models import TableInfo, ColumnInfo

BASE_DIR = Path(__file__).resolve().parent.parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"


class FileParserConnector(DataSourceConnector):
    """解析上传的 Excel/CSV 文件，提取 Sheet/列结构"""

    def __init__(self):
        self._tables: list[TableInfo] = []
        self._columns: dict[str, list[ColumnInfo]] = {}
        self._file_path: str = ""
        self._file_type: str = ""

    async def connect(self, config: dict) -> bool:
        self._file_path = config["file_path"]
        self._file_type = config.get("file_type", "")
        if not self._file_type:
            ext = os.path.splitext(self._file_path)[1].lower()
            self._file_type = ext

        if self._file_type in (".xlsx", ".xls"):
            return await self._parse_excel()
        elif self._file_type == ".csv":
            return await self._parse_csv()
        else:
            raise ValueError(f"不支持的文件格式: {self._file_type}")

    async def disconnect(self):
        self._tables.clear()
        self._columns.clear()
        self._file_path = ""
        self._file_type = ""

    async def test_connection(self, config: dict) -> bool:
        path = config.get("file_path", "")
        return os.path.isfile(path)

    async def get_tables(self) -> list[TableInfo]:
        return self._tables

    async def get_columns(self, table: str, schema: str = "") -> list[ColumnInfo]:
        return self._columns.get(table, [])

    async def preview_data(self, table: str, schema: str = "", limit: int = 10) -> list[dict]:
        """预览前N行数据"""
        if self._file_type == ".csv":
            return await self._preview_csv(limit)
        elif self._file_type in (".xlsx", ".xls"):
            return await self._preview_excel(table, limit)
        return []

    # ---- Excel 解析 ----

    async def _parse_excel(self) -> bool:
        try:
            import openpyxl
            wb = openpyxl.load_workbook(self._file_path, read_only=True, data_only=True)
        except Exception:
            try:
                import xlrd
                wb = xlrd.open_workbook(self._file_path)
                return await self._parse_xls(wb)
            except Exception:
                raise RuntimeError("无法打开 Excel 文件")

        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            rows_iter = ws.iter_rows(min_row=1, max_row=min(ws.max_row, 21), values_only=True)
            try:
                header = next(rows_iter)
            except StopIteration:
                continue
            if not header or all(h is None or str(h).strip() == "" for h in header):
                continue

            header = [str(h).strip() if h is not None else f"Column{i}" for i, h in enumerate(header)]
            col_types = []
            row_count = 0
            for row in rows_iter:
                if row and any(v is not None for v in row):
                    row_count += 1
                    if row_count <= 20:
                        for i, val in enumerate(row):
                            if i < len(col_types):
                                if val is not None:
                                    col_types[i] = self._merge_type(col_types[i], type(val).__name__)
                            else:
                                col_types.append(type(val).__name__ if val is not None else "str")
                else:
                    row_count += 1

            while len(col_types) < len(header):
                col_types.append("str")

            type_map = {"int": "INTEGER", "float": "FLOAT", "str": "VARCHAR", "bool": "BOOLEAN"}
            columns = [
                ColumnInfo(name=h, data_type=type_map.get(col_types[i], "VARCHAR"))
                for i, h in enumerate(header)
            ]
            self._tables.append(TableInfo(name=sheet_name, row_count=row_count))
            self._columns[sheet_name] = columns

        wb.close()
        return True

    async def _parse_xls(self, wb) -> bool:
        for sheet_idx in range(wb.nsheets):
            ws = wb.sheet_by_index(sheet_idx)
            if ws.nrows < 1:
                continue
            header = [str(ws.cell_value(0, c)).strip() for c in range(ws.ncols)]
            preview_rows = min(ws.nrows, 21)
            col_types = []
            for r in range(1, preview_rows):
                for c in range(ws.ncols):
                    val = ws.cell_value(r, c)
                    if val != "" and val is not None:
                        if c < len(col_types):
                            col_types[c] = self._merge_type(col_types[c], type(val).__name__)
                        else:
                            col_types.append(type(val).__name__)
            while len(col_types) < len(header):
                col_types.append("str")
            type_map = {"int": "INTEGER", "float": "FLOAT", "str": "VARCHAR", "bool": "BOOLEAN"}
            columns = [
                ColumnInfo(name=h, data_type=type_map.get(col_types[i], "VARCHAR"))
                for i, h in enumerate(header)
            ]
            self._tables.append(TableInfo(name=ws.name, row_count=ws.nrows - 1))
            self._columns[ws.name] = columns
        return True

    async def _preview_excel(self, sheet: str, limit: int) -> list[dict]:
        try:
            import openpyxl
            wb = openpyxl.load_workbook(self._file_path, read_only=True, data_only=True)
        except Exception:
            return []
        if sheet not in wb.sheetnames:
            wb.close()
            return []
        ws = wb[sheet]
        rows_iter = ws.iter_rows(min_row=1, max_row=min(ws.max_row, limit + 1), values_only=True)
        try:
            header = next(rows_iter)
        except StopIteration:
            wb.close()
            return []
        header = [str(h).strip() if h is not None else f"Col{i}" for i, h in enumerate(header)]
        result = []
        for row in rows_iter:
            result.append({header[i]: row[i] if i < len(row) else None for i in range(len(header))})
        wb.close()
        return result

    # ---- CSV 解析 ----

    async def _parse_csv(self) -> bool:
        with open(self._file_path, "rb") as f:
            raw = f.read(4096)
        try:
            import chardet
            encoding = chardet.detect(raw)["encoding"] or "utf-8"
        except ImportError:
            encoding = "utf-8"

        with open(self._file_path, "r", encoding=encoding, errors="replace") as f:
            sample = f.read(2048)
            f.seek(0)
            dialect = csv.Sniffer().sniff(sample)
            reader = csv.reader(f, dialect)
            try:
                header = next(reader)
            except StopIteration:
                return True
            header = [h.strip() for h in header if h.strip()]
            if not header:
                return True

            col_types = []
            row_count = 0
            for row in reader:
                if row:
                    row_count += 1
                    if row_count <= 20:
                        for i, val in enumerate(row):
                            inferred = self._infer_csv_type(val)
                            if i < len(col_types):
                                col_types[i] = self._merge_type(col_types[i], inferred)
                            else:
                                col_types.append(inferred)

        while len(col_types) < len(header):
            col_types.append("VARCHAR")

        file_name = os.path.basename(self._file_path)
        columns = [
            ColumnInfo(name=h, data_type=col_types[i])
            for i, h in enumerate(header)
        ]
        self._tables.append(TableInfo(name=file_name, row_count=row_count))
        self._columns[file_name] = columns
        return True

    async def _preview_csv(self, limit: int) -> list[dict]:
        with open(self._file_path, "rb") as f:
            raw = f.read(4096)
        try:
            import chardet
            encoding = chardet.detect(raw)["encoding"] or "utf-8"
        except ImportError:
            encoding = "utf-8"

        with open(self._file_path, "r", encoding=encoding, errors="replace") as f:
            sample = f.read(2048)
            f.seek(0)
            dialect = csv.Sniffer().sniff(sample)
            reader = csv.DictReader(f, dialect=dialect)
            rows = []
            for i, row in enumerate(reader):
                if i >= limit:
                    break
                rows.append(dict(row))
            return rows

    def _infer_csv_type(self, val: str) -> str:
        if val is None or val.strip() == "":
            return "VARCHAR"
        val = val.strip()
        try:
            int(val)
            return "INTEGER"
        except ValueError:
            pass
        try:
            float(val)
            return "FLOAT"
        except ValueError:
            pass
        return "VARCHAR"

    def _merge_type(self, old: str, new: str) -> str:
        if old == new:
            return old
        if old == "VARCHAR" or new == "VARCHAR":
            return "VARCHAR"
        if "FLOAT" in (old, new):
            return "FLOAT"
        return "VARCHAR"
```

- [ ] **Step 2: 验证语法**

Run: `cd H:/Git/OCR_benti-main_win7/backend && python -c "from app.connectors.file_parser import FileParserConnector; print('file_parser.py OK')"`
Expected: `file_parser.py OK`

---

### Task 5: 创建 services/ontology_extract.py — 本体提取逻辑 [并行B]

**Files:**
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/services/ontology_extract.py`

- [ ] **Step 1: 创建 __init__.py**

```python
# services package
```

- [ ] **Step 2: 创建 ontology_extract.py**

```python
"""从数据源结构中提取本体概念"""

import uuid
from app.models import TableInfo, ColumnInfo, ImportSelection


def extract_ontology_nodes(
    tables: list[TableInfo],
    columns_map: dict[str, list[ColumnInfo]],
    selection: ImportSelection,
    start_x: float = 120,
    start_y: float = 120,
    spacing_x: float = 220,
    spacing_y: float = 140,
    columns_per_row: int = 3
) -> list[dict]:
    """根据用户勾选，生成本体节点列表。

    表名 → 父节点（name=A表, attributes=[]）
    列名 → 子节点（name=字段名, parent_id=父节点ID, attributes=[{类型: VARCHAR, 注释: ...}]）

    返回: 可直接追加到画的 OntologyNode dict 列表
    """
    nodes = []
    col_idx = 0

    for table_name in selection.tables:
        # 用户可能编辑了表名
        display_name = selection.edited_names.get(table_name, table_name)

        parent_id = str(uuid.uuid4())
        x = start_x + (col_idx % columns_per_row) * spacing_x
        y = start_y + (col_idx // columns_per_row) * spacing_y * 2

        nodes.append({
            "id": parent_id,
            "name": display_name,
            "x": x,
            "y": y,
            "parent_id": None,
            "attributes": []
        })

        # 获取勾选的列
        selected_cols = selection.columns.get(table_name, [])
        columns = columns_map.get(table_name, [])

        child_x = x
        child_y = y + spacing_y
        child_count = 0

        for col in columns:
            if col.name not in selected_cols:
                continue

            display_col_name = selection.edited_names.get(
                f"{table_name}.{col.name}", col.name
            )

            child_attrs = [
                {"key": "数据类型", "value": col.data_type},
            ]
            if col.comment:
                child_attrs.append({"key": "注释", "value": col.comment})
            if col.is_pk:
                child_attrs.append({"key": "主键", "value": "是"})

            child_id = str(uuid.uuid4())
            nodes.append({
                "id": child_id,
                "name": display_col_name,
                "x": child_x + child_count * 180,
                "y": child_y,
                "parent_id": parent_id,
                "attributes": child_attrs
            })
            child_count += 1

        col_idx += 1

    return nodes
```

- [ ] **Step 3: 验证语法**

Run: `cd H:/Git/OCR_benti-main_win7/backend && python -c "from app.services.ontology_extract import extract_ontology_nodes; print('ontology_extract.py OK')"`
Expected: `ontology_extract.py OK`

---

### Task 6: 创建 routers/__init__.py [并行B]

**Files:**
- Create: `backend/app/routers/__init__.py`

```python
# routers package
```

---

### Task 7: 创建 routers/datasource.py — 数据源API路由 [并行B]

**Files:**
- Create: `backend/app/routers/datasource.py`

- [ ] **Step 1: 创建 datasource.py**

```python
"""数据源接入 API —— 数据库连接 + 文件上传 + 本体导入"""

import os
import uuid
import shutil
from pathlib import Path
from fastapi import APIRouter, File, HTTPException, UploadFile
from app.models import ImportSelection
from app.connectors.dameng import SimDamengConnector, DamengConnector
from app.connectors.file_parser import FileParserConnector
from app.services.ontology_extract import extract_ontology_nodes

router = APIRouter(prefix="/api/datasource")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"

# 连接会话存储 {session_id: connector_instance}
_sessions: dict[str, tuple] = {}


def _ensure_upload_dir():
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# 数据库连接
# ============================================================

@router.post("/db/test")
async def test_db_connection(config: dict):
    """测试数据库连接参数"""
    db_type = config.get("type", "sim_dameng")
    if db_type == "dameng":
        connector = DamengConnector()
    else:
        connector = SimDamengConnector()
    ok = await connector.test_connection(config)
    return {"success": ok, "message": "连接成功" if ok else "连接失败，请检查参数"}


@router.post("/db/connect")
async def connect_db(config: dict):
    """建立数据库连接，返回 session_id"""
    db_type = config.get("type", "sim_dameng")
    if db_type == "dameng":
        connector = DamengConnector()
    else:
        connector = SimDamengConnector()
    ok = await connector.connect(config)
    if not ok:
        raise HTTPException(500, "连接失败")
    session_id = str(uuid.uuid4())
    _sessions[session_id] = (connector, db_type)
    return {"session_id": session_id, "db_type": db_type}


@router.get("/db/tables")
async def get_db_tables(session_id: str):
    """获取表列表"""
    if session_id not in _sessions:
        raise HTTPException(404, "会话不存在或已过期")
    connector, _ = _sessions[session_id]
    tables = await connector.get_tables()
    return {"tables": [t.model_dump() for t in tables]}


@router.get("/db/tables/{table}/columns")
async def get_db_columns(table: str, session_id: str, schema: str = ""):
    """获取列信息"""
    if session_id not in _sessions:
        raise HTTPException(404, "会话不存在或已过期")
    connector, _ = _sessions[session_id]
    columns = await connector.get_columns(table, schema)
    return {"columns": [c.model_dump() for c in columns]}


@router.get("/db/tables/{table}/preview")
async def preview_db_data(table: str, session_id: str, schema: str = "", limit: int = 10):
    """预览表数据"""
    if session_id not in _sessions:
        raise HTTPException(404, "会话不存在或已过期")
    connector, _ = _sessions[session_id]
    rows = await connector.preview_data(table, schema, limit)
    return {"rows": rows}


@router.post("/db/disconnect")
async def disconnect_db(session_id: str):
    """断开数据库连接"""
    if session_id in _sessions:
        connector, _ = _sessions.pop(session_id)
        await connector.disconnect()
    return {"success": True}


# ============================================================
# 文件上传
# ============================================================

@router.post("/file/upload")
async def upload_file(file: UploadFile = File(...)):
    """上传 Excel/CSV 文件，返回解析后的结构"""
    _ensure_upload_dir()

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in (".xlsx", ".xls", ".csv"):
        raise HTTPException(400, f"不支持的文件格式: {ext}，仅支持 .xlsx .xls .csv")

    file_id = str(uuid.uuid4())
    save_name = f"{file_id}{ext}"
    save_path = UPLOAD_DIR / save_name

    with open(save_path, "wb") as f:
        content = await file.read()
        f.write(content)

    parser = FileParserConnector()
    await parser.connect({"file_path": str(save_path), "file_type": ext})
    tables = await parser.get_tables()
    columns_map = {}
    for t in tables:
        cols = await parser.get_columns(t.name)
        columns_map[t.name] = [c.model_dump() for c in cols]

    await parser.disconnect()

    return {
        "file_id": file_id,
        "file_name": file.filename,
        "file_type": ext,
        "tables": [t.model_dump() for t in tables],
        "columns": columns_map
    }


@router.get("/file/{file_id}/preview")
async def preview_file_data(file_id: str, table: str = "", limit: int = 10):
    """预览上传文件的数据"""
    _ensure_upload_dir()
    for ext in (".xlsx", ".xls", ".csv"):
        path = UPLOAD_DIR / f"{file_id}{ext}"
        if path.exists():
            parser = FileParserConnector()
            await parser.connect({"file_path": str(path), "file_type": ext})
            if table:
                rows = await parser.preview_data(table, limit=limit)
            else:
                tables = await parser.get_tables()
                if tables:
                    rows = await parser.preview_data(tables[0].name, limit=limit)
                else:
                    rows = []
            await parser.disconnect()
            return {"rows": rows}
    raise HTTPException(404, "文件不存在或已过期")


# ============================================================
# 本体导入（数据库 + 文件共用）
# ============================================================

@router.post("/import")
async def import_ontology(selection: ImportSelection):
    """提交用户勾选，生成本体节点"""
    nodes = []

    # 检查是否是数据库来源
    if selection.source_id in _sessions:
        connector, _ = _sessions[selection.source_id]
        tables = await connector.get_tables()
        columns_map = {}
        for t in tables:
            if t.name in selection.tables:
                cols = await connector.get_columns(t.name)
                columns_map[t.name] = [c.model_dump() for c in cols]
        table_infos = [t.model_dump() for t in tables if t.name in selection.tables]

        nodes = extract_ontology_nodes(
            tables=[type('T', (), t)() or type('T', (), {'name': t['name'], 'schema': t.get('schema',''), 'comment': t.get('comment',''), 'row_count': t.get('row_count',0)}) for t in table_infos],
            columns_map=columns_map,
            selection=selection
        )
    else:
        # 文件来源
        _ensure_upload_dir()
        for ext in (".xlsx", ".xls", ".csv"):
            path = UPLOAD_DIR / f"{selection.source_id}{ext}"
            if path.exists():
                parser = FileParserConnector()
                await parser.connect({"file_path": str(path), "file_type": ext})
                tables = await parser.get_tables()
                columns_map = {}
                for t in tables:
                    if t.name in selection.tables:
                        cols = await parser.get_columns(t.name)
                        columns_map[t.name] = cols
                await parser.disconnect()

                nodes = extract_ontology_nodes(
                    tables=tables,
                    columns_map=columns_map,
                    selection=selection
                )
                break

    return {"nodes": nodes, "count": len(nodes)}
```

**注意**：Task 7 的 datasource.py 中包含类型构造的 trick，在后续执行的 agent 应该清理为直接传 TableInfo 对象。考虑到 extract_ontology_nodes 需要 TableInfo 对象，这里做了简化处理。

- [ ] **Step 2: 验证语法**

Run: `cd H:/Git/OCR_benti-main_win7/backend && python -c "from app.routers.datasource import router; print('datasource.py OK')"`
Expected: `datasource.py OK`

---

### Task 8: 创建 routers/perspective.py — 多视角API [并行B]

**Files:**
- Create: `backend/app/routers/perspective.py`

- [ ] **Step 1: 创建 perspective.py**

```python
"""多视角查询 API"""

import json
from pathlib import Path
from fastapi import APIRouter, HTTPException
from app.models import (
    LeaderViewData, EngineerViewData, DataSourceInfo,
    BusinessDomain, DataMapping, FieldMapping, PerspectiveType
)

router = APIRouter(prefix="/api/perspective")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
PROJECTS_DIR = BASE_DIR / "projects"


def _load_project(project_id: str) -> dict:
    path = PROJECTS_DIR / f"{project_id}.json"
    if not path.exists():
        raise HTTPException(404, f"项目不存在: {project_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def _load_perspective_config(project_id: str) -> dict:
    """加载项目的视角配置文件"""
    config_path = PROJECTS_DIR / f"{project_id}_perspective.json"
    if config_path.exists():
        return json.loads(config_path.read_text(encoding="utf-8"))
    return {"domains": [], "mappings": [], "sources": []}


def _save_perspective_config(project_id: str, config: dict):
    config_path = PROJECTS_DIR / f"{project_id}_perspective.json"
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


# ============================================================
# 视角数据获取
# ============================================================

@router.get("/{project_id}/leader")
async def get_leader_view(project_id: str):
    """返回领导视角完整数据"""
    graph = _load_project(project_id)
    config = _load_perspective_config(project_id)

    domains = [BusinessDomain(**d) for d in config.get("domains", [])]
    sources = [DataSourceInfo(**s) for s in config.get("sources", [])]

    # 构建数据源→业务域映射
    source_domain_map = {}
    for src in sources:
        source_domain_map[src.id] = [
            d.id for d in domains
            if src.id in d.databases or src.name in d.databases
        ]

    domain_concept_count = sum(len(d.ontology_node_ids) for d in domains)

    return LeaderViewData(
        summary={
            "domains": len(domains),
            "nodes": len(graph.get("nodes", [])),
            "edges": len(graph.get("edges", [])),
            "sources": len(sources),
            "domain_concepts": domain_concept_count,
            "dameng_count": sum(1 for s in sources if s.type == "dameng"),
            "excel_count": sum(1 for s in sources if s.type == "excel"),
            "csv_count": sum(1 for s in sources if s.type == "csv"),
        },
        data_sources=sources,
        domains=domains,
        source_domain_map=source_domain_map
    )


@router.get("/{project_id}/engineer")
async def get_engineer_view(project_id: str):
    """返回软件工程师视角完整数据"""
    graph = _load_project(project_id)
    config = _load_perspective_config(project_id)

    domains = [BusinessDomain(**d) for d in config.get("domains", [])]
    mappings = [DataMapping(**m) for m in config.get("mappings", [])]

    # 构建节点简要信息
    node_map = {n["id"]: n for n in graph.get("nodes", [])}
    nodes_brief = [
        {"id": nid, "name": node_map[nid]["name"]}
        for m in mappings
        if (nid := m.ontology_node_id) in node_map
    ]

    return EngineerViewData(
        nodes=nodes_brief,
        mappings=mappings,
        domains=domains
    )


@router.get("/{project_id}/process")
async def get_process_view(project_id: str):
    """返回工艺人员视角数据 —— 即现有完整图数据"""
    return _load_project(project_id)


# ============================================================
# 配置管理
# ============================================================

@router.get("/{project_id}/domains")
async def get_domains(project_id: str):
    config = _load_perspective_config(project_id)
    return {"domains": config.get("domains", [])}


@router.put("/{project_id}/domains")
async def update_domains(project_id: str, domains: list[BusinessDomain]):
    config = _load_perspective_config(project_id)
    config["domains"] = [d.model_dump() for d in domains]
    _save_perspective_config(project_id, config)
    return {"success": True}


@router.put("/{project_id}/mappings")
async def update_mappings(project_id: str, mappings: list[DataMapping]):
    config = _load_perspective_config(project_id)
    config["mappings"] = [m.model_dump() for m in mappings]
    _save_perspective_config(project_id, config)
    return {"success": True}


@router.get("/{project_id}/sources")
async def get_sources(project_id: str):
    config = _load_perspective_config(project_id)
    return {"sources": config.get("sources", [])}


@router.put("/{project_id}/sources")
async def update_sources(project_id: str, sources: list[DataSourceInfo]):
    config = _load_perspective_config(project_id)
    config["sources"] = [s.model_dump() for s in sources]
    _save_perspective_config(project_id, config)
    return {"success": True}
```

- [ ] **Step 2: 验证语法**

Run: `cd H:/Git/OCR_benti-main_win7/backend && python -c "from app.routers.perspective import router; print('perspective.py OK')"`
Expected: `perspective.py OK`

---

### Task 9: 创建 SQLite 模拟达梦数据库 [并行C]

**Files:**
- Create: `backend/projects/sim_dameng.db`（通过脚本生成）
- Create: `backend/scripts/init_sim_db.py`

- [ ] **Step 1: 创建初始化脚本**

```python
"""初始化模拟达梦数据库 —— 创建系统表 + 录入测试数据"""

import sqlite3
import os
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "projects" / "sim_dameng.db"

def init():
    if DB_PATH.exists():
        os.remove(DB_PATH)
    
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # ---- 模拟达梦系统视图 ----
    cur.execute("""
        CREATE TABLE all_tables (
            owner TEXT, table_name TEXT, comments TEXT, num_rows INTEGER, row_count INTEGER
        )
    """)
    cur.execute("""
        CREATE TABLE all_tab_columns (
            owner TEXT, table_name TEXT, column_name TEXT, data_type TEXT,
            nullable INTEGER, is_pk INTEGER, comments TEXT, column_id INTEGER
        )
    """)
    
    # ---- 录入测试表（5张机械加工业务表）----
    tables = [
        ("BENTI", "CUTTING_PARAM", "切削参数表", 5000),
        ("BENTI", "MACHINE_INFO", "机床信息表", 200),
        ("BENTI", "TOOL_LIBRARY", "刀具库表", 800),
        ("BENTI", "QUALITY_CHECK", "质检记录表", 12000),
        ("BENTI", "OPERATOR_RECORD", "操作人员记录表", 350),
    ]
    cur.executemany(
        "INSERT INTO all_tables VALUES (?, ?, ?, ?, ?)", tables
    )
    
    # ---- 录入测试列（字段详情）----
    columns = [
        # CUTTING_PARAM
        ("BENTI", "CUTTING_PARAM", "cutting_speed", "FLOAT", 1, 0, "切削速度 m/min", 1),
        ("BENTI", "CUTTING_PARAM", "spindle_rpm", "INTEGER", 1, 0, "主轴转速 rpm", 2),
        ("BENTI", "CUTTING_PARAM", "feed_rate", "FLOAT", 1, 0, "进给量 mm/r", 3),
        ("BENTI", "CUTTING_PARAM", "depth_of_cut", "FLOAT", 1, 0, "切削深度 mm", 4),
        ("BENTI", "CUTTING_PARAM", "coolant_flow_rate", "FLOAT", 1, 0, "冷却液流量 L/min", 5),
        ("BENTI", "CUTTING_PARAM", "cutting_temp", "FLOAT", 1, 0, "切削温度 °C", 6),
        ("BENTI", "CUTTING_PARAM", "param_id", "VARCHAR", 0, 1, "参数ID（主键）", 7),
        # MACHINE_INFO
        ("BENTI", "MACHINE_INFO", "machine_model", "VARCHAR", 0, 0, "机床型号", 1),
        ("BENTI", "MACHINE_INFO", "rigidity_level", "VARCHAR", 1, 0, "刚性等级", 2),
        ("BENTI", "MACHINE_INFO", "max_rpm", "INTEGER", 1, 0, "最高转速", 3),
        ("BENTI", "MACHINE_INFO", "machine_id", "VARCHAR", 0, 1, "机床ID（主键）", 4),
        # TOOL_LIBRARY
        ("BENTI", "TOOL_LIBRARY", "material_type", "VARCHAR", 0, 0, "刀具材料类型", 1),
        ("BENTI", "TOOL_LIBRARY", "coating", "VARCHAR", 1, 0, "涂层材料", 2),
        ("BENTI", "TOOL_LIBRARY", "hardness", "FLOAT", 1, 0, "硬度 HRC", 3),
        ("BENTI", "TOOL_LIBRARY", "wear_amount", "FLOAT", 1, 0, "磨损量 mm", 4),
        ("BENTI", "TOOL_LIBRARY", "life_remaining", "INTEGER", 1, 0, "剩余寿命 h", 5),
        ("BENTI", "TOOL_LIBRARY", "tool_id", "VARCHAR", 0, 1, "刀具ID（主键）", 6),
        # QUALITY_CHECK
        ("BENTI", "QUALITY_CHECK", "surface_ra", "FLOAT", 1, 0, "表面粗糙度 Ra", 1),
        ("BENTI", "QUALITY_CHECK", "dim_tolerance", "FLOAT", 1, 0, "尺寸公差 mm", 2),
        ("BENTI", "QUALITY_CHECK", "nominal_dim", "FLOAT", 1, 0, "标称尺寸 mm", 3),
        ("BENTI", "QUALITY_CHECK", "quality_grade", "VARCHAR", 1, 0, "质量等级", 4),
        ("BENTI", "QUALITY_CHECK", "defect_count", "INTEGER", 1, 0, "缺陷数量", 5),
        ("BENTI", "QUALITY_CHECK", "measure_date", "DATE", 1, 0, "检测日期", 6),
        ("BENTI", "QUALITY_CHECK", "check_id", "VARCHAR", 0, 1, "检测ID（主键）", 7),
        # OPERATOR_RECORD
        ("BENTI", "OPERATOR_RECORD", "skill_level", "VARCHAR", 0, 0, "技能等级", 1),
        ("BENTI", "OPERATOR_RECORD", "cert_type", "VARCHAR", 1, 0, "证书类型", 2),
        ("BENTI", "OPERATOR_RECORD", "exp_years", "INTEGER", 1, 0, "从业年限", 3),
        ("BENTI", "OPERATOR_RECORD", "efficiency_rate", "FLOAT", 1, 0, "效率评分", 4),
        ("BENTI", "OPERATOR_RECORD", "output_qty", "INTEGER", 1, 0, "产出数量", 5),
        ("BENTI", "OPERATOR_RECORD", "operator_id", "VARCHAR", 0, 1, "操作人员ID（主键）", 6),
    ]
    cur.executemany(
        "INSERT INTO all_tab_columns VALUES (?, ?, ?, ?, ?, ?, ?, ?)", columns
    )
    
    conn.commit()
    conn.close()
    print(f"模拟数据库已创建: {DB_PATH}")


if __name__ == "__main__":
    init()
```

- [ ] **Step 2: 执行脚本生成数据库**

Run: `cd H:/Git/OCR_benti-main_win7/backend && python scripts/init_sim_db.py`
Expected: `模拟数据库已创建: ...\sim_dameng.db`

- [ ] **Step 3: 验证数据库内容**

Run: `cd H:/Git/OCR_benti-main_win7/backend && python -c "
import sqlite3
conn = sqlite3.connect('projects/sim_dameng.db')
tables = conn.execute('SELECT table_name FROM all_tables').fetchall()
print([t[0] for t in tables])
cols = conn.execute('SELECT COUNT(*) FROM all_tab_columns').fetchone()[0]
print(f'列数: {cols}')
conn.close()
"`
Expected: `['CUTTING_PARAM', 'MACHINE_INFO', 'TOOL_LIBRARY', 'QUALITY_CHECK', 'OPERATOR_RECORD']` 和 `列数: 30`

---

### Task 10: 创建 machining-demo 视角配置 [并行C]

**Files:**
- Create: `backend/projects/machining-demo_perspective.json`

- [ ] **Step 1: 创建视角配置文件**

```json
{
  "domains": [
    {
      "id": "domain-equipment",
      "name": "设备与刀具域",
      "ontology_node_ids": [
        "machine-rigidity", "tool-material", "tool-wear", "coolant-flow"
      ],
      "databases": ["BENTI_DB", "material_spec.xlsx"]
    },
    {
      "id": "domain-process",
      "name": "工艺参数域",
      "ontology_node_ids": [
        "cutting-speed", "feed-rate", "depth-of-cut", "cutting-temp"
      ],
      "databases": ["BENTI_DB"]
    },
    {
      "id": "domain-quality",
      "name": "质量检测域",
      "ontology_node_ids": [
        "surface-roughness", "dimensional-accuracy", "part-quality"
      ],
      "databases": ["BENTI_DB"]
    },
    {
      "id": "domain-personnel",
      "name": "人员与成本域",
      "ontology_node_ids": [
        "operator-skill", "machining-efficiency", "production-cost"
      ],
      "databases": ["BENTI_DB", "cost_report.csv"]
    }
  ],
  "sources": [
    {
      "id": "src-benti-db",
      "name": "BENTI_DB",
      "type": "dameng",
      "conn_info": {"host": "192.168.1.100", "port": 5236, "schema": "BENTI"},
      "tables": ["CUTTING_PARAM", "MACHINE_INFO", "TOOL_LIBRARY", "QUALITY_CHECK", "OPERATOR_RECORD"],
      "covered_nodes": 12,
      "covered_domains": ["domain-equipment", "domain-process", "domain-quality", "domain-personnel"],
      "total_fields": 22
    },
    {
      "id": "src-material-xlsx",
      "name": "material_spec.xlsx",
      "type": "excel",
      "conn_info": {"file_name": "material_spec.xlsx"},
      "tables": ["材料规格"],
      "covered_nodes": 1,
      "covered_domains": ["domain-equipment"],
      "total_fields": 3
    },
    {
      "id": "src-cost-csv",
      "name": "cost_report.csv",
      "type": "csv",
      "conn_info": {"file_name": "cost_report.csv"},
      "tables": ["cost_report.csv"],
      "covered_nodes": 2,
      "covered_domains": ["domain-personnel"],
      "total_fields": 5
    }
  ],
  "mappings": [
    {
      "ontology_node_id": "machine-rigidity",
      "source_type": "dameng", "source_name": "BENTI_DB",
      "table_name": "MACHINE_INFO",
      "field_mappings": [
        {"field_name": "rigidity_level", "attribute_key": "刚性等级", "data_type": "VARCHAR"},
        {"field_name": "machine_model", "attribute_key": "机床型号", "data_type": "VARCHAR"}
      ]
    },
    {
      "ontology_node_id": "tool-material",
      "source_type": "dameng", "source_name": "BENTI_DB",
      "table_name": "TOOL_LIBRARY",
      "field_mappings": [
        {"field_name": "material_type", "attribute_key": "材料类型", "data_type": "VARCHAR"},
        {"field_name": "coating", "attribute_key": "涂层", "data_type": "VARCHAR"},
        {"field_name": "hardness", "attribute_key": "硬度", "data_type": "FLOAT"}
      ]
    },
    {
      "ontology_node_id": "tool-wear",
      "source_type": "dameng", "source_name": "BENTI_DB",
      "table_name": "TOOL_LIBRARY",
      "field_mappings": [
        {"field_name": "wear_amount", "attribute_key": "磨损量", "data_type": "FLOAT"},
        {"field_name": "life_remaining", "attribute_key": "剩余寿命", "data_type": "INTEGER"}
      ]
    },
    {
      "ontology_node_id": "coolant-flow",
      "source_type": "dameng", "source_name": "BENTI_DB",
      "table_name": "CUTTING_PARAM",
      "field_mappings": [
        {"field_name": "coolant_flow_rate", "attribute_key": "流量", "data_type": "FLOAT"}
      ]
    },
    {
      "ontology_node_id": "cutting-speed",
      "source_type": "dameng", "source_name": "BENTI_DB",
      "table_name": "CUTTING_PARAM",
      "field_mappings": [
        {"field_name": "cutting_speed", "attribute_key": "切削速度", "data_type": "FLOAT"},
        {"field_name": "spindle_rpm", "attribute_key": "主轴转速", "data_type": "INTEGER"}
      ]
    },
    {
      "ontology_node_id": "feed-rate",
      "source_type": "dameng", "source_name": "BENTI_DB",
      "table_name": "CUTTING_PARAM",
      "field_mappings": [
        {"field_name": "feed_rate", "attribute_key": "进给量", "data_type": "FLOAT"}
      ]
    },
    {
      "ontology_node_id": "depth-of-cut",
      "source_type": "dameng", "source_name": "BENTI_DB",
      "table_name": "CUTTING_PARAM",
      "field_mappings": [
        {"field_name": "depth_of_cut", "attribute_key": "切削深度", "data_type": "FLOAT"}
      ]
    },
    {
      "ontology_node_id": "cutting-temp",
      "source_type": "dameng", "source_name": "BENTI_DB",
      "table_name": "CUTTING_PARAM",
      "field_mappings": [
        {"field_name": "cutting_temp", "attribute_key": "切削温度", "data_type": "FLOAT"}
      ]
    },
    {
      "ontology_node_id": "surface-roughness",
      "source_type": "dameng", "source_name": "BENTI_DB",
      "table_name": "QUALITY_CHECK",
      "field_mappings": [
        {"field_name": "surface_ra", "attribute_key": "粗糙度", "data_type": "FLOAT"},
        {"field_name": "measure_date", "attribute_key": "检测日期", "data_type": "DATE"}
      ]
    },
    {
      "ontology_node_id": "dimensional-accuracy",
      "source_type": "dameng", "source_name": "BENTI_DB",
      "table_name": "QUALITY_CHECK",
      "field_mappings": [
        {"field_name": "dim_tolerance", "attribute_key": "尺寸公差", "data_type": "FLOAT"},
        {"field_name": "nominal_dim", "attribute_key": "标称尺寸", "data_type": "FLOAT"}
      ]
    },
    {
      "ontology_node_id": "part-quality",
      "source_type": "dameng", "source_name": "BENTI_DB",
      "table_name": "QUALITY_CHECK",
      "field_mappings": [
        {"field_name": "quality_grade", "attribute_key": "质量等级", "data_type": "VARCHAR"},
        {"field_name": "defect_count", "attribute_key": "缺陷数", "data_type": "INTEGER"}
      ]
    },
    {
      "ontology_node_id": "operator-skill",
      "source_type": "dameng", "source_name": "BENTI_DB",
      "table_name": "OPERATOR_RECORD",
      "field_mappings": [
        {"field_name": "skill_level", "attribute_key": "技能等级", "data_type": "VARCHAR"},
        {"field_name": "cert_type", "attribute_key": "证书", "data_type": "VARCHAR"},
        {"field_name": "exp_years", "attribute_key": "从业年限", "data_type": "INTEGER"}
      ]
    },
    {
      "ontology_node_id": "machining-efficiency",
      "source_type": "dameng", "source_name": "BENTI_DB",
      "table_name": "OPERATOR_RECORD",
      "field_mappings": [
        {"field_name": "efficiency_rate", "attribute_key": "效率评分", "data_type": "FLOAT"},
        {"field_name": "output_qty", "attribute_key": "产出数量", "data_type": "INTEGER"}
      ]
    },
    {
      "ontology_node_id": "workpiece-hardness",
      "source_type": "excel", "source_name": "material_spec.xlsx",
      "table_name": "材料规格",
      "field_mappings": [
        {"field_name": "hardness_hb", "attribute_key": "硬度HB", "data_type": "FLOAT"},
        {"field_name": "material_grade", "attribute_key": "材料牌号", "data_type": "VARCHAR"}
      ]
    },
    {
      "ontology_node_id": "production-cost",
      "source_type": "csv", "source_name": "cost_report.csv",
      "table_name": "cost_report.csv",
      "field_mappings": [
        {"field_name": "material_cost", "attribute_key": "材料成本", "data_type": "FLOAT"},
        {"field_name": "labor_hour", "attribute_key": "工时", "data_type": "FLOAT"},
        {"field_name": "total_cost", "attribute_key": "总成本", "data_type": "FLOAT"}
      ]
    }
  ]
}
```

- [ ] **Step 2: 验证JSON格式**

Run: `cd H:/Git/OCR_benti-main_win7/backend && python -c "import json; data=json.load(open('projects/machining-demo_perspective.json','r',encoding='utf-8')); print(f'domains={len(data[\"domains\"])}, sources={len(data[\"sources\"])}, mappings={len(data[\"mappings\"])}')"`
Expected: `domains=4, sources=3, mappings=15`

---

### Task 11: 修改 main.py — 注册新路由 [并行D]

**Files:**
- Modify: `backend/app/main.py`

**具体改动：在 `app = FastAPI(...)` 之后添加新路由注册**

- [ ] **Step 1: 在 main.py 的 app 定义后添加路由注册**

在 `app = FastAPI(...)` 和 CORS 中间件之后，添加以下两行：

```python
from app.routers.datasource import router as datasource_router
from app.routers.perspective import router as perspective_router
app.include_router(datasource_router)
app.include_router(perspective_router)
```

- [ ] **Step 2: 验证后端启动**

Run: `cd H:/Git/OCR_benti-main_win7/backend && python -c "from app.main import app; print([r.path for r in app.routes if hasattr(r, 'path')])"`
Expected: 输出包含 `/api/datasource/*` 和 `/api/perspective/*` 相关路由

---

### Task 12-22: 前端组件创建 [并行E-1 到 E-11]

由于上下文限制，前端11个组件需要在 subagent 执行中按以下清单逐个创建，每个组件包含完整的 `<template>` + `<script setup>` + `<style scoped>`。我会在分派 subagent 时提供每个组件的详细代码规范。

**创建清单：**

| # | 文件 | 功能概要 |
|---|------|---------|
| 12 | `components/canvas/CanvasArea.vue` | SVG画布渲染、缩放平移、节点卡片布局 |
| 13 | `components/canvas/NodeCard.vue` | 单个节点卡片（本体名+属性列表+右键菜单） |
| 14 | `components/canvas/EdgeLine.vue` | 关系连线（贝塞尔曲线+箭头） |
| 15 | `components/datasource/DataSourcePanel.vue` | 数据导入入口面板（数据库/文件两个入口按钮） |
| 16 | `components/datasource/DbConnector.vue` | 数据库连接表单（类型选择、host、port、user、password） |
| 17 | `components/datasource/FileUploader.vue` | 文件拖拽/点击上传区域 |
| 18 | `components/datasource/SchemaPreview.vue` | 树形结构预览（表→列，勾选框，支持编辑名称） |
| 19 | `components/perspective/PerspectiveTabs.vue` | 顶部三个Tab切换栏 |
| 20 | `components/perspective/LeaderView.vue` | 领导视角（统计卡片+数据源表+业务域卡片） |
| 21 | `components/perspective/EngineerView.vue` | 工程师视角（数据映射表，按业务域分组） |
| 22 | `components/perspective/ProcessView.vue` | 工艺人员视角（即现有画布核心，从App.vue提取） |

- [ ] **Step: 修改 App.vue 集成新组件**

在 App.vue 顶部 `import` 区添加：

```javascript
import PerspectiveTabs from "./components/perspective/PerspectiveTabs.vue";
import DataSourcePanel from "./components/datasource/DataSourcePanel.vue";
```

在模板中，在侧边栏的"因果分析"按钮组下方添加数据导入面板入口，在画布区域上方添加视角Tab栏。

---

### Task 23: 安装新依赖 [并行G]

- [ ] **Step 1: 安装 Python 依赖**

Run: `conda run -n benti-py38 pip install dmPython openpyxl xlrd chardet`
Expected: 所有包安装成功

- [ ] **Step 2: 验证依赖导入**

Run: `conda run -n benti-py38 python -c "import openpyxl; import xlrd; import chardet; print('All OK')"`
Expected: `All OK`

---

### Task 24: 更新 PyInstaller spec [并行G]

**Files:**
- Modify: `OCR-Benti.spec`

- [ ] **Step 1: 在 spec 中添加新模块的数据收集**

在 `datas=[]` 中添加:

```
('backend/app/connectors/*', 'app/connectors'),
('backend/app/routers/*', 'app/routers'),
('backend/app/services/*', 'app/services'),
('backend/projects/sim_dameng.db', 'projects'),
```

---

## 执行顺序依赖

```
Task 1 (models) ──┬── Task 2 (base) ── Task 3 (dameng) ──┐
                  │                                       ├── Task 7 (datasource router)
                  ├── Task 4 (file_parser) ────────────────┘
                  │
                  ├── Task 5 (ontology_extract) ── Task 7 (datasource router)
                  │
                  └── Task 8 (perspective router)

Task 9 (sim_db) ── Task 10 (perspective_config) ← 可与上面并行

Task 11 (修改main.py) ← 依赖 Task 7, 8

Task 12-14 (canvas组件) ─┐
Task 15-18 (datasource组件) ├── 可与后端并行
Task 19-22 (perspective组件)┘
```

**第一波并行执行（6个Agent）**：
- Agent A: Task 1+2+3 (models + base + dameng)
- Agent B: Task 4 (file_parser)
- Agent C: Task 5+7 (ontology_extract + datasource router)
- Agent D: Task 8 (perspective router)
- Agent E: Task 9+10 (sim_db + perspective_config)
- Agent F: Task 12+13+14 (canvas组件)

**第二波并行执行**：
- Agent G: Task 11 (修改main.py注册路由)
- Agent H: Task 15+16+17+18 (datasource组件)
- Agent I: Task 19+20+21+22 (perspective组件)

**第三波**：
- Task 23 (安装依赖)
- Task 24 (更新spec + 集成App.vue)
