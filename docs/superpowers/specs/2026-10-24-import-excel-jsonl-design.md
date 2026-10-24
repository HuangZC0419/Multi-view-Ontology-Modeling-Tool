# Excel 导入修复 + JSONL 标注数据导入 设计文档

- 日期：2026-10-24
- 状态：已确认
- 范围：`frontend/`、`backend/`

## 1. 背景与目标

1. 修复 Excel 数据导入失效。
2. 新增 JSONL 标注文件导入：把「文件」作为实体（标签固定为 `文件`），把文件内被标注的实体和实体间关系组织进知识图谱。
3. JSONL 需要兼容多种导出格式，不绑定单一 schema。

## 2. Excel 导入失效诊断

### 2.1 已验证的事实

- 后端解析链路本身正常。使用 `E:\Anaconda\envs\benti-py38` 环境实测上传 `测试数据/机械加工本体关系表.xlsx`：
  - 解析出 4 张表：`实体属性`、`实体关系`、`推理规则`、`互斥规则`
  - 调 `/api/datasource/import` 生成 15 个节点、25 条关系边、3 条推理规则、1 条互斥规则
- 真实故障点在前端浮层交互。

### 2.2 根因

`frontend/src/App.vue` 的 `onFlyoutBodyClick`（约 1432 行）：

```js
function onFlyoutBodyClick(event) {
  const btn = event.target.closest("button");
  if (!btn) return;
  if (btn.classList.contains("ksp-btn")) return;
  flyoutOpen.value = false;
}
```

浮层内点击任意 `<button>` 都会收起浮层。`DataSourcePanel` 的「上传文件」「连接数据库」按钮位于浮层内，点击后：

1. 按钮自身 handler 设置 `showFileDialog = true`
2. 事件冒泡到 `.flyout-body`，`onFlyoutBodyClick` 把 `flyoutOpen` 置为 `false`
3. `v-if="flyoutOpen"` 的整个浮层（含 `FileUploader`、`SchemaPreview`）被卸载
4. 表现为「点击没反应」；即使弹窗打开，点击「确认导入」也会在同一帧被卸载，导入结果无法回传

检索面板此前踩过同类问题，已用 `.ksp-btn` 白名单绕开，数据源面板未处理。

### 2.3 附带问题

- 中文文件名乱码：Starlette 按 latin-1 解码 multipart filename，`机械加工本体关系表.xlsx` 存成 `»úÐµ¼Ó¹¤±¾Ìå¹ØÏµ±í.xlsx`，并出现在 `origin` 和预览页来源名中。
- `FileParserConnector._parse_excel` 捕获所有异常后只抛「无法打开 Excel 文件，请安装 openpyxl 或 xlrd」，掩盖真实错误。

## 3. 需求决策（已与用户确认）

| 决策点 | 结论 |
|---|---|
| 跨文件同名实体 | **全局合并**：`(label, name)` 相同即同一个节点 |
| 标签存储 | `OntologyNode` 新增 `label` 字段，节点卡片展示标签小条 |
| 导入入口 | **复用「上传文件」入口**，选择 `.jsonl` 后展示导入预览再确认 |
| 原文 `text` | **不保存**，不存摘要也不存上下文 |

## 4. 方案选择

JSONL 兼容策略采用 **规则驱动适配层**：

- 字段别名表 + 结构探测
- 无法识别时做有界递归兜底扫描
- 纯离线、确定性、可解释；预览页展示实际识别到的字段映射
- 手动字段映射（用户拖拽字段）作为后续增强，不在本期范围

## 5. 详细设计

### 5.1 数据模型

`backend/app/main.py` 的 `OntologyNode` 增加：

```python
label: str = ""
```

- 默认空字符串，老项目 JSON 无需迁移
- 前端节点数据同步携带 `label`
- `ConceptMatch`（检索结果）增加 `label` 字段，便于检索结果展示类型

### 5.2 图元素映射规则

| JSONL 内容 | 图元素 |
|---|---|
| `file_name`（去重后） | 节点，`name=file_name`，`label="文件"` |
| `spans[]` / 实体数组 | 节点，`name=text`，`label=span.label`（缺失为 `"实体"`） |
| 文件 → 其实体 | 边，`relation="包含"`，`kind="relation"`，`weight=1.0` |
| `relations[]` | 边，`relation=关系类型`（缺失为 `"关联"`），`kind="relation"`，`weight=1.0` |
| 无 `spans` 时 | 用 `annotations[]` 兜底生成实体 |
| `origin` | `jsonl:<上传的原始文件名>` |

说明：因为实体全局合并，一个实体可能属于多个文件，而 `parent_id` 只能表达单一父级，所以文件→实体一律使用显式关系边，不设置 `parent_id`。

### 5.3 后端解析层

新增 `backend/app/services/jsonl_import.py`，对外暴露：

```python
@dataclass
class JsonlParseResult:
    records: list[dict]
    mappings: dict[str, str]      # 识别到的字段映射，供预览展示
    warnings: list[str]
    total_lines: int
    bad_lines: int

def parse_jsonl(path: str | Path) -> JsonlParseResult
def build_graph(records: list[dict], origin: str) -> tuple[list[dict], list[dict], dict]
```

#### 5.3.1 行读取与容错

- 编码依次尝试 `utf-8-sig`、`utf-8`、`gb18030`。
- 逐行解析；空行跳过。
- 每行截断到第一个 `{` 开始（丢弃 `0{...}` 这类前缀）；仍解析失败则计入 `bad_lines`，最多记录 20 条警告。
- 若整文件解析为一个 JSON 数组（非逐行 JSON），按记录列表兼容。
- 记录必须是 dict，否则丢弃并告警。

#### 5.3.2 字段别名表

| 语义 | 别名（按优先级） |
|---|---|
| 文件名 | `file_name`, `fileName`, `filename`, `document_name`, `doc_name`, `source_file`, `file`, `文件名`, `文档名`, `文件` |
| 实体数组 | `spans`, `entities`, `mentions`, `ner`, `labels`, `annotations`, `实体`, `标注片段` |
| 关系数组 | `relations`, `links`, `edges`, `triples`, `关系`, `三元组` |
| 实体文本 | `text`, `mention`, `entity`, `value`, `surface`, `word`, `span_text`, `实体名`, `文本` |
| 实体标签 | `label`, `type`, `tag`, `entity_type`, `category`, `标签`, `类型` |
| 实体 id | `id`, `span_id`, `ann_id`, `key` |
| 关系起点 | `fromId`, `from_id`, `from`, `source`, `head`, `subject`, `subj`, `head_id`, `头实体` |
| 关系终点 | `toId`, `to_id`, `to`, `target`, `tail`, `object`, `obj`, `tail_id`, `尾实体` |
| 关系类型 | `type`, `relation`, `rel`, `label`, `predicate`, `关系`, `关系类型` |

补充规则：

- 文件名缺失时，回退到 `source_path` / `markdown_path` 的 basename；再回退到上传文件名；最终回退 `未命名文件`。
- 实体数组必须是 list；元素为 dict 时按上表取字段，元素为字符串时直接作为实体文本、标签默认 `"实体"`。
- 实体只保留 `text` 非空的项。
- `annotations` 仅在顶层不存在 `spans` 时作为实体兜底来源；其元素同样遵循上一条规则，缺少文本类字段的元素直接忽略（不会用 `tags` 批量造实体）。
- 关系端点先按 id 匹配；匹配不到再按实体文本匹配；仍匹配不到则跳过该关系并计数告警。
- id 在记录内命名空间化（`<record_index>:<raw_id>`），避免跨行冲突。
- 有界递归兜底：顶层找不到实体/关系数组时，最多递归 3 层查找符合命名的数组字段；实体判定条件为「对象含文本类字段 + 标签类字段」。
- 实体文本与文件名保留原文，写入图数据时不转义；HTML 安全由前端渲染层负责（`NodeCard.vue` 与 `App.vue` 的 `formatSymbol` 在 `v-html` 前调用 `escapeHtml`）。
- 关系支持同文件跨记录引用：先按记录内映射解析，再回退到文件级映射；仍无法解析的关系跳过，并在 summary 的 `unresolved_relations` 中计数。

#### 5.3.3 合并与去重

- 文件节点按 `file_name` 去重。
- 实体节点按 `(label, name)` 全局去重。
- 边按 `(source, target, relation)` 去重。
- 自环关系丢弃。

#### 5.3.4 布局

后端在原点附近完成布局，前端负责整体平移：

- 采用「文件块」布局：文件节点放在块首 `(0, cursor_y)`，该文件的新实体按 4 列网格排布在文件右侧（起始 x=320，列距 240，行距 120）
- 块高度取 `max(88, rows × 120) + 80`，下一个文件块从新的 `cursor_y` 开始
- 卡片尺寸按 200 × 88 计算，保证任意两个节点矩形不相交；已有单元测试锁定
- 已被前一个文件放置的合并实体不移动
- 位置确定、不使用随机数，保证重复导入结果稳定

### 5.4 API

#### 5.4.1 扩展 `POST /api/datasource/file/upload`

- 扩展名白名单增加 `.jsonl`
- `file_type == ".jsonl"` 时：
  1. 保存到 `uploads/{uuid}.jsonl` 并写入 meta
  2. 调用 `parse_jsonl` + `build_graph` 仅用于统计
  3. 返回：

```json
{
  "file_id": "...",
  "file_name": "annotations.jsonl",
  "file_type": ".jsonl",
  "jsonl_summary": {
    "mappings": {"file": "file_name", "entities": "spans", "relations": "relations"},
    "records": 4,
    "files": 1,
    "entities": 6,
    "relations": 0,
    "labels": {"标准条文": 6, "数值信息": 3},
    "file_names": ["测试文本.png"],
    "warnings": [],
    "bad_lines": 0,
    "total_lines": 4,
    "unresolved_relations": 0,
    "sample_nodes": [],
    "sample_edges": []
  }
}
```

#### 5.4.2 新增 `POST /api/datasource/jsonl/import`

- 入参：`{"source_id": "<file_id>"}`
- 读取 `uploads/{uuid}.jsonl`，重新解析构建图
- 返回：`{"nodes": [...], "edges": [...], "summary": {...}}`
- `source_id` 对应文件不存在时返回 404
- 解析结果为空（0 节点）时返回 400 和可读错误信息

### 5.5 前端

#### 5.5.1 Excel 修复

- `App.vue` 的 `onFlyoutBodyClick` 增加豁免：

```js
if (btn.closest(".datasource-panel, .ocr-import-group")) return;
```

- 保留 `.ksp-btn` 特例。
- 效果：数据源弹窗、OCR 识别结果弹窗不会因点击按钮而被卸载。

#### 5.5.2 中文文件名修复

`backend/app/routers/datasource.py` 增加文件名解码函数：

```python
def _decode_upload_filename(name: str) -> str:
    try:
        return name.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return name
```

上传保存 meta 与返回值统一使用解码后的文件名。

#### 5.5.3 上传器

`FileUploader.vue`：

- `ACCEPTED_TYPES` 与校验白名单增加 `.jsonl`
- 提示文案改为「支持 Excel (.xlsx / .xls)、CSV (.csv) 与 JSONL (.jsonl)」
- `data.file_type === ".jsonl"` 时，`preview-ready` 事件携带 `{sourceType: "jsonl", source_id, sourceName, summary: data.jsonl_summary}`

#### 5.5.4 导入预览组件

新增 `frontend/src/components/datasource/JsonlImportPreview.vue`：

- 展示：识别到的字段映射、记录数 / 文件数 / 实体数 / 关系数、标签分布、文件清单、警告、样例
- 「确认导入」调用 `POST /api/datasource/jsonl/import`
- 成功后 `emit("import-done", nodes, edges, [], [])`，并由父组件接收合并标记

`DataSourcePanel.vue`：

- `previewData.sourceType === "jsonl"` 时渲染 `JsonlImportPreview`
- `onImportDone` 透传 JSONL 标记

#### 5.5.5 与现有画布合并

`App.vue` 的 `onImportNodes` 增加 JSONL 专用合并路径（Excel/CSV 保持原行为）：

1. 建立 `(label, name) → 现有节点` 映射
2. 导入节点若已存在，记录 id 重映射，不新增
3. 新节点的边按重映射后的 id 指向目标；指向失败或重复的边丢弃
4. 计算画布现有节点包围盒，把整批新节点平移到右侧（原有内容为空时不平移）
5. 追加节点/边后调用 `syncGraph`

效果：重复导入同一 JSONL 幂等；跨文件实体自然汇聚。

#### 5.5.6 标签展示

`NodeCard.vue`：

- `node.label` 非空时，在节点图标/名称区域渲染标签小条
- 不同标签使用稳定分配的颜色（按标签名哈希取色），文件标签固定使用一种醒目标记

### 5.6 错误处理

| 场景 | 处理 |
|---|---|
| Excel 解析异常 | 错误信息附带原始异常文本 |
| JSONL 无有效记录 | 预览页提示「未识别到有效记录」，「确认导入」禁用 |
| 存在坏行 | 预览页展示坏行数与前几条警告，仍允许导入有效记录 |
| 关系端点缺失 | 跳过该关系并计入警告 |
| 重复导入 | 节点/边去重，不产生重复 |
| 上传文件已过期 | 返回 404，预览页给出重新上传提示 |

## 6. 测试

### 6.1 单元测试

新增 `backend/tests/test_jsonl_import.py`，使用标准库 `unittest`（`benti-py38` 环境未安装 pytest）：

- 样本 A `annotations.jsonl`：数字 span id、`fromId/toId` 关系、首行 `0` 前缀
- 样本 B `测试文本_annotations.jsonl`：同文件多行、字符串 id、`annotations` 汇总
- 变体：JSON 数组整体文件、GBK 编码、关系端点用实体文本、坏 JSON 行、空 span 文本
- 断言：文件节点数、实体数、边数、标签分布、坏行计数、幂等性（构建两次结果一致）

### 6.2 接口冒烟

用 `urllib`（不依赖 httpx）实测：

1. 启动 `benti-py38` 后端
2. 上传两个真实 JSONL → 检查 `jsonl_summary`
3. 调 `/api/datasource/jsonl/import` → 核对节点/边数量
4. 重复导入 → 验证前端合并逻辑所需的 id 稳定性

### 6.3 手工验证

- Excel：点击「上传文件」→ 弹窗正常出现 → 选表/列 → 确认导入 → 节点出现在画布并持久化
- JSONL：上传 → 预览信息正确 → 确认导入 → 文件节点与实体节点正确、标签显示、关系边正确
- 中文文件名显示正常

## 7. 非目标

- 不引入 LLM 辅助字段推断
- 不做用户手动拖拽字段映射
- 不保存原文 `text`
- 不改变 Excel/CSV 现有的「表名→父节点、列名→子节点」行为
- 不重构无关的画布或检索逻辑

## 8. 风险

| 风险 | 缓解 |
|---|---|
| 别名表覆盖不到某些格式 | 预览页展示识别结果；坏行/缺字段有告警；后续可补别名 |
| 全局合并产生过大连通图 | 文件节点与实体节点标签区分；后续可加按标签折叠 |
| 大量实体导致布局拥挤 | 环形分环 + 前端整体平移；先保证不重叠，不做自动力导布局 |
| `v-html` 渲染导入文本 | 数据层保留原文，渲染层 `escapeHtml` 后再 `v-html` |
