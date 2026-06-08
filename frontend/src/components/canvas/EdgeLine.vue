<script setup>
/**
 * EdgeLine.vue - 本体关系连线组件
 * 渲染 SVG 贝塞尔曲线 / 正交折线路径，包含箭头标记和关系标签
 */

defineProps({
  /** 预计算的边视图数据，包含 path / labelX / labelY / displayRelation / kind / characteristics / id */
  edge: {
    type: Object,
    required: true
  },
  /** 是否选中 */
  selected: {
    type: Boolean,
    default: false
  },
  /** 贝叶斯分析高亮 */
  highlighted: {
    type: Boolean,
    default: false
  },
  /** 贝叶斯分析时非关注边的弱化 */
  dimmed: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['click']);

function onClick() {
  emit('click');
}
</script>

<template>
  <g
    class="edge-group"
    :class="{ selected, highlighted, dimmed }"
    @click.stop="onClick"
  >
    <!-- 宽的透明路径方便点击 -->
    <path
      :d="edge.path"
      class="edge-click-area"
      fill="none"
      stroke="transparent"
      stroke-width="20"
    />
    <!-- 实际可见连线 -->
    <path
      :d="edge.path"
      :class="['edge-line', edge.kind, {
        symmetric: edge.characteristics?.includes('symmetric'),
        transitive: edge.characteristics?.includes('transitive')
      }]"
      :marker-end="edge.characteristics?.includes('symmetric')
        ? 'url(#arrow-symmetric)'
        : `url(#arrow${edge.kind === 'parent-child' ? '-parent' : (selected ? '-selected' : '')})`"
      :marker-start="edge.characteristics?.includes('symmetric')
        ? 'url(#arrow-reverse-symmetric)'
        : ''"
      fill="none"
    />
    <!-- 标签背景 -->
    <rect
      :x="edge.labelX - 42"
      :y="edge.labelY - 13"
      width="84"
      height="26"
      rx="13"
      class="edge-label-bg"
    />
    <!-- 标签文字 -->
    <text
      :x="edge.labelX"
      :y="edge.labelY + 4.5"
      class="edge-label"
    >
      {{ edge.displayRelation }}
    </text>
  </g>
</template>

<style scoped>
/* ======================== 边线样式 ======================== */

.edge-line {
  stroke: #94a3b8;
  stroke-width: 2.5px;
  transition:
    stroke 0.25s cubic-bezier(0.4, 0, 0.2, 1),
    stroke-width 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  fill: none;
}

/* 普通关系线 */
.edge-line.relation {
  stroke: #6366f1;
  stroke-dasharray: 8 4;
  animation: dash-flow 2s linear infinite;
}

@keyframes dash-flow {
  to {
    stroke-dashoffset: -24;
  }
}

/* 传递特性 */
.edge-line.relation.transitive {
  stroke-width: 4px;
  stroke-dasharray: 3 5;
  stroke: #8b5cf6;
}

/* 对称特性 */
.edge-line.relation.symmetric {
  stroke: #a78bfa;
  stroke-dasharray: none;
}

/* 父子关系线 */
.edge-line.parent-child {
  stroke: #10b981;
  stroke-width: 2.5px;
}

/* 选中态 */
.edge-group.selected .edge-line {
  stroke: #2563eb;
  stroke-width: 4px;
}

/* 交互区 */
.edge-group {
  pointer-events: all;
  cursor: pointer;
  transition: filter 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.edge-click-area {
  cursor: pointer;
  pointer-events: stroke;
}

/* hover 高亮 */
.edge-group:hover .edge-line {
  stroke-width: 4px;
  filter: brightness(1.1) saturate(1.2);
}

.edge-group:hover .edge-line.relation {
  stroke: #4f46e5;
}

.edge-group:hover .edge-line.parent-child {
  stroke: #059669;
}

/* 标签背景 */
.edge-label-bg {
  fill: rgba(255, 255, 255, 0.9);
  stroke: #e2e8f0;
  stroke-width: 1px;
  filter: drop-shadow(0 1px 2px rgba(0, 0, 0, 0.06));
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

.edge-group:hover .edge-label-bg {
  fill: #ffffff;
  stroke: #cbd5e1;
  filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.1));
}

/* 标签文字 */
.edge-label,
.edge-label-bg {
  pointer-events: all;
  cursor: pointer;
}

.edge-label {
  font-size: 11px;
  font-weight: 700;
  fill: #475569;
  text-anchor: middle;
  dominant-baseline: middle;
  transition: fill 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  letter-spacing: 0.02em;
}

.edge-group:hover .edge-label {
  fill: #1e293b;
}

/* 贝叶斯分析高亮联动 */
.edge-group.dimmed .edge-line {
  opacity: 0.15;
  transition: opacity 0.35s ease;
}

.edge-group.highlighted .edge-line {
  opacity: 1;
  stroke-width: 3.5;
  filter: drop-shadow(0 0 4px rgba(30, 64, 175, 0.4));
}

.edge-group.highlighted .edge-label-bg {
  fill: #1E40AF;
}

.edge-group.highlighted .edge-label {
  fill: #FFFFFF;
  font-weight: 700;
}
</style>
