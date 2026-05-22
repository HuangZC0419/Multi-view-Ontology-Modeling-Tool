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

async function loadData() {
  loading.value = true;
  error.value = null;
  try {
    const resp = await fetch(
      `${API_BASE}/api/perspective/${props.projectId}/leader`
    );
    if (!resp.ok) {
      throw new Error(`HTTP ${resp.status}: ${await resp.text()}`);
    }
    data.value = await resp.json();
  } catch (e) {
    error.value = e.message;
    console.error("LeaderView: 加载数据失败:", e);
  } finally {
    loading.value = false;
  }
}

onMounted(loadData);
watch(() => props.projectId, loadData);

// 统计数据
const summaryCards = computed(() => {
  if (!data.value) return [];
  const s = data.value.summary || {};
  return [
    {
      label: "业务域数",
      value: s.domain_count ?? (data.value.domains?.length ?? 0),
      icon: "\u{1F4CA}",
      color: "#2563eb",
      bg: "#eff6ff",
      borderColor: "#bfdbfe",
    },
    {
      label: "本体概念数",
      value: s.node_count ?? 0,
      icon: "\u{1F9E9}",
      color: "#059669",
      bg: "#d1fae5",
      borderColor: "#a7f3d0",
    },
    {
      label: "数据源数",
      value: s.source_count ?? (data.value.data_sources?.length ?? 0),
      icon: "\u{1F4E6}",
      color: "#d97706",
      bg: "#fffbeb",
      borderColor: "#fcd34d",
    },
    {
      label: "推理关系数",
      value: s.inference_count ?? 0,
      icon: "\u{1F50D}",
      color: "#7c3aed",
      bg: "#f5f3ff",
      borderColor: "#c4b5fd",
    },
    {
      label: "数据源分布",
      value: formatSourceDist(s.source_distribution),
      icon: "\u{1F310}",
      color: "#0891b2",
      bg: "#ecfeff",
      borderColor: "#a5f3fc",
    },
  ];
});

/** 格式化数据源分布为简短字符串 */
function formatSourceDist(dist) {
  if (!dist) return "N/A";
  if (typeof dist === "string") return dist;
  const parts = [];
  if (dist.dameng != null) parts.push(`达梦${dist.dameng}`);
  if (dist.excel != null) parts.push(`Excel${dist.excel}`);
  if (dist.csv != null) parts.push(`CSV${dist.csv}`);
  return parts.length ? parts.join(" / ") : "N/A";
}

// 数据源类型标签颜色映射
const sourceTypeStyles = {
  dameng: { bg: "#f5f3ff", color: "#6d28d9", border: "#c4b5fd", label: "达梦" },
  excel: { bg: "#d1fae5", color: "#059669", border: "#a7f3d0", label: "Excel" },
  csv: { bg: "#fffbeb", color: "#d97706", border: "#fcd34d", label: "CSV" },
};

function sourceTypeStyle(type) {
  const key = (type || "").toLowerCase();
  return sourceTypeStyles[key] || { bg: "#f1f5f9", color: "#475569", border: "#e2e8f0", label: type };
}

// 业务域颜色序列
const domainColors = [
  { bar: "#ef4444", bg: "#fef2f2" },
  { bar: "#f59e0b", bg: "#fffbeb" },
  { bar: "#10b981", bg: "#d1fae5" },
  { bar: "#3b82f6", bg: "#eff6ff" },
  { bar: "#8b5cf6", bg: "#f5f3ff" },
];

/** 获取业务域对应的颜色 */
function domainColor(index) {
  return domainColors[index % domainColors.length];
}

// 覆盖度相关计算属性
const coverageItems = computed(() => {
  if (!data.value?.data_sources) return [];
  const sources = data.value.data_sources;
  const damengSources = sources.filter(
    (s) => (s.type || "").toLowerCase() === "dameng"
  );
  const fileSources = sources.filter(
    (s) => (s.type || "").toLowerCase() !== "dameng"
  );

  return [
    {
      label: "达梦数据库",
      count: damengSources.length,
      total: sources.length,
      pct: sources.length ? Math.round((damengSources.length / sources.length) * 100) : 0,
      color: "#7c3aed",
      bg: "#f5f3ff",
    },
    {
      label: "文件数据源",
      count: fileSources.length,
      total: sources.length,
      pct: sources.length ? Math.round((fileSources.length / sources.length) * 100) : 0,
      color: "#10b981",
      bg: "#d1fae5",
    },
  ];
});
</script>

<template>
  <div class="leader-view">
    <!-- 加载状态 -->
    <div v-if="loading" class="lv-loading">
      <div class="loading-spinner"></div>
      <span>正在加载宏观概览...</span>
    </div>

    <!-- 错误状态 -->
    <div v-else-if="error" class="lv-error">
      <p>数据加载失败：{{ error }}</p>
      <button class="btn-retry" @click="loadData">重试</button>
    </div>

    <!-- 正常内容 -->
    <div v-else-if="data" class="lv-content">
      <!-- 1. 统计卡片行 -->
      <section class="lv-section">
        <h3 class="lv-section-title">核心指标</h3>
        <div class="lv-summary-row">
          <div
            v-for="card in summaryCards"
            :key="card.label"
            class="lv-summary-card"
            :style="{
              borderLeftColor: card.color,
              background: card.bg,
            }"
          >
            <div class="sc-icon" :style="{ color: card.color }">
              {{ card.icon }}
            </div>
            <div class="sc-body">
              <span class="sc-value">{{ card.value }}</span>
              <span class="sc-label">{{ card.label }}</span>
            </div>
          </div>
        </div>
      </section>

      <!-- 2. 数据源全景表 -->
      <section class="lv-section">
        <h3 class="lv-section-title">数据源全景</h3>
        <div class="lv-table-wrap">
          <table class="lv-table" v-if="data.data_sources?.length">
            <thead>
              <tr>
                <th>数据源名称</th>
                <th>类型</th>
                <th>连接信息</th>
                <th>包含表</th>
                <th>支撑业务域</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="ds in data.data_sources" :key="ds.id || ds.name">
                <td>
                  <span class="ds-name">{{ ds.name }}</span>
                </td>
                <td>
                  <span
                    class="ds-type-tag"
                    :style="{
                      background: sourceTypeStyle(ds.type).bg,
                      color: sourceTypeStyle(ds.type).color,
                      borderColor: sourceTypeStyle(ds.type).border,
                    }"
                  >
                    {{ sourceTypeStyle(ds.type).label }}
                  </span>
                </td>
                <td>
                  <span class="ds-connection">{{
                    ds.connection_info || ds.host || "-"
                  }}</span>
                </td>
                <td>
                  <div class="ds-tables" v-if="ds.tables?.length">
                    <span
                      v-for="tbl in ds.tables.slice(0, 3)"
                      :key="tbl"
                      class="ds-table-chip"
                      >{{ tbl }}</span
                    >
                    <span
                      v-if="ds.tables.length > 3"
                      class="ds-table-more"
                      >+{{ ds.tables.length - 3 }} 更多</span
                    >
                  </div>
                  <span v-else class="ds-na">-</span>
                </td>
                <td>
                  <div
                    class="ds-domains"
                    v-if="data.source_domain_map?.[ds.id]?.length"
                  >
                    <span
                      v-for="(dom, di) in data.source_domain_map[ds.id]"
                      :key="dom"
                      class="ds-domain-chip"
                      :style="{
                        background: domainColor(di).bg,
                        color: domainColor(di).bar,
                      }"
                      >{{ dom }}</span
                    >
                  </div>
                  <span v-else class="ds-na">-</span>
                </td>
              </tr>
            </tbody>
          </table>
          <div v-else class="lv-empty">
            <span>暂无数据源信息</span>
          </div>
        </div>
      </section>

      <!-- 3. 数据源 -> 业务域关系图 -->
      <section class="lv-section">
        <h3 class="lv-section-title">数据源与业务域关系</h3>
        <div
          class="lv-sd-grid"
          v-if="data.domains?.length && data.data_sources?.length"
        >
          <div
            v-for="(domain, di) in data.domains"
            :key="domain.id || domain.name"
            class="lv-sd-domain-card"
            :style="{ borderLeftColor: domainColor(di).bar }"
          >
            <div class="sd-domain-header">
              <span class="sd-domain-name">{{ domain.name }}</span>
              <span
                class="sd-domain-badge"
                :style="{
                  background: domainColor(di).bg,
                  color: domainColor(di).bar,
                }"
              >
                {{ domain.concept_count ?? domain.nodes?.length ?? 0 }} 概念
              </span>
            </div>
            <div class="sd-sources">
              <span
                v-for="sourceId in domain.source_ids || domain.sources || []"
                :key="sourceId"
                class="sd-source-link"
              >
                <svg
                  viewBox="0 0 24 24"
                  width="10"
                  height="10"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                >
                  <path
                    d="M5 12h14M12 5l7 7-7 7"
                  />
                </svg>
                {{
                  data.data_sources.find((ds) => ds.id === sourceId)?.name ||
                  sourceId
                }}
              </span>
              <span
                v-if="
                  !domain.source_ids?.length && !domain.sources?.length
                "
                class="sd-source-empty"
                >暂无关联数据源</span
              >
            </div>
          </div>
        </div>
        <div v-else class="lv-empty">
          <span>暂无业务域与数据源关联信息</span>
        </div>
      </section>

      <!-- 4. 数据源覆盖度分析 -->
      <section class="lv-section">
        <h3 class="lv-section-title">数据源覆盖度分析</h3>
        <div class="lv-coverage">
          <div
            v-for="item in coverageItems"
            :key="item.label"
            class="lv-coverage-item"
          >
            <div class="cov-header">
              <span class="cov-label">{{ item.label }}</span>
              <span class="cov-stat">{{ item.pct }}%</span>
            </div>
            <div class="cov-bar-wrap">
              <div
                class="cov-bar"
                :style="{
                  width: item.pct + '%',
                  background: item.color,
                }"
              ></div>
            </div>
            <div class="cov-footer">
              <span
                >{{ item.count }} / {{ item.total }} 个数据源</span
              >
            </div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
/* ======================== 容器 ======================== */

.leader-view {
  flex: 1;
  overflow-y: auto;
  padding: 24px 32px;
  background: #f8fafc;
}

.leader-view::-webkit-scrollbar {
  width: 5px;
}
.leader-view::-webkit-scrollbar-track {
  background: transparent;
}
.leader-view::-webkit-scrollbar-thumb {
  background: #e2e8f0;
  border-radius: 3px;
}

/* ======================== 加载 / 错误 ======================== */

.lv-loading {
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

.lv-error {
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

.lv-content {
  display: flex;
  flex-direction: column;
  gap: 32px;
  max-width: 1200px;
}

/* ======================== 区块 ======================== */

.lv-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.lv-section-title {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
  padding-left: 8px;
  border-left: 3px solid #2563eb;
}

/* ======================== 统计卡片行 ======================== */

.lv-summary-row {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 16px;
}

.lv-summary-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 18px 20px;
  border-radius: 12px;
  border: 1px solid transparent;
  border-left-width: 4px;
  border-left-style: solid;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.lv-summary-card:hover {
  transform: translateY(-2px);
  box-shadow:
    0 4px 6px rgba(0, 0, 0, 0.05),
    0 2px 4px rgba(0, 0, 0, 0.04);
}

.sc-icon {
  font-size: 28px;
  flex-shrink: 0;
  line-height: 1;
}

.sc-body {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.sc-value {
  font-size: 26px;
  font-weight: 700;
  color: #0f172a;
  font-variant-numeric: tabular-nums;
  line-height: 1.2;
}

.sc-label {
  font-size: 12.5px;
  font-weight: 500;
  color: #64748b;
}

/* ======================== 数据源表格 ======================== */

.lv-table-wrap {
  overflow-x: auto;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background: #ffffff;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.lv-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.lv-table th {
  text-align: left;
  padding: 12px 16px;
  font-size: 12px;
  font-weight: 700;
  color: #475569;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
  white-space: nowrap;
}

.lv-table td {
  padding: 14px 16px;
  border-bottom: 1px solid #f1f5f9;
  color: #334155;
  vertical-align: middle;
}

.lv-table tbody tr:last-child td {
  border-bottom: none;
}

.lv-table tbody tr:hover {
  background: #fafbfc;
}

.ds-name {
  font-weight: 600;
  color: #0f172a;
}

.ds-type-tag {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 6px;
  font-size: 11.5px;
  font-weight: 700;
  letter-spacing: 0.02em;
  border: 1px solid;
}

.ds-connection {
  font-family: "SF Mono", "Cascadia Code", ui-monospace, monospace;
  font-size: 12px;
  color: #64748b;
  word-break: break-all;
}

.ds-tables {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: center;
}

.ds-table-chip {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  background: #f1f5f9;
  font-family: "SF Mono", "Cascadia Code", ui-monospace, monospace;
  font-size: 11.5px;
  color: #334155;
  font-weight: 500;
}

.ds-table-more {
  font-size: 11.5px;
  color: #94a3b8;
  font-weight: 500;
}

.ds-domains {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.ds-domain-chip {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11.5px;
  font-weight: 600;
}

.ds-na {
  color: #cbd5e1;
  font-size: 13px;
}

/* ======================== 业务域卡片 ======================== */

.lv-sd-grid {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.lv-sd-domain-card {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-left-width: 4px;
  border-left-style: solid;
  border-radius: 10px;
  padding: 16px 20px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
  transition: box-shadow 0.2s ease;
}

.lv-sd-domain-card:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.sd-domain-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.sd-domain-name {
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
}

.sd-domain-badge {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 6px;
  font-size: 11.5px;
  font-weight: 700;
}

.sd-sources {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.sd-source-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 6px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  font-size: 12px;
  font-weight: 500;
  color: #475569;
  transition: border-color 0.15s ease;
}

.sd-source-link:hover {
  border-color: #cbd5e1;
}

.sd-source-empty {
  font-size: 12px;
  color: #cbd5e1;
  font-style: italic;
}

/* ======================== 覆盖度分析 ======================== */

.lv-coverage {
  display: flex;
  flex-direction: column;
  gap: 20px;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.lv-coverage-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.cov-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.cov-label {
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
}

.cov-stat {
  font-size: 20px;
  font-weight: 700;
  color: #0f172a;
  font-variant-numeric: tabular-nums;
}

.cov-bar-wrap {
  height: 10px;
  background: #f1f5f9;
  border-radius: 5px;
  overflow: hidden;
}

.cov-bar {
  height: 100%;
  border-radius: 5px;
  transition: width 0.6s cubic-bezier(0.22, 0.61, 0.36, 1);
}

.cov-footer {
  font-size: 12px;
  color: #94a3b8;
  font-weight: 500;
}

/* ======================== 空状态 ======================== */

.lv-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  background: #ffffff;
  border: 1.5px dashed #e2e8f0;
  border-radius: 12px;
  color: #94a3b8;
  font-size: 13px;
  font-weight: 500;
}

/* ======================== 响应式 ======================== */

@media (max-width: 900px) {
  .leader-view {
    padding: 16px;
  }
  .lv-summary-row {
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  }
}
</style>
