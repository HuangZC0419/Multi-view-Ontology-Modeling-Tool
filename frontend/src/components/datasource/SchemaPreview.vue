<script setup>
import { reactive, computed, ref } from "vue";

const API_BASE = import.meta.env.VITE_API_BASE ||
  (typeof window !== "undefined" ? `http://${window.location.hostname}:8000` : "http://127.0.0.1:8000");

const props = defineProps({
  previewData: {
    type: Object,
    required: true,
  },
});

const emit = defineEmits(["import-done", "back"]);

// ---------- 初始化勾选 ----------
const tablesList = computed(() => props.previewData.tables || []);
const columnsMap = computed(() => props.previewData.columns || {});

const selection = reactive({
  source_id: props.previewData.source_id || "",
  tables: [],
  columns: {},
  edited_names: {},
});

// 展开/折叠状态
const expandedTables = reactive({});
const editingCell = ref(null); // {table, column|null, value}
const editingValue = ref("");
const isImporting = ref(false);
const importError = ref("");

// 初始化: 默认只展开前几个表，并且全选所有表和列
function initSelection() {
  tablesList.value.forEach((t, idx) => {
    const name = typeof t === "string" ? t : t.name;
    expandedTables[name] = idx < 3; // 默认展开前3个表
    selection.tables.push(name);
    
    const cols = columnsMap.value[name] || [];
    selection.columns[name] = cols.map(c => (typeof c === "string" ? c : c.name));
  });
}

// 使用一个简单的标记确保只初始化一次
if (tablesList.value.length > 0) {
  initSelection();
}

// ---------- 表选项 ----------
function getTableName(table) {
  return typeof table === "string" ? table : table.name;
}

function getTableComment(table) {
  return typeof table === "string" ? "" : table.comment || "";
}

function getTableRowCount(table) {
  return typeof table === "string" ? 0 : table.row_count || 0;
}

// ---------- 勾选逻辑 ----------
function isTableChecked(tableName) {
  return selection.tables.includes(tableName);
}

function isColumnChecked(tableName, colName) {
  return (selection.columns[tableName] || []).includes(colName);
}

function isTableIndeterminate(tableName) {
  const cols = columnsMap.value[tableName] || [];
  const checked = selection.columns[tableName] || [];
  return checked.length > 0 && checked.length < cols.length;
}

function toggleTable(tableName) {
  const checked = isTableChecked(tableName);
  const cols = columnsMap.value[tableName] || [];
  const colNames = cols.map(c => (typeof c === "string" ? c : c.name));

  if (checked) {
    // 取消全选
    selection.tables = selection.tables.filter(t => t !== tableName);
    delete selection.columns[tableName];
  } else {
    // 全选
    selection.tables.push(tableName);
    selection.columns[tableName] = [...colNames];
  }
}

function toggleColumn(tableName, colName) {
  if (!selection.columns[tableName]) {
    selection.columns[tableName] = [];
  }

  const idx = selection.columns[tableName].indexOf(colName);
  if (idx > -1) {
    selection.columns[tableName].splice(idx, 1);
  } else {
    selection.columns[tableName].push(colName);
  }

  // 同步表级勾选状态
  const cols = columnsMap.value[tableName] || [];
  const colNamesAll = cols.map(c => (typeof c === "string" ? c : c.name));
  const selectedAll = colNamesAll.every(n => selection.columns[tableName].includes(n));

  if (selectedAll && !selection.tables.includes(tableName)) {
    selection.tables.push(tableName);
  } else if (!selectedAll && selection.tables.includes(tableName)) {
    selection.tables = selection.tables.filter(t => t !== tableName);
  }
}

// ---------- 列辅助函数 ----------
function getColName(col) {
  return typeof col === "string" ? col : col.name;
}

function getColType(col) {
  return typeof col === "string" ? "" : col.data_type || "";
}

function getColComment(col) {
  return typeof col === "string" ? "" : col.comment || "";
}

function isColNullable(col) {
  return typeof col === "string" ? true : col.nullable !== false;
}

function isColPk(col) {
  return typeof col === "string" ? false : col.is_pk === true;
}

// ---------- 内联编辑 ----------
function startEdit(tableName, colName) {
  const key = colName || tableName;
  const displayName = selection.edited_names[key] || key;
  editingCell.value = { table: tableName, column: colName || null, value: key };
  editingValue.value = displayName;
}

function confirmEdit() {
  if (!editingCell.value) return;
  const { table, column, value: originalName } = editingCell.value;
  const trimmed = editingValue.value.trim();

  if (trimmed && trimmed !== originalName) {
    selection.edited_names[originalName] = trimmed;
  } else if (trimmed === originalName) {
    delete selection.edited_names[originalName];
  }

  editingCell.value = null;
  editingValue.value = "";
}

function cancelEdit() {
  editingCell.value = null;
  editingValue.value = "";
}

function getDisplayName(originalName) {
  return selection.edited_names[originalName] || originalName;
}

// ---------- 确认导入 ----------
async function confirmImport() {
  if (selection.tables.length === 0) {
    importError.value = "请至少选择一个表";
    return;
  }

  // 校验每个选中的表至少有一列被勾选
  for (const tableName of selection.tables) {
    const cols = selection.columns[tableName] || [];
    if (cols.length === 0) {
      importError.value = `表「${getDisplayName(tableName)}」未勾选任何列`;
      return;
    }
  }

  isImporting.value = true;
  importError.value = "";

  try {
    const resp = await fetch(`${API_BASE}/api/datasource/import`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source_id: selection.source_id,
        tables: selection.tables,
        columns: selection.columns,
        edited_names: selection.edited_names,
      }),
    });

    if (!resp.ok) {
      const errData = await resp.json().catch(() => ({}));
      throw new Error(errData.detail || errData.message || "导入失败");
    }

    const data = await resp.json();
    emit("import-done", data.nodes || [], data.edges || [], data.inference_rules || [], data.mutex_rules || []);
  } catch (err) {
    importError.value = err.message || "导入请求失败";
  } finally {
    isImporting.value = false;
  }
}

// ---------- 已选统计 ----------
const selectedTableCount = computed(() => selection.tables.length);
const selectedColumnCount = computed(() => {
  let count = 0;
  Object.values(selection.columns).forEach(list => {
    count += list.length;
  });
  return count;
});
</script>

<template>
  <div class="sp-overlay" @click.self="emit('back')">
    <div class="sp-dialog" @click.stop>
      <!-- 头部 -->
      <div class="sp-header">
        <div class="sp-header-left">
          <button class="sp-back-btn" @click="emit('back')">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="15 18 9 12 15 6"/>
            </svg>
          </button>
          <h2>数据结构预览</h2>
          <span class="sp-source-badge">
            {{ previewData.sourceType === 'db' ? '数据库' : '文件' }}
          </span>
          <span v-if="previewData.sourceName" class="sp-source-name">{{ previewData.sourceName }}</span>
        </div>
        <div class="sp-header-right">
          <span class="sp-stat">
            共 <strong>{{ selectedTableCount }}</strong> 表 / <strong>{{ selectedColumnCount }}</strong> 列
          </span>
        </div>
      </div>

      <!-- 体部 -->
      <div class="sp-body">
        <!-- 错误 -->
        <div v-if="importError" class="sp-error-box">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
          </svg>
          <span>{{ importError }}</span>
        </div>

        <!-- 表树 -->
        <div v-if="tablesList.length > 0" class="sp-tree">
          <div
            v-for="(table, tIdx) in tablesList"
            :key="getTableName(table)"
            class="sp-table-node"
          >
            <!-- 表行 -->
            <div class="sp-table-row">
              <!-- 展开折叠 -->
              <button
                class="sp-expand-btn"
                @click="expandedTables[getTableName(table)] = !expandedTables[getTableName(table)]"
              >
                <svg
                  viewBox="0 0 24 24"
                  width="14"
                  height="14"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2.5"
                  stroke-linecap="round"
                  :class="{ rotated: expandedTables[getTableName(table)] }"
                >
                  <polyline points="9 18 15 12 9 6"/>
                </svg>
              </button>

              <!-- 表名可编辑 -->
              <div class="sp-table-info" @dblclick="startEdit(getTableName(table), null)">
                <!-- 编辑中 -->
                <template v-if="editingCell && editingCell.table === getTableName(table) && !editingCell.column">
                  <input
                    class="sp-inline-input"
                    v-model="editingValue"
                    @keydown.enter="confirmEdit"
                    @keydown.escape="cancelEdit"
                    @blur="confirmEdit"
                    ref="editInput"
                    autofocus
                  />
                </template>
                <!-- 显示 -->
                <template v-else>
                  <span class="sp-table-name">
                    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
                      <polyline points="9 22 9 12 15 12 15 22"/>
                    </svg>
                    {{ getDisplayName(getTableName(table)) }}
                  </span>
                  <span v-if="getTableComment(table)" class="sp-table-comment">{{ getTableComment(table) }}</span>
                  <span v-if="getTableRowCount(table) > 0" class="sp-table-rows">{{ getTableRowCount(table) }} 行</span>
                </template>

                <!-- 编辑按钮 -->
                <button
                  class="sp-edit-btn"
                  @click.stop="startEdit(getTableName(table), null)"
                  title="编辑表名"
                >
                  <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                  </svg>
                </button>
              </div>
            </div>

            <!-- 列列表（展开时） -->
            <div v-if="expandedTables[getTableName(table)]" class="sp-column-list">
              <div
                v-for="(col, cIdx) in (columnsMap[getTableName(table)] || [])"
                :key="getColName(col)"
                class="sp-column-row"
              >
                <div class="sp-col-indent">
                  <!-- 列名可编辑 -->
                  <div class="sp-column-info" @dblclick="startEdit(getTableName(table), getColName(col))">
                    <template v-if="editingCell && editingCell.table === getTableName(table) && editingCell.column === getColName(col)">
                      <input
                        class="sp-inline-input"
                        v-model="editingValue"
                        @keydown.enter="confirmEdit"
                        @keydown.escape="cancelEdit"
                        @blur="confirmEdit"
                        autofocus
                      />
                    </template>
                    <template v-else>
                      <span class="sp-column-name">{{ getDisplayName(getColName(col)) }}</span>
                      <span v-if="getColType(col)" class="sp-column-type">{{ getColType(col) }}</span>
                      <span v-if="isColPk(col)" class="sp-column-pk">PK</span>
                      <span v-if="!isColNullable(col)" class="sp-column-nn">NOT NULL</span>
                      <span v-if="getColComment(col)" class="sp-column-comment">{{ getColComment(col) }}</span>
                    </template>

                    <!-- 编辑按钮 -->
                    <button
                      class="sp-edit-btn"
                      @click.stop="startEdit(getTableName(table), getColName(col))"
                      title="编辑列名"
                    >
                      <svg viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                        <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                      </svg>
                    </button>
                  </div>
                </div>
              </div>

              <!-- 无列提示 -->
              <div v-if="!columnsMap[getTableName(table)] || columnsMap[getTableName(table)].length === 0" class="sp-column-empty">
                无列信息
              </div>
            </div>
          </div>
        </div>

        <!-- 无数据提示 -->
        <div v-else class="sp-empty">
          <p>暂无表数据</p>
        </div>
      </div>

      <!-- 底部操作栏 -->
      <div class="sp-footer">
        <button class="sp-btn sp-btn-ghost" @click="emit('back')">
          返回
        </button>
        <button
          class="sp-btn sp-btn-primary"
          @click="confirmImport"
          :disabled="isImporting || selectedTableCount === 0"
        >
          <svg v-if="!isImporting" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M5 12h14"/><path d="M12 5l7 7-7 7"/>
          </svg>
          <div v-else class="sp-btn-spinner"></div>
          {{ isImporting ? '导入中...' : `确认导入 (${selectedColumnCount})` }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* ======================== 变量 ======================== */
.sp-overlay {
  --color-primary: #2563eb;
  --color-primary-dark: #1d4ed8;
  --color-primary-bg: #eff6ff;
  --color-success: #10b981;
  --color-success-bg: #d1fae5;
  --color-danger: #dc2626;
  --color-danger-bg: #fef2f2;
  --color-warning: #d97706;
  --color-text: #0f172a;
  --color-text-secondary: #475569;
  --color-text-muted: #64748b;
  --color-border: #e2e8f0;
  --color-bg: #f8fafc;
  --color-surface: #ffffff;
  --shadow-sm: 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
  --shadow-md: 0 4px 6px -1px rgba(0,0,0,0.06), 0 2px 4px -2px rgba(0,0,0,0.04);
  --shadow-xl: 0 20px 40px -8px rgba(0,0,0,0.12), 0 10px 15px -3px rgba(0,0,0,0.08);
  --radius-sm: 6px;
  --radius-md: 8px;
  --radius-lg: 12px;
  --radius-xl: 16px;
}

/* ---------- 遮罩 ---------- */
.sp-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.5);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 151;
  animation: sp-overlay-in 0.15s ease-out;
}

@keyframes sp-overlay-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

/* ---------- 弹窗卡片 ---------- */
.sp-dialog {
  background: #ffffff;
  border-radius: var(--radius-xl);
  width: 680px;
  max-width: 95vw;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-xl);
  animation: sp-dialog-in 0.22s ease-out;
}

@keyframes sp-dialog-in {
  from { opacity: 0; transform: scale(0.95) translateY(10px); }
  to { opacity: 1; transform: scale(1) translateY(0); }
}

/* ---------- 头部 ---------- */
.sp-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 22px 16px 22px;
  border-bottom: 1px solid #f1f5f9;
  flex-shrink: 0;
  flex-wrap: wrap;
  gap: 10px;
}

.sp-header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.sp-back-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  background: none;
  border: 1px solid #e2e8f0;
  border-radius: var(--radius-md);
  color: #64748b;
  cursor: pointer;
  transition: all 0.18s ease;
  flex-shrink: 0;
}

.sp-back-btn:hover {
  background: #f1f5f9;
  border-color: #cbd5e1;
  color: #0f172a;
}

.sp-header-left h2 {
  margin: 0;
  font-size: 17px;
  font-weight: 700;
  color: #0f172a;
  white-space: nowrap;
}

.sp-source-badge {
  padding: 3px 8px;
  background: #eff6ff;
  color: #1e40af;
  font-size: 11px;
  font-weight: 600;
  border-radius: 4px;
  white-space: nowrap;
}

.sp-source-name {
  font-size: 12.5px;
  color: #94a3b8;
  font-weight: 500;
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sp-header-right {
  flex-shrink: 0;
}

.sp-stat {
  font-size: 12.5px;
  color: #64748b;
  font-weight: 500;
}

.sp-stat strong {
  color: #2563eb;
}

/* ---------- 错误 ---------- */
.sp-error-box {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 10px 14px;
  margin-bottom: 14px;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: var(--radius-md);
  color: #dc2626;
  font-size: 13px;
  font-weight: 500;
}

.sp-error-box svg {
  flex-shrink: 0;
  margin-top: 1px;
}

/* ---------- 体部 ---------- */
.sp-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px 22px;
}

/* ---------- 空状态 ---------- */
.sp-empty {
  text-align: center;
  padding: 48px 24px;
  color: #94a3b8;
  font-size: 14px;
  font-weight: 500;
}

/* ---------- 树 ---------- */
.sp-tree {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

/* ---------- 表节点 ---------- */
.sp-table-node {
  border: 1px solid #f1f5f9;
  border-radius: var(--radius-md);
  overflow: hidden;
  transition: border-color 0.2s ease;
}

.sp-table-node:hover {
  border-color: #e2e8f0;
}

.sp-table-row {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 12px;
  background: #f8fafc;
  cursor: default;
  transition: background 0.15s ease;
}

.sp-table-row:hover {
  background: #f1f5f9;
}

/* ---------- 复选框 ---------- */
.sp-check-label {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}

.sp-check-label input[type="checkbox"] {
  width: 16px;
  height: 16px;
  accent-color: #2563eb;
  cursor: pointer;
  margin: 0;
}

/* ---------- 展开按钮 ---------- */
.sp-expand-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  background: none;
  border: none;
  color: #94a3b8;
  cursor: pointer;
  transition: all 0.18s ease;
  flex-shrink: 0;
  padding: 0;
}

.sp-expand-btn:hover {
  color: #475569;
}

.sp-expand-btn svg {
  transition: transform 0.2s ease;
}

.sp-expand-btn svg.rotated {
  transform: rotate(90deg);
}

/* ---------- 表信息 ---------- */
.sp-table-info {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  cursor: text;
}

.sp-table-name {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
  white-space: nowrap;
}

.sp-table-name svg {
  color: #94a3b8;
  flex-shrink: 0;
}

.sp-table-comment {
  font-size: 12px;
  color: #94a3b8;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sp-table-rows {
  font-size: 11px;
  color: #94a3b8;
  font-weight: 500;
  background: #f1f5f9;
  padding: 1px 6px;
  border-radius: 3px;
  white-space: nowrap;
}

/* ---------- 列列表 ---------- */
.sp-column-list {
  border-top: 1px solid #f1f5f9;
}

.sp-column-row {
  transition: background 0.12s ease;
}

.sp-column-row:hover {
  background: #fafbfc;
}

.sp-column-row.selected {
  background: #f8faff;
}

.sp-col-indent {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px 8px 50px;
}

.sp-column-info {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  flex-wrap: wrap;
  cursor: text;
}

.sp-column-name {
  font-size: 13px;
  font-weight: 500;
  color: #334155;
}

.sp-column-type {
  font-size: 11px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  color: #6366f1;
  background: #eef2ff;
  padding: 1px 6px;
  border-radius: 3px;
  white-space: nowrap;
}

.sp-column-pk {
  font-size: 10px;
  font-weight: 700;
  color: #d97706;
  background: #fffbeb;
  padding: 1px 5px;
  border-radius: 3px;
  white-space: nowrap;
}

.sp-column-nn {
  font-size: 10px;
  font-weight: 500;
  color: #dc2626;
  background: #fef2f2;
  padding: 1px 5px;
  border-radius: 3px;
  white-space: nowrap;
}

.sp-column-comment {
  font-size: 11px;
  color: #94a3b8;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sp-column-empty {
  padding: 12px 12px 12px 50px;
  font-size: 12px;
  color: #94a3b8;
  font-style: italic;
}

/* ---------- 编辑按钮 ---------- */
.sp-edit-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  background: none;
  border: 1px solid transparent;
  border-radius: 4px;
  color: #cbd5e1;
  cursor: pointer;
  transition: all 0.15s ease;
  flex-shrink: 0;
  opacity: 0;
}

.sp-table-row:hover .sp-edit-btn,
.sp-column-row:hover .sp-edit-btn {
  opacity: 1;
}

.sp-edit-btn:hover {
  background: #f1f5f9;
  border-color: #e2e8f0;
  color: #475569;
}

/* ---------- 内联编辑 input ---------- */
.sp-inline-input {
  padding: 4px 8px;
  border: 1.5px solid #bfdbfe;
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-weight: 600;
  color: #0f172a;
  background: #ffffff;
  outline: none;
  width: 100%;
  max-width: 280px;
  font-family: inherit;
  box-sizing: border-box;
}

.sp-inline-input:focus {
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
}

/* ---------- 底部 ---------- */
.sp-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 22px;
  border-top: 1px solid #f1f5f9;
  background: #f8fafc;
  flex-shrink: 0;
}

/* ---------- 按钮 ---------- */
.sp-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 10px 20px;
  border-radius: var(--radius-md);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  border: 1px solid transparent;
  outline: none;
  font-family: inherit;
}

.sp-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.sp-btn-primary {
  background: #2563eb;
  color: #ffffff;
  box-shadow: 0 4px 6px -1px rgba(37, 99, 235, 0.2);
}

.sp-btn-primary:hover:not(:disabled) {
  background: #1d4ed8;
  box-shadow: 0 6px 8px -1px rgba(37, 99, 235, 0.3);
  transform: translateY(-1px);
}

.sp-btn-ghost {
  background: transparent;
  color: #475569;
}

.sp-btn-ghost:hover {
  color: #0f172a;
  background: #f1f5f9;
  border-color: #e2e8f0;
}

/* ---------- 按钮内加载 spinner ---------- */
.sp-btn-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: #ffffff;
  border-radius: 50%;
  animation: sp-btn-spin 0.6s linear infinite;
}

@keyframes sp-btn-spin {
  to { transform: rotate(360deg); }
}

/* ---------- 滚动条 ---------- */
.sp-body {
  scrollbar-width: thin;
  scrollbar-color: #e2e8f0 transparent;
}

.sp-body::-webkit-scrollbar {
  width: 4px;
}

.sp-body::-webkit-scrollbar-track {
  background: transparent;
}

.sp-body::-webkit-scrollbar-thumb {
  background: #e2e8f0;
  border-radius: 2px;
}

.sp-body::-webkit-scrollbar-thumb:hover {
  background: #cbd5e1;
}
</style>
