# 多数据源接入 + 多视角查询系统 设计文档

日期: 2026-05-22 | 状态: 已确认

## 一、需求概述

为本体建模系统新增三大功能：

1. **国产数据库连接** — 支持达梦 DM8 数据库，读取表结构元数据，提取本体概念（仅概念层，不导入实例）
2. **Excel/CSV 文件导入** — 上传文件，解析 Sheet/列名，提取本体概念
3. **多视角查询** — 基于 machining-demo 案例，支持领导/软件工程师/工艺人员三种视角切换

约束：所有依赖放入 conda 环境 `benti-py38`，目标平台 Windows 7，后续用 PyInstaller 打包。

## 二、关键决策

| 决策项 | 选择 |
|--------|------|
| 三个功能开发顺序 | 并行开发 |
| 数据库范围 | 仅达梦 DM8（通过抽象基类预留扩展能力） |
| 视角切换方式 | 顶部 Tab 栏切换，点击后画布内容重新组织 |
| 本体提取流程 | 半自动：预览结构 → 用户勾选编辑 → 确认导入 |
| machining-demo | 完全重新设计，三层架构覆盖三种视角 |

## 三、架构方案（方案C：混合式）

只拆分新增功能为独立模块，现有核心逻辑（main.py 本体CRUD、贝叶斯分析）保持不变。

### 3.1 后端新模块

```
backend/app/
├── main.py                   # 不变：本体编辑、贝叶斯分析、项目管理
├── models.py                 # 新增：共享Pydantic模型 + 数据源/视角模型
├── routers/
│   ├── datasource.py         # 新增：数据库连接、Excel/CSV解析、本体导入
│   └── perspective.py        # 新增：多视角查询API
├── connectors/
│   ├── base.py               # 新增：DataSourceConnector抽象基类
│   ├── dameng.py             # 新增：达梦数据库连接器（dmPython）
│   └── file_parser.py        # 新增：Excel/CSV解析器
└── services/
    └── ontology_extract.py   # 新增：本体概念提取逻辑
```

### 3.2 前端新组件

```
frontend/src/
├── App.vue                   # 精简：保留主框架 + 画布核心
├── components/
│   ├── canvas/               # 画布相关
│   │   ├── CanvasArea.vue
│   │   ├── NodeCard.vue
│   │   └── EdgeLine.vue
│   ├── datasource/           # 数据导入面板
│   │   ├── DataSourcePanel.vue
│   │   ├── DbConnector.vue
│   │   ├── FileUploader.vue
│   │   └── SchemaPreview.vue
│   └── perspective/          # 多视角
│       ├── PerspectiveTabs.vue
│       ├── LeaderView.vue
│       ├── EngineerView.vue
│       └── ProcessView.vue
```

## 四、数据源接入模块设计

### 4.1 连接器抽象基类

```python
class DataSourceConnector(ABC):
    async def connect(config: dict) -> bool
    async def disconnect()
    async def test_connection(config: dict) -> bool
    async def get_tables() -> list[TableInfo]
    async def get_columns(table: str) -> list[ColumnInfo]
    async def preview_data(table: str, limit=10) -> list[dict]
```

### 4.2 达梦连接器

- 驱动：dmPython（conda benti-py38 安装）
- 连接参数：host, port(5236), user, password, schema
- 元数据查询：ALL_TABLES / ALL_TAB_COLUMNS 系统视图
- 注释支持：读取表和字段的 COMMENT 作为本体名称提示

### 4.3 文件解析器

- Excel：openpyxl (.xlsx) + xlrd (.xls)，Sheet → 概念源，第1行 → 列名
- CSV：内置 csv + chardet 编码检测 + 分隔符自动识别

### 4.4 半自动本体提取流程

1. 获取结构：连接器返回 TableInfo[] / ColumnInfo[]
2. 预览确认：前端 SchemaPreview 组件展示树形结构，用户勾选
3. 概念提取：表名→父节点，列名→子节点(属性=类型+注释)
4. 导入画布：POST /api/datasource/import 追加到当前项目

### 4.5 开发阶段模拟方案

使用 SQLite + SimDamengConnector 模拟达梦表结构，查询 all_tables/all_tab_columns 两个模拟系统表。

### 4.6 API 端点

| 方法 | 路由 | 功能 |
|------|------|------|
| POST | /api/datasource/db/test | 测试数据库连接 |
| POST | /api/datasource/db/connect | 建立连接，返回 session_id |
| GET | /api/datasource/db/tables | 获取表列表 |
| GET | /api/datasource/db/tables/{table}/columns | 获取列信息 |
| GET | /api/datasource/db/tables/{table}/preview | 预览数据 |
| POST | /api/datasource/db/disconnect | 断开连接 |
| POST | /api/datasource/file/upload | 上传Excel/CSV，返回结构 |
| GET | /api/datasource/file/{file_id}/preview | 预览文件数据 |
| POST | /api/datasource/import | 提交勾选，生成本体导入 |

## 五、多视角查询模块设计

### 5.1 三层概念架构

| 层级 | 视角 | 内容 |
|------|------|------|
| 第1层 业务域 | 领导视角 | 4个业务域 + 数据源全景 + 覆盖度分析 |
| 第2层 本体概念 | 工艺人员视角 | 15个节点 + 25条关系 + 贝叶斯分析（现有画布） |
| 第3层 数据映射 | 软件工程师视角 | 本体→数据源→表→字段 四级映射表 |

### 5.2 三种视角内容

**领导视角**：
- 统计指标卡片（业务域数/概念数/数据源数/关系数）
- 数据源全景表（达梦BENTI_DB + Excel + CSV，含连接信息、表清单、支撑域）
- 数据源→业务域映射图
- 数据源覆盖度分析（进度条可视化）

**软件工程师视角**：
- 本体概念→数据源→表名→字段名→类型 五列明细表
- 按业务域分组展示
- 点击可查看数据血缘详情

**工艺人员视角**：
- 现有本体画布（节点+关系+推理规则）
- 贝叶斯分析面板（上游追溯/下游传播/全局概览）
- 完整的图编辑功能

### 5.3 数据模型

- `PerspectiveType` — leader/engineer/process 枚举
- `BusinessDomain` — 业务域（名称、包含节点、支撑数据库列表）
- `DataSourceInfo` — 数据源元信息（名称、类型、连接信息、表清单、覆盖度）
- `DataMapping` — 数据映射（本体节点→数据源→表→字段）
- `FieldMapping` — 字段映射（字段名→属性名→数据类型）
- `LeaderViewData` — 领导视角完整数据聚合

### 5.4 API 端点

| 方法 | 路由 | 功能 |
|------|------|------|
| GET | /api/perspective/{project_id}/leader | 领导视角数据 |
| GET | /api/perspective/{project_id}/engineer | 工程师视角数据 |
| GET | /api/perspective/{project_id}/process | 工艺人员视角数据（即现有图数据） |
| PUT | /api/perspective/{project_id}/mappings | 批量更新数据映射 |
| GET | /api/perspective/{project_id}/domains | 获取业务域配置 |
| PUT | /api/perspective/{project_id}/domains | 更新业务域配置 |

## 六、重新设计的 machining-demo 数据

### 6.1 业务域（4个）

| 域 | 概念数 | 数据源 |
|----|--------|--------|
| 设备与刀具域 | 4 | 达梦·BENTI_DB + Excel·material_spec |
| 工艺参数域 | 4 | 达梦·BENTI_DB |
| 质量检测域 | 3 | 达梦·BENTI_DB |
| 人员与成本域 | 3 | 达梦·BENTI_DB + CSV·cost_report |

### 6.2 数据源（3个）

| 数据源 | 类型 | 表/文件 | 字段数 | 覆盖概念 |
|--------|------|---------|--------|----------|
| BENTI_DB | 达梦DM8 | MACHINE_INFO, TOOL_LIBRARY, CUTTING_PARAM, QUALITY_CHECK, OPERATOR_RECORD | 22 | 12/15 |
| material_spec.xlsx | Excel | 材料规格 | 3 | 1/15 |
| cost_report.csv | CSV | cost_report.csv | 5 | 2/15 |

### 6.3 数据映射（15条映射）

每个本体概念映射到 数据源/表名/字段名/字段类型，详见设计原型。

## 七、依赖清单（conda benti-py38）

现有依赖保持不变，新增：
- dmPython（达梦官方Python驱动）
- openpyxl（Excel .xlsx 读写）
- xlrd（Excel .xls 读取）
- chardet（编码检测，CSV用）

## 八、约束

- 所有依赖放入 conda=benti-py38
- 目标平台 Windows 7，后续 PyInstaller 打包
- 前端 API_BASE 为空字符串，Vite proxy 本地代转
- 前端 server.host 为 0.0.0.0
- 不引入 Vue Router / Pinia（保持现有简洁架构）
