<script setup>
import { ref, onMounted, watch, computed } from "vue";

const props = defineProps({
  projectId: { type: String, required: true },
});

// API_BASE 常量定义
const defaultApiBase =
  typeof window !== "undefined"
    ? `http://${window.location.hostname}:8000`
    : "http://127.0.0.1:8000";
const API_BASE = import.meta.env.VITE_API_BASE || defaultApiBase;

const data = ref(null);
const loading = ref(true);
const error = ref(null);

/** 搜索关键词 */
const searchText = ref("");

/** 选中的类型筛选 */
const filterType = ref("all");

async function loadData() {
  loading.value = true;
  error.value = null;
  try {
    const resp = await fetch(
      `${API_BASE}/api/perspective/${props.projectId}/engineer`
    );
    if (!resp.ok) {
      throw new Error(`HTTP ${resp.status}: ${await resp.text()}`);
    }
    data.value = await resp.json();
  } catch (e) {
    error.value = e.message;
    console.error("EngineerView: 加载数据失败:", e);
  } finally {
    loading.value = false;
  }
}

onMounted(loadData);
watch(() => props.projectId, loadData);

// 数据源类型颜色映射
const sourceTypeStyles = {
  dameng: { bg: "#f5f3ff", color: "#7c3aed", border: "#c4b5fd", label: "达梦" },
  excel: { bg: "#d1fae5", color: "#059669", border: "#a7f3d0", label: "Excel" },
  csv: { bg: "#fffbeb", color: "#d97706", border: "#fcd34d", label: "CSV" },
};

function sourceTypeStyle(type) {
  const key = (type || "").toLowerCase();
  return (
    sourceTypeStyles[key] || {
      bg: "#f1f5f9",
      color: "#475569",
      border: "#e2e8f0",
      label: type,
    }
  );
}

/**
 * 将 mappings 按业务域分组
 * 返回 [{ domain, mappings: [...] }]
 */
const groupedMappings = computed(() => {
  if (!data.value?.mappings) return [];

  const domains = data.value.domains || [];
  const domainMap = new Map();
  domains.forEach((d) => domainMap.set(d.id || d.name, d.name || d.id));

  // 按 domain_id 分组
  const groups = {};
  data.value.mappings.forEach((m) => {
    const domainId = m.domain_id || "_uncategorized";
    if (!groups[domainId]) {
      groups[domainId] = [];
    }
    groups[domainId].push(m);
  });

  // 过滤搜索和类型
  const result = [];
  Object.entries(groups).forEach(([domainId, mappings]) => {
    let filtered = mappings;

    // 搜索过滤
    if (searchText.value.trim()) {
      const keyword = searchText.value.trim().toLowerCase();
      filtered = filtered.filter((m) => {
        const concept = (m.concept || m.ontology_node || "").toLowerCase();
        const table = (m.table_name || "").toLowerCase();
        const field = (m.field_name || "").toLowerCase();
        const source = (m.source_name || "").toLowerCase();
        return (
          concept.includes(keyword) ||
          table.includes(keyword) ||
          field.includes(keyword) ||
          source.includes(keyword)
        );
      });
    }

    // 类型过滤
    if (filterType.value !== "all") {
      filtered = filtered.filter(
        (m) => (m.source_type || "").toLowerCase() === filterType.value
      );
    }

    if (filtered.length === 0) return;

    const domainName = domainMap.get(domainId) || domainId;
    result.push({ domainId, domainName, mappings: filtered });
  });

  return result;
});

/** 数据源类型列表（用于筛选下拉） */
const availableTypes = computed(() => {
  if (!data.value?.mappings) return [];
  const types = new Set();
  data.value.mappings.forEach((m) => {
    if (m.source_type) types.add(m.source_type.toLowerCase());
  });
  return [...types];
});

/** 总映射数 */
const totalCount = computed(() => data.value?.mappings?.length ?? 0);

/** 筛选后的计数 */
const filteredCount = computed(() => {
  let count = 0;
  groupedMappings.value.forEach((g) => (count += g.mappings.length));
  return count;
});
</script>

<template>
  <div class="engineer-view">
    <!-- 加载状态 -->
    <div v-if="loading" class="ev-loading">
      <div class="loading-spinner"></div>
      <span>正在加载数据映射...</span>
    </div>

    <!-- 错误状态 -->
    <div v-else-if="error" class="ev-error">
      <p>数据加载失败：{{ error }}</p>
      <button class="btn-retry" @click="loadData">重试</button>
    </div>

    <!-- 正常内容 -->
    <div v-else-if="data" class="ev-content">
      <!-- 工具栏 -->
      <div class="ev-toolbar">
        <div class="ev-search">
          <svg
            viewBox="0 0 24 24"
            width="16"
            height="16"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
          >
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <input
            v-model="searchText"
            type="text"
            placeholder="搜索本体概念、表名、字段名..."
            class="ev-search-input"
          />
        </div>
        <div class="ev-filter" v-if="availableTypes.length > 1">
          <label class="ev-filter-label">数据源类型：</label>
          <select v-model="filterType" class="ev-filter-select">
            <option value="all">全部</option>
            <option v-for="t in availableTypes" :key="t" :value="t">
              {{ t === "dameng" ? "达梦" : t === "excel" ? "Excel" : t === "csv" ? "CSV" : t }}
            </option>
          </select>
        </div>
        <div class="ev-count">
          共 {{ filteredCount }} / {{ totalCount }} 条映射
        </div>
      </div>

      <!-- 映射表格 -->
      <div class="ev-table-wrap" v-if="groupedMappings.length">
        <table class="ev-table">
          <thead>
            <tr>
              <th class="col-concept">本体概念</th>
              <th class="col-source">数据源</th>
              <th class="col-table">表名</th>
              <th class="col-field">字段名</th>
              <th class="col-type">字段类型</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="group in groupedMappings" :key="group.domainId">
              <!-- 分组标题行 -->
              <tr class="ev-group-header">
                <td colspan="5">
                  <div class="ev-group-row">
                    <svg
                      viewBox="0 0 24 24"
                      width="14"
                      height="14"
                      fill="none"
                      stroke="currentColor"
                      stroke-width="2.5"
                      stroke-linecap="round"
                    >
                      <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
                    </svg>
                    <span class="ev-group-name">{{ group.domainName }}</span>
                    <span class="ev-group-meta">{{ group.mappings.length }} 条</span>
                  </div>
                </td>
              </tr>
              <!-- 数据行 -->
              <tr
                v-for="(m, mi) in group.mappings"
                :key="`${group.domainId}-${mi}`"
                class="ev-data-row"
              >
                <td>
                  <span class="ev-concept">{{
                    m.concept || m.ontology_node || "-"
                  }}</span>
                </td>
                <td>
                  <span
                    class="ev-source-tag"
                    :style="{
                      background: sourceTypeStyle(m.source_type).bg,
                      color: sourceTypeStyle(m.source_type).color,
                      borderColor: sourceTypeStyle(m.source_type).border,
                    }"
                  >
                    {{ m.source_name || "-" }}
                  </span>
                </td>
                <td>
                  <code class="ev-table-name">{{
                    m.table_name || "-"
                  }}</code>
                </td>
                <td>
                  <code class="ev-field-name">{{
                    m.field_name || "-"
                  }}</code>
                </td>
                <td>
                  <span class="ev-field-type">{{
                    m.field_type || m.data_type || "-"
                  }}</span>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>

      <!-- 空状态 -->
      <div v-else class="ev-empty">
        <svg
          viewBox="0 0 24 24"
          width="36"
          height="36"
          fill="none"
          stroke="currentColor"
          stroke-width="1.5"
          stroke-linecap="round"
        >
          <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
          <line x1="3" y1="9" x2="21" y2="9" />
          <line x1="9" y1="21" x2="9" y2="9" />
        </svg>
        <span v-if="searchText">没有匹配的映射记录</span>
        <span v-else>暂无数据映射信息</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* ======================== 容器 ======================== */

.engineer-view {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: #f8fafc;
}

/* ======================== 加载 / 错误 ======================== */

.ev-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 14px;
  padding: 60px 20px;
  color: #64748b;
  font-size: 14px;
  font-weight: 500;
}

.loading-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid #e2e8f0;
  border-top-color: #2563eb;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.ev-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 60px 20px;
  color: #94a3b8;
  font-size: 14px;
  font-weight: 500;
}

.btn-retry {
  padding: 8px 20px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  background: #ffffff;
  color: #334155;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}
.btn-retry:hover {
  background: #f1f5f9;
  border-color: #94a3b8;
}

/* ======================== 内容区 ======================== */

.ev-content {
  display: flex;
  flex-direction: column;
  flex: 1;
  overflow: hidden;
  padding: 20px 32px 0;
}

/* ======================== 工具栏 ======================== */

.ev-toolbar {
  display: flex;
  align-items: center;
  gap: 16px;
  padding-bottom: 16px;
  flex-shrink: 0;
  flex-wrap: wrap;
}

.ev-search {
  position: relative;
  flex: 1;
  min-width: 240px;
}

.ev-search svg {
  position: absolute;
  top: 50%;
  left: 12px;
  transform: translateY(-50%);
  color: #94a3b8;
  pointer-events: none;
}

.ev-search-input {
  width: 100%;
  height: 38px;
  padding: 0 16px 0 38px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 13.5px;
  color: #0f172a;
  background: #ffffff;
  outline: none;
  box-sizing: border-box;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.ev-search-input:focus {
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.08);
}

.ev-filter {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.ev-filter-label {
  font-size: 13px;
  font-weight: 500;
  color: #475569;
  white-space: nowrap;
}

.ev-filter-select {
  height: 38px;
  padding: 0 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 13px;
  color: #0f172a;
  background: #ffffff;
  outline: none;
  cursor: pointer;
  transition: border-color 0.2s ease;
}

.ev-filter-select:focus {
  border-color: #2563eb;
}

.ev-count {
  font-size: 12.5px;
  font-weight: 500;
  color: #64748b;
  white-space: nowrap;
  flex-shrink: 0;
}

/* ======================== 表格容器 ======================== */

.ev-table-wrap {
  flex: 1;
  overflow: auto;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background: #ffffff;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.ev-table-wrap::-webkit-scrollbar {
  width: 5px;
  height: 5px;
}
.ev-table-wrap::-webkit-scrollbar-track {
  background: transparent;
}
.ev-table-wrap::-webkit-scrollbar-thumb {
  background: #e2e8f0;
  border-radius: 3px;
}

/* ======================== 表格 ======================== */

.ev-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  table-layout: fixed;
}

.ev-table thead {
  position: sticky;
  top: 0;
  z-index: 2;
}

.ev-table th {
  text-align: left;
  padding: 12px 16px;
  font-size: 11.5px;
  font-weight: 700;
  color: #475569;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
  white-space: nowrap;
}

.col-concept {
  width: 20%;
}
.col-source {
  width: 18%;
}
.col-table {
  width: 22%;
}
.col-field {
  width: 22%;
}
.col-type {
  width: 18%;
}

/* ======================== 分组标题行 ======================== */

.ev-group-header {
  background: #fafbfc;
}

.ev-group-header td {
  padding: 10px 16px;
  border-bottom: 1px solid #e2e8f0;
}

.ev-group-row {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #64748b;
}

.ev-group-name {
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
}

.ev-group-meta {
  font-size: 11px;
  font-weight: 400;
  color: #94a3b8;
}

/* ======================== 数据行 ======================== */

.ev-data-row td {
  padding: 12px 16px;
  border-bottom: 1px solid #f1f5f9;
  color: #334155;
  vertical-align: middle;
}

.ev-data-row:last-child td {
  border-bottom: none;
}

.ev-data-row:hover {
  background: #fafbfc;
}

/* 分组内最后一行加底部间距 */
.ev-data-row + .ev-group-header td {
  border-top: 1px solid #e2e8f0;
}

/* ======================== 单元格内容 ======================== */

.ev-concept {
  font-weight: 600;
  color: #0f172a;
}

.ev-source-tag {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 6px;
  font-size: 11.5px;
  font-weight: 700;
  letter-spacing: 0.02em;
  border: 1px solid;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ev-table-name,
.ev-field-name {
  font-family: "SF Mono", "Cascadia Code", "Fira Code", ui-monospace,
    Consolas, monospace;
  font-size: 12px;
  color: #334155;
  background: #f8fafc;
  padding: 2px 6px;
  border-radius: 4px;
  word-break: break-all;
}

.ev-field-type {
  font-size: 11.5px;
  color: #64748b;
  font-weight: 500;
  font-family: "SF Mono", "Cascadia Code", ui-monospace, monospace;
}

/* ======================== 空状态 ======================== */

.ev-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 60px 20px;
  color: #94a3b8;
  background: #ffffff;
  border: 1.5px dashed #e2e8f0;
  border-radius: 12px;
  font-size: 13px;
  font-weight: 500;
  margin-top: 16px;
}

/* ======================== 响应式 ======================== */

@media (max-width: 900px) {
  .ev-content {
    padding: 16px 16px 0;
  }
  .ev-toolbar {
    flex-direction: column;
    align-items: stretch;
  }
  .ev-search {
    min-width: auto;
  }
}
</style>
