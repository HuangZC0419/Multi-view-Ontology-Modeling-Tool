<script setup>
import { ref, onMounted, onUnmounted, watch, computed } from "vue";

const props = defineProps({
  projectId: { type: String, required: true },
});

const API_BASE = import.meta.env.VITE_API_BASE || "";

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

const sourceTypeStyleMap = {
  dameng: { label: "达梦", color: "#7c3aed", fill: "#7c3aed", bg: "#f5f3ff", border: "#c4b5fd" },
  excel: { label: "Excel", color: "#059669", fill: "#059669", bg: "#ecfdf5", border: "#a7f3d0" },
  csv: { label: "CSV", color: "#d97706", fill: "#ea580c", bg: "#fff7ed", border: "#fdba74" },
  manual: { label: "人工维护", color: "#64748b", fill: "#64748b", bg: "#f1f5f9", border: "#cbd5e1" },
};

function sourceTypeStyle(type) {
  const key = (type || "").toLowerCase();
  return sourceTypeStyleMap[key] || { label: type, color: "#64748b", fill: "#64748b", bg: "#f8fafc", border: "#e2e8f0" };
}

const summaryCards = computed(() => {
  if (!data.value) return [];
  const s = data.value.summary || {};
  return [
    {
      key: "nodes",
      label: "本体概念数",
      value: s.node_count ?? 0,
      icon: "nodes",
      color: "#059669",
      barColor: "#059669",
      bg: "#ecfdf5",
    },
    {
      key: "inferences",
      label: "推理关系数",
      value: s.inference_count ?? 0,
      icon: "inferences",
      color: "#7c3aed",
      barColor: "#7c3aed",
      bg: "#f5f3ff",
    },
    {
      key: "sources",
      label: "数据底座数",
      value: s.source_count ?? (data.value.data_sources?.length ?? 0),
      icon: "sources",
      color: "#ea580c",
      barColor: "#ea580c",
      bg: "#fff7ed",
    },
  ];
});

const sourceGroups = computed(() => {
  if (!data.value) return [];
  const sources = data.value.data_sources || [];
  const groups = [
    { type: "dameng", sources: [] },
    { type: "excel", sources: [] },
    { type: "csv", sources: [] },
  ];
  for (const src of sources) {
    const type = (src.type || "").toLowerCase();
    const group = groups.find((g) => g.type === type);
    if (group) {
      group.sources.push(src);
    }
  }
  const result = groups.filter((g) => g.sources.length > 0);

  const manualNodeCount = data.value.summary?.manual_node_count || 0;
  const manualEdgeCount = data.value.summary?.manual_edge_count || 0;
  if (manualNodeCount > 0 || manualEdgeCount > 0) {
    result.push({
      type: "manual",
      sources: [
        {
          id: "manual-src",
          name: "人工维护数据",
          type: "manual",
          isManual: true,
          covered_nodes: manualNodeCount,
          edges_count: manualEdgeCount
        }
      ]
    });
  }

  return result;
});

const COLLAPSE_LIMIT = 8;
const expandedSources = ref(new Set());

function toggleExpand(sourceId) {
  const next = new Set(expandedSources.value);
  if (next.has(sourceId)) {
    next.delete(sourceId);
  } else {
    next.add(sourceId);
  }
  expandedSources.value = next;
}

// ========== 响应式并排-树形布局 ==========
const svgContainer = ref(null);
const containerWidth = ref(700);

let resizeObserver = null;
onMounted(() => {
  if (svgContainer.value) {
    resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const w = entry.contentRect.width;
        if (w > 0) containerWidth.value = w;
      }
    });
    resizeObserver.observe(svgContainer.value);
  }
});

onUnmounted(() => {
  if (resizeObserver) resizeObserver.disconnect();
});

watch(svgContainer, (el) => {
  if (el && !resizeObserver) {
    resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const w = entry.contentRect.width;
        if (w > 0) containerWidth.value = w;
      }
    });
    resizeObserver.observe(el);
  }
});

const layoutParams = computed(() => {
  const W = containerWidth.value;
  const padding = 24;

  const sourceW = Math.max(120, Math.floor(W * 0.15));
  const sourceH = 48;

  const chipGapX = 12;
  const chipGapY = 16;
  const minChipW = 90;
  const maxChipW = 160;

  const chipH = 36;
  const rowH = chipH + chipGapY;

  // 上下层级之间的垂直间距
  const verticalGap = 40;
  // 每个数据源组之间的水平间距
  const groupGapX = 32;
  
  // 多行折叠高度
  const collapseLimit = 6;

  const sourceFontSize = Math.max(12, Math.min(14, Math.floor(W / 60)));
  const chipFontSize = Math.max(11, Math.min(13, Math.floor(W / 70)));
  const nameMaxLen = Math.floor(maxChipW / (chipFontSize * 0.65));

  return {
    padding, sourceW, sourceH,
    chipGapX, chipGapY, minChipW, maxChipW, chipH, rowH,
    verticalGap, groupGapX, collapseLimit, sourceFontSize, chipFontSize, nameMaxLen,
    W,
  };
});

function shortName(name, maxLen = 11) {
  if (!name) return "";
  return name.length > maxLen ? name.slice(0, maxLen - 1) + "…" : name;
}

const svgLayout = computed(() => {
  if (!data.value?.data_sources?.length) return { groups: [], totalHeight: 0, totalWidth: 0 };

  const sources = data.value.data_sources;
  const manualNames = data.value?.summary?.manual_node_names || [];
  if (!sources.length && !manualNames.length) return { groups: [], totalHeight: 0, totalWidth: 0 };

  const LP = layoutParams.value;
  const groups = [];
  
  // 1. 准备原始分组数据
  const rawGroups = [];
  for (const src of sources) {
    rawGroups.push({ id: src.id, name: src.name, type: (src.type || "").toLowerCase(), names: src.covered_ontology_names || [] });
  }
  if (manualNames.length > 0) {
    rawGroups.push({ id: "src-manual", name: "人工维护", type: "manual", names: manualNames });
  }
  
  const groupCount = rawGroups.length;
  // 计算平分后每个组可以分到的最大宽度
  const availableWidth = LP.W - LP.padding * 2;
  // 每组的理想宽度 (如果宽度够的话)
  let groupColWidth = Math.max(
    LP.sourceW,
    Math.floor((availableWidth - (groupCount - 1) * LP.groupGapX) / groupCount)
  );
  
  // 如果分不到足够的宽度，我们需要允许 svg 出现水平滚动，确保每个组有合理的最小宽度
  // 每个组至少要能放下两个 chip 
  const minGroupColWidth = Math.max(LP.sourceW, LP.minChipW * 2 + LP.chipGapX);
  groupColWidth = Math.max(groupColWidth, minGroupColWidth);
  
  const totalContentWidth = groupCount * groupColWidth + (groupCount - 1) * LP.groupGapX;
  // 实际 SVG 的宽度（如果大于容器宽度则出横向滚动条）
  const svgWidth = Math.max(LP.W, totalContentWidth + LP.padding * 2);

  let startX = LP.padding + Math.max(0, (svgWidth - LP.padding * 2 - totalContentWidth) / 2);
  let maxBlockH = LP.sourceH;

  for (let gIdx = 0; gIdx < groupCount; gIdx++) {
    const { id, name, type, names } = rawGroups[gIdx];
    const fullCount = names.length;
    const isExpanded = expandedSources.value.has(id);
    const showAll = isExpanded || fullCount <= LP.collapseLimit;
    const visibleCount = showAll ? fullCount : LP.collapseLimit;
    const visibleNames = showAll ? names : names.slice(0, LP.collapseLimit);

    // 确定此组内部布局参数
    // 当前组的可用区域
    const groupX = startX + gIdx * (groupColWidth + LP.groupGapX);
    
    // 当前组一排能放几个 chip
    const cols = Math.max(1, Math.floor((groupColWidth + LP.chipGapX) / (LP.minChipW + LP.chipGapX)));
    const actualChipW = Math.min(LP.maxChipW, Math.max(LP.minChipW, Math.floor((groupColWidth - (cols - 1) * LP.chipGapX) / cols)));
    const actualColW = actualChipW + LP.chipGapX;
    
    // 数据源卡片居中
    const sourceX = groupX + (groupColWidth - LP.sourceW) / 2;
    const sourceY = LP.padding;
    const chipStartY = sourceY + LP.sourceH + LP.verticalGap;

    const chips = [];
    const rows = fullCount === 0 ? 0 : Math.ceil(visibleCount / cols);
    
    for (let i = 0; i < visibleCount; i++) {
      const row = Math.floor(i / cols);
      const itemsInRow = row === rows - 1 ? visibleCount - row * cols : cols;
      const rowWidth = itemsInRow * actualChipW + (itemsInRow - 1) * LP.chipGapX;
      const rowStartX = groupX + (groupColWidth - rowWidth) / 2;
      const colInRow = i % cols;
      
      chips.push({
        name: visibleNames[i],
        x: rowStartX + colInRow * actualColW,
        y: chipStartY + row * LP.rowH,
        w: actualChipW,
      });
    }

    const needsButton = fullCount > LP.collapseLimit;
    let buttonX = 0;
    let buttonY = 0;
    let blockH = LP.sourceH;

    if (fullCount > 0) {
       blockH += LP.verticalGap + rows * LP.rowH;
    }

    if (needsButton && !isExpanded) {
      buttonX = groupX + (groupColWidth - actualChipW) / 2;
      buttonY = chipStartY + rows * LP.rowH;
      blockH += LP.chipH + LP.chipGapY;
    }

    maxBlockH = Math.max(maxBlockH, blockH);

    groups.push({
      id, name, type,
      sourceX, sourceY, sourceW: LP.sourceW, sourceH: LP.sourceH,
      chips, rows, hasContent: fullCount > 0,
      needsButton, hiddenCount: fullCount - LP.collapseLimit, isExpanded,
      buttonX, buttonY, blockH,
      sourceMidX: sourceX + LP.sourceW / 2,
      sourceMidY: sourceY + LP.sourceH,
      actualChipW
    });
  }

  const totalHeight = LP.padding * 2 + maxBlockH;
  return { groups, totalHeight, totalWidth: svgWidth };
});

function chipPathX(chip) {
  return chip.x + chip.w / 2;
}

function getVerticalCurve(x1, y1, x2, y2) {
  const dy = Math.abs(y2 - y1);
  const cy = y1 + dy * 0.4;
  return `M ${x1} ${y1} C ${x1} ${cy}, ${x2} ${y2 - dy * 0.4}, ${x2} ${y2}`;
}
</script>

<template>
  <div class="leader-view">
    <div v-if="loading" class="lv-loading">
      <div class="loading-spinner"></div>
      <span>正在加载宏观概览...</span>
    </div>

    <div v-else-if="error" class="lv-error">
      <div class="lv-error-icon">
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10"/>
          <line x1="12" y1="8" x2="12" y2="12"/>
          <line x1="12" y1="16" x2="12.01" y2="16"/>
        </svg>
      </div>
      <p>数据加载失败：{{ error }}</p>
      <button class="btn-retry" @click="loadData">重试</button>
    </div>

    <div v-else-if="data" class="lv-content">
      <section class="lv-section">
        <div class="lv-section-header">
          <span class="section-bar"></span>
          <span class="section-title">核心指标</span>
        </div>
        <div class="lv-summary-grid">
          <div
            v-for="card in summaryCards"
            :key="card.key"
            class="lv-summary-card"
            :style="{ borderLeftColor: card.barColor }"
          >
            <div class="sc-icon-wrap">
              <svg v-if="card.icon === 'nodes'" width="28" height="28" viewBox="0 0 24 24" fill="none">
                <circle cx="7" cy="7" r="3.5" :stroke="card.color" stroke-width="1.8"/>
                <circle cx="17" cy="7" r="3.5" :stroke="card.color" stroke-width="1.8"/>
                <circle cx="12" cy="18" r="3.5" :stroke="card.color" stroke-width="1.8"/>
                <line x1="10" y1="8.5" x2="10.5" y2="16" :stroke="card.color" stroke-width="1.2" opacity="0.5"/>
                <line x1="14" y1="8.5" x2="13.5" y2="16" :stroke="card.color" stroke-width="1.2" opacity="0.5"/>
              </svg>
              <svg v-else-if="card.icon === 'inferences'" width="28" height="28" viewBox="0 0 24 24" fill="none">
                <circle cx="5" cy="12" r="3" :stroke="card.color" stroke-width="1.8"/>
                <circle cx="19" cy="12" r="3" :stroke="card.color" stroke-width="1.8"/>
                <path d="M8 12 L16 12" :stroke="card.color" stroke-width="1.6" stroke-dasharray="3 2"/>
                <path d="M5 12 L5 19 L13 19" :stroke="card.color" stroke-width="1.2" opacity="0.4"/>
              </svg>
              <svg v-else-if="card.icon === 'sources'" width="28" height="28" viewBox="0 0 24 24" fill="none">
                <ellipse cx="12" cy="5" rx="9" ry="3.5" :stroke="card.color" stroke-width="1.8"/>
                <path d="M3 5 L3 19 A9 3.5 0 0 0 21 19 L21 5" :stroke="card.color" stroke-width="1.8" fill="none"/>
                <ellipse cx="12" cy="12" rx="9" ry="3.5" :stroke="card.color" stroke-width="1" opacity="0.5"/>
              </svg>
            </div>
            <div class="sc-body">
              <span class="sc-value">{{ card.value }}</span>
              <span class="sc-label">{{ card.label }}</span>
            </div>
          </div>
        </div>
      </section>

      <section class="lv-section">
        <div class="lv-section-header">
          <span class="section-bar"></span>
          <span class="section-title">数据底座</span>
        </div>
        <div v-if="sourceGroups.length" class="lv-source-groups">
          <div
            v-for="group in sourceGroups"
            :key="group.type"
            class="lv-source-group"
          >
            <div class="lsg-header">
              <span
                class="lsg-type-pill"
                :style="{
                  background: sourceTypeStyle(group.type).color,
                  color: '#ffffff',
                }"
              >
                {{ sourceTypeStyle(group.type).label }}
              </span>
              <span class="lsg-count">{{ group.sources.length }} 个数据源</span>
            </div>
            <div class="lsg-cards">
              <div
                v-for="src in group.sources"
                :key="src.id"
                class="lsg-card"
              >
                <div class="lsgc-top">
                  <span class="lsgc-name">{{ src.name }}</span>
                  <span
                    class="lsgc-type-tag"
                    :style="{
                      background: sourceTypeStyle(group.type).bg,
                      color: sourceTypeStyle(group.type).color,
                      borderColor: sourceTypeStyle(group.type).border,
                    }"
                  >{{ sourceTypeStyle(group.type).label }}</span>
                </div>
                <div class="lsgc-stats">
                  <template v-if="src.isManual">
                    <div class="lsgc-stat">
                      <span class="lsgc-stat-val">{{ src.covered_nodes ?? 0 }}</span>
                      <span class="lsgc-stat-label">个本体</span>
                    </div>
                    <div class="lsgc-stat-divider"></div>
                    <div class="lsgc-stat">
                      <span class="lsgc-stat-val">{{ src.edges_count ?? 0 }}</span>
                      <span class="lsgc-stat-label">条推理</span>
                    </div>
                  </template>
                  <template v-else>
                    <div class="lsgc-stat">
                      <span class="lsgc-stat-val">{{ src.tables?.length ?? 0 }}</span>
                      <span class="lsgc-stat-label">张表</span>
                    </div>
                    <div class="lsgc-stat-divider"></div>
                    <div class="lsgc-stat">
                      <span class="lsgc-stat-val">{{ src.covered_nodes ?? 0 }}</span>
                      <span class="lsgc-stat-label">个本体</span>
                    </div>
                  </template>
                </div>
                <div v-if="src.tables?.length" class="lsgc-table-chips">
                  <span
                    v-for="tbl in src.tables"
                    :key="tbl"
                    class="lsgc-chip"
                  >{{ tbl }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div v-else class="lv-empty">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#cbd5e1" stroke-width="1.5" stroke-linecap="round">
            <ellipse cx="12" cy="5" rx="9" ry="3"/>
            <path d="M3 5 L3 19 A9 3 0 0 0 21 19 L21 5"/>
          </svg>
          <span>暂无数据源信息</span>
        </div>
      </section>

      <section class="lv-section">
        <div class="lv-section-header">
          <span class="section-bar"></span>
          <span class="section-title">数据底座与本体支撑关系</span>
          <div class="lv-legend-items">
            <span class="lv-legend-item">
              <span class="lv-legend-dot" style="background:#7c3aed"></span>达梦
            </span>
            <span class="lv-legend-item">
              <span class="lv-legend-dot" style="background:#059669"></span>Excel
            </span>
            <span class="lv-legend-item">
              <span class="lv-legend-dot" style="background:#ea580c"></span>CSV
            </span>
            <span v-if="data.summary.manual_node_names?.length" class="lv-legend-item">
              <span class="lv-legend-dot" style="background:#64748b"></span>人工维护
            </span>
          </div>
        </div>
        <div
          v-if="svgLayout.groups.length"
          class="lv-svg-wrap"
          ref="svgContainer"
        >
          <svg
            :width="svgLayout.totalWidth"
            :height="svgLayout.totalHeight"
            :viewBox="`0 0 ${svgLayout.totalWidth} ${svgLayout.totalHeight}`"
            class="lv-svg"
            xmlns="http://www.w3.org/2000/svg"
          >
            <defs>
              <filter id="card-shadow" x="-10%" y="-10%" width="120%" height="120%">
                <feDropShadow dx="0" dy="0.5" stdDeviation="1" flood-color="#000" flood-opacity="0.06"/>
              </filter>
              <filter id="chip-shadow" x="-20%" y="-20%" width="140%" height="140%">
                <feDropShadow dx="0" dy="1" stdDeviation="1.5" flood-color="#0f172a" flood-opacity="0.05"/>
              </filter>
            </defs>

            <g
              v-for="g in svgLayout.groups"
              :key="g.id"
            >
              <path
                v-for="chip in g.chips"
                :key="'p-' + chip.name"
                :d="getVerticalCurve(g.sourceMidX, g.sourceMidY, chipPathX(chip), chip.y)"
                fill="none"
                :stroke="sourceTypeStyle(g.type).color"
                stroke-opacity="0.35"
                stroke-width="1.5"
                class="animated-path"
              />

              <rect
                :x="g.sourceX"
                :y="g.sourceY"
                :width="g.sourceW"
                :height="g.sourceH"
                :rx="8"
                :fill="sourceTypeStyle(g.type).fill"
                filter="url(#card-shadow)"
              />
              <text
                :x="g.sourceX + g.sourceW / 2"
                :y="g.sourceY + g.sourceH / 2 + 1"
                text-anchor="middle"
                dominant-baseline="central"
                fill="#ffffff"
                :font-size="layoutParams.sourceFontSize + 1"
                font-weight="800"
                letter-spacing="0.04em"
              >{{ shortName(g.name, layoutParams.nameMaxLen) }}</text>

              <g v-for="chip in g.chips" :key="`c-${chip.name}`">
                <rect
                  :x="chip.x"
                  :y="chip.y"
                  :width="g.actualChipW"
                  :height="layoutParams.chipH"
                  :rx="layoutParams.chipH / 2"
                  fill="#ffffff"
                  stroke="#e2e8f0"
                  stroke-width="1"
                  filter="url(#chip-shadow)"
                />
                <text
                  :x="chip.x + g.actualChipW / 2"
                  :y="chip.y + layoutParams.chipH / 2 + 1"
                  text-anchor="middle"
                  dominant-baseline="central"
                  fill="#1e293b"
                  :font-size="layoutParams.chipFontSize"
                  font-weight="700"
                >{{ shortName(chip.name, layoutParams.nameMaxLen) }}</text>
              </g>

              <g v-if="g.needsButton" class="svg-expand-btn" @click="toggleExpand(g.id)">
                <rect
                  :x="g.buttonX"
                  :y="g.buttonY"
                  :width="g.actualChipW"
                  :height="layoutParams.chipH"
                  :rx="layoutParams.chipH / 2"
                  fill="#f8fafc"
                  stroke="#94a3b8"
                  stroke-width="1.5"
                  stroke-dasharray="4 4"
                />
                <text
                  :x="g.buttonX + g.actualChipW / 2"
                  :y="g.buttonY + layoutParams.chipH / 2 + 1"
                  text-anchor="middle"
                  dominant-baseline="central"
                  fill="#475569"
                  :font-size="layoutParams.chipFontSize"
                  font-weight="700"
                >{{ g.isExpanded ? '收起' : `+${g.hiddenCount} 个` }}</text>
              </g>

              <text
                v-if="!g.hasContent"
                :x="g.sourceMidX"
                :y="g.sourceY + g.sourceH + layoutParams.verticalGap / 2"
                text-anchor="middle"
                dominant-baseline="central"
                fill="#94a3b8"
                font-size="11"
                font-style="italic"
              >暂无关联本体</text>
            </g>
          </svg>
        </div>
        <div v-else class="lv-empty">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#cbd5e1" stroke-width="1.5" stroke-linecap="round">
            <rect x="3" y="3" width="18" height="18" rx="2"/>
            <line x1="3" y1="9" x2="21" y2="9"/>
            <line x1="9" y1="21" x2="9" y2="9"/>
          </svg>
          <span>暂无数据底座与本体关联信息</span>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.leader-view {
  flex: 1;
  overflow-y: auto;
  padding: 20px 28px;
  background: #f8fafc;
  min-width: 0;
}

.leader-view::-webkit-scrollbar {
  width: 6px;
}
.leader-view::-webkit-scrollbar-track {
  background: transparent;
}
.leader-view::-webkit-scrollbar-thumb {
  background: #e2e8f0;
  border-radius: 3px;
}
.leader-view::-webkit-scrollbar-thumb:hover {
  background: #cbd5e1;
}

.lv-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  padding: 80px 20px;
  color: #64748b;
  font-size: 14px;
  font-weight: 500;
}

.loading-spinner {
  width: 34px;
  height: 34px;
  border: 3px solid #e2e8f0;
  border-top-color: #f97316;
  border-radius: 50%;
  animation: spin 0.75s linear infinite;
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
  padding: 80px 20px;
  color: #94a3b8;
  font-size: 14px;
  font-weight: 500;
}

.lv-error p {
  margin: 0;
  color: #64748b;
  font-weight: 600;
}

.lv-error-icon {
  margin-bottom: 4px;
}

.btn-retry {
  padding: 8px 24px;
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

.lv-content {
  display: flex;
  flex-direction: column;
  gap: 24px;
  width: 100%;
}

.lv-section {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.lv-section-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-bottom: 0;
}

.section-bar {
  display: inline-block;
  width: 4px;
  height: 20px;
  background: #f97316;
  border-radius: 2px;
  flex-shrink: 0;
}

.section-title {
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
}

.lv-legend-items {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-left: auto;
}

.lv-legend-item {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  font-weight: 500;
  color: #94a3b8;
}

.lv-legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 2px;
  flex-shrink: 0;
}

.lv-summary-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.lv-summary-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 22px 24px;
  background: #ffffff;
  border-radius: 12px;
  border: 1px solid #f1f5f9;
  border-left: 3px solid;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.lv-summary-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06), 0 1px 3px rgba(0, 0, 0, 0.04);
}

.sc-icon-wrap {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  border-radius: 10px;
  background: #f8fafc;
}

.sc-body {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.sc-value {
  font-size: 28px;
  font-weight: 800;
  color: #0f172a;
  font-variant-numeric: tabular-nums;
  line-height: 1.15;
  letter-spacing: -0.01em;
}

.sc-label {
  font-size: 11.5px;
  font-weight: 600;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.lv-source-groups {
  display: flex;
  flex-direction: row;
  flex-wrap: wrap;
  gap: 16px;
  align-items: stretch;
}

.lv-source-group {
  display: flex;
  flex-direction: column;
  gap: 14px;
  flex: 1;
  min-width: 200px;
}

.lsg-header {
  display: flex;
  align-items: center;
  gap: 10px;
}

.lsg-type-pill {
  display: inline-flex;
  align-items: center;
  padding: 4px 14px;
  border-radius: 100px;
  font-size: 11.5px;
  font-weight: 700;
  letter-spacing: 0.03em;
}

.lsg-count {
  font-size: 12.5px;
  font-weight: 500;
  color: #94a3b8;
}

.lsg-cards {
  display: flex;
  flex-direction: column;
  gap: 12px;
  flex: 1;
}

.lsg-card {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 18px 20px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
  display: flex;
  flex-direction: column;
  gap: 14px;
  flex: 1;
  transition: box-shadow 0.2s ease, border-color 0.2s ease;
}

.lsg-card:hover {
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.06);
  border-color: #cbd5e1;
}

.lsgc-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.lsgc-name {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
  font-family: "SF Mono", "Cascadia Code", ui-monospace, monospace;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.lsgc-type-tag {
  display: inline-flex;
  align-items: center;
  padding: 2px 10px;
  border-radius: 100px;
  font-size: 10.5px;
  font-weight: 700;
  border: 1px solid;
  letter-spacing: 0.03em;
  flex-shrink: 0;
}

.lsgc-stats {
  display: flex;
  align-items: center;
  gap: 14px;
}

.lsgc-stat {
  display: flex;
  align-items: baseline;
  gap: 3px;
}

.lsgc-stat-val {
  font-size: 17px;
  font-weight: 800;
  color: #0f172a;
  font-variant-numeric: tabular-nums;
  line-height: 1;
}

.lsgc-stat-label {
  font-size: 11px;
  font-weight: 500;
  color: #94a3b8;
}

.lsgc-stat-divider {
  width: 1px;
  height: 14px;
  background: #e2e8f0;
  flex-shrink: 0;
}

.lsgc-table-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: auto;
}

.lsgc-chip {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 5px;
  background: #f1f5f9;
  font-family: "SF Mono", "Cascadia Code", ui-monospace, monospace;
  font-size: 11px;
  color: #475569;
  font-weight: 500;
  border: 1px solid #e8ecf1;
  line-height: 1.4;
}

.lv-svg-wrap {
  border: 1px solid #e8ecf1;
  border-radius: 12px;
  background: #ffffff;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
  overflow-x: auto;
  overflow-y: hidden;
  padding: 14px 14px 0 14px;
  width: 100%;
  box-sizing: border-box;
}

.lv-svg-wrap::-webkit-scrollbar {
  height: 6px;
}
.lv-svg-wrap::-webkit-scrollbar-track {
  background: transparent;
}
.lv-svg-wrap::-webkit-scrollbar-thumb {
  background: #e2e8f0;
  border-radius: 3px;
}

.lv-svg {
  display: block;
  /* width and height are defined inline to prevent scaling up */
  margin: 0 auto;
}

.svg-expand-btn {
  cursor: pointer;
}

.svg-expand-btn:hover rect {
  fill: #e2e8f0;
  stroke: #94a3b8;
}

.svg-expand-btn:hover text {
  fill: #334155;
}

.lv-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 48px 20px;
  background: #ffffff;
  border: 1.5px dashed #e2e8f0;
  border-radius: 12px;
  color: #94a3b8;
  font-size: 13px;
  font-weight: 500;
}

.lv-manual-hint {
  font-size: 12px;
  color: #94a3b8;
  padding-top: 10px;
  margin-top: 2px;
  border-top: 1px solid #e8ecf1;
}

@media (max-width: 960px) {
  .lv-summary-grid {
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
    gap: 12px;
  }

  .lv-summary-card {
    padding: 16px 18px;
    gap: 12px;
  }

  .sc-value {
    font-size: 24px;
  }

  .lv-legend-items {
    display: none;
  }
}

@media (max-width: 768px) {
  .leader-view {
    padding: 16px;
  }

  .lv-summary-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  /* removed .lsg-cards specific grid override since it's flex column now */
}

</style>
