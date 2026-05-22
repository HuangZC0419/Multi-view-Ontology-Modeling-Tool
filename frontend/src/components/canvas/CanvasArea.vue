<script setup>
/**
 * CanvasArea.vue - 画布主容器组件
 *
 * 包含 SVG 画布渲染区域、缩放/平移交互、节点卡片和边线的布局与渲染。
 * 通过 props 接收所有状态数据，通过 emit 向父组件发送交互事件。
 */

import { computed } from 'vue';
import NodeCard from './NodeCard.vue';
import EdgeLine from './EdgeLine.vue';

/* ==================================================================
 * Props
 * ================================================================== */

const props = defineProps({
  /** 所有节点数据 */
  nodes: { type: Array, default: () => [] },
  /** 所有边数据 */
  edges: { type: Array, default: () => [] },
  /** 画布平移偏移量 { x, y } */
  viewOffset: { type: Object, default: () => ({ x: 0, y: 0 }) },
  /** 缩放值 (0.1 ~ 5) */
  zoom: { type: Number, default: 1 },
  /** 当前选中节点 ID */
  selectedNodeId: { type: String, default: null },
  /** 当前选中边 ID */
  selectedEdgeId: { type: String, default: null },
  /** 是否处于连线模式 */
  connectMode: { type: Boolean, default: false },
  /** 连线模式源节点 ID */
  connectSourceId: { type: String, default: null },
  /** 是否处于重挂载模式 */
  reparentMode: { type: Boolean, default: false },
  /** 重挂载源节点 ID */
  reparentSourceId: { type: String, default: null },
  /** 当前拖拽中的节点 ID */
  draggingNodeId: { type: String, default: null },
  /** 是否正在平移画布 */
  isPanning: { type: Boolean, default: false },
  /** 贝叶斯分析高亮节点 ID 集合 */
  highlightedNodeIds: { type: Set, default: () => new Set() },
  /** 贝叶斯分析高亮边 ID 集合 */
  highlightedEdgeIds: { type: Set, default: () => new Set() },
  /** 是否启用贝叶斯高亮 */
  highlightEnabled: { type: Boolean, default: false },
  /** 右键菜单状态 { visible, x, y, type, nodeId } */
  contextMenu: { type: Object, default: () => ({ visible: false, x: 0, y: 0, type: 'canvas', nodeId: null }) },
  /** 折叠节点 ID 集合 */
  collapsedNodeIds: { type: Set, default: () => new Set() },
  /** 拖拽计数器，强制边线实时跟随 */
  dragTick: { type: Number, default: 0 }
});

/* ==================================================================
 * Emits
 * ================================================================== */

const emit = defineEmits([
  'update:viewOffset',
  'update:zoom',
  'node-click',
  'node-contextmenu',
  'node-drag-start',
  'canvas-click',
  'canvas-contextmenu',
  'canvas-pointerdown',
  'edge-click',
  'toggle-collapse',
  'wheel',
  'update:draggingNodeId',
  'update:isPanning'
]);

/* ==================================================================
 * 辅助函数
 * ================================================================== */

/**
 * 计算从矩形中心指向外部点的射线与矩形边界的交点
 * 用于让连线端点落在节点矩形边框上，而非被卡片遮挡
 */
function lineRectIntersection(outX, outY, rectX, rectY, rectW, rectH) {
  const cx = rectX + rectW / 2;
  const cy = rectY + rectH / 2;
  const dx = outX - cx;
  const dy = outY - cy;

  if (Math.abs(dx) < 0.001 && Math.abs(dy) < 0.001) return { x: cx, y: cy };

  let tMin = Infinity;

  // 右边: x = rectX + rectW
  if (dx > 0) {
    const t = (rectX + rectW - cx) / dx;
    const hitY = cy + t * dy;
    if (hitY >= rectY && hitY <= rectY + rectH && t < tMin) tMin = t;
  }
  // 左边: x = rectX
  if (dx < 0) {
    const t = (rectX - cx) / dx;
    const hitY = cy + t * dy;
    if (hitY >= rectY && hitY <= rectY + rectH && t < tMin) tMin = t;
  }
  // 下边: y = rectY + rectH
  if (dy > 0) {
    const t = (rectY + rectH - cy) / dy;
    const hitX = cx + t * dx;
    if (hitX >= rectX && hitX <= rectX + rectW && t < tMin) tMin = t;
  }
  // 上边: y = rectY
  if (dy < 0) {
    const t = (rectY - cy) / dy;
    const hitX = cx + t * dx;
    if (hitX >= rectX && hitX <= rectX + rectW && t < tMin) tMin = t;
  }

  return { x: cx + tMin * dx, y: cy + tMin * dy };
}

/**
 * 递归查找被折叠节点的所有子孙节点
 */
const hiddenNodeIds = computed(() => {
  const hidden = new Set();
  const hideChildren = (parentId) => {
    props.nodes.forEach(n => {
      if (n.parent_id === parentId) {
        hidden.add(n.id);
        hideChildren(n.id);
      }
    });
  };
  if (props.collapsedNodeIds) {
    props.collapsedNodeIds.forEach(id => hideChildren(id));
  }
  return hidden;
});

/* ==================================================================
 * 派生数据
 * ================================================================== */

/** 可见节点 (排除被折叠节点及其子孙) */
const visibleNodes = computed(() =>
  props.nodes.filter(n => !hiddenNodeIds.value.has(n.id))
);

/** 可见边 (排除连接隐藏节点的边) */
const visibleEdges = computed(() =>
  props.edges.filter(e =>
    !hiddenNodeIds.value.has(e.source) && !hiddenNodeIds.value.has(e.target)
  )
);

/** 节点 ID -> 节点数据映射 */
const nodeMap = computed(() => {
  const map = new Map();
  visibleNodes.value.forEach(node => map.set(node.id, node));
  return map;
});

/**
 * 判断节点是否有子节点
 */
function hasChildren(nodeId) {
  return props.nodes.some(n => n.parent_id === nodeId);
}

/**
 * 预计算边视图数据：路径、标签位置、显示关系名
 */
const edgeViews = computed(() => {
  // 读取 dragTick 强制在拖拽时重新计算
  void props.dragTick;
  return visibleEdges.value
    .map(edge => {
      const source = nodeMap.value.get(edge.source);
      const target = nodeMap.value.get(edge.target);
      if (!source || !target) return null;

      // 节点中心坐标 (卡片宽 200, 高约 70)
      const srcCX = source.x + 100;
      const srcCY = source.y + 35;
      const tgtCX = target.x + 100;
      const tgtCY = target.y + 35;

      // 射线与矩形边界求交点
      const srcPt = lineRectIntersection(tgtCX, tgtCY, source.x, source.y, 200, 70);
      const tgtPt = lineRectIntersection(srcCX, srcCY, target.x, target.y, 200, 70);

      const x1 = srcPt.x;
      const y1 = srcPt.y;
      const x2 = tgtPt.x;
      const y2 = tgtPt.y;

      // 权重百分比展示
      const effWeight = edge.weight != null ? edge.weight : 0.5;
      const weightPct = (effWeight * 100).toFixed(0);
      const displayRelation = edge.relation + ' · ' + weightPct + '%';

      if (edge.kind === 'parent-child') {
        // 树状正交折线
        const midY = y1 + (y2 - y1) / 2;
        const path = `M ${x1} ${y1} L ${x1} ${midY} L ${x2} ${midY} L ${x2} ${y2}`;
        const labelX = (x1 + x2) / 2;
        const labelY = (y1 + y2) / 2;
        return { ...edge, x1, y1, x2, y2, labelX, labelY, path, displayRelation };
      } else {
        // 普通关系：二次贝塞尔曲线
        const dx = x2 - x1;
        const dy = y2 - y1;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const cx = (x1 + x2) / 2;
        const cy = (y1 + y2) / 2 + dist * 0.15;
        const path = `M ${x1} ${y1} Q ${cx} ${cy} ${x2} ${y2}`;
        const labelX = 0.25 * x1 + 0.5 * cx + 0.25 * x2;
        const labelY = 0.25 * y1 + 0.5 * cy + 0.25 * y2;
        return { ...edge, x1, y1, x2, y2, cx, cy, labelX, labelY, path, displayRelation };
      }
    })
    .filter(Boolean);
});

/* ==================================================================
 * 事件处理
 * ================================================================== */

function onNodeClick(nodeId) {
  emit('node-click', nodeId);
}

function onNodeContextMenu(event, nodeId) {
  emit('node-contextmenu', event, nodeId);
}

function onNodeDragStart(event, node) {
  emit('node-drag-start', event, node);
}

function onCanvasClick() {
  emit('canvas-click');
}

function onCanvasContextMenu(event) {
  emit('canvas-contextmenu', event);
}

function onCanvasPointerDown(event) {
  emit('canvas-pointerdown', event);
}

function onWheel(event) {
  emit('wheel', event);
}

function onEdgeClick(edgeId) {
  emit('edge-click', edgeId);
}

function onToggleCollapse(nodeId) {
  emit('toggle-collapse', nodeId);
}

function zoomIn() {
  const newZoom = Math.min(props.zoom * 1.2, 5);
  emit('update:zoom', newZoom);
}

function zoomOut() {
  const newZoom = Math.max(props.zoom / 1.2, 0.1);
  emit('update:zoom', newZoom);
}

function zoomReset() {
  emit('update:zoom', 1);
  emit('update:viewOffset', { x: 0, y: 0 });
}
</script>

<template>
  <main
    class="canvas"
    :class="{ panning: isPanning }"
    :style="{
      backgroundPosition: `${viewOffset.x}px ${viewOffset.y}px`,
      backgroundSize: `${24 * zoom}px ${24 * zoom}px`
    }"
    @pointerdown="onCanvasPointerDown"
    @wheel.prevent="onWheel"
    @click.self="onCanvasClick"
    @contextmenu.prevent="onCanvasContextMenu"
  >
    <!-- 画布空状态提示 -->
    <div class="canvas-hint" v-if="nodes.length === 0">
      画布为空，右键点击空白处「新增独立本体」
    </div>

    <!-- 右键菜单 -->
    <div
      class="context-menu"
      v-if="contextMenu.visible"
      :style="{ top: contextMenu.y + 'px', left: contextMenu.x + 'px' }"
      @click.stop
    >
      <template v-if="contextMenu.type === 'node'">
        <div class="menu-item" @click="$emit('add-child-ontology', contextMenu.nodeId)">
          <span class="menu-icon">&#10133;</span> 新增子本体
        </div>
        <div class="menu-item" @click="$emit('start-connection', contextMenu.nodeId)">
          <span class="menu-icon">&#128279;</span> 从此节点连线
        </div>
        <div class="menu-item" @click="$emit('start-reparent', contextMenu.nodeId)">
          <span class="menu-icon">&#127794;</span> 将此节点转为子本体
        </div>
        <div class="menu-divider" v-if="hasChildren(contextMenu.nodeId)"></div>
        <div class="menu-item" v-if="hasChildren(contextMenu.nodeId)" @click="onToggleCollapse(contextMenu.nodeId)">
          <span class="menu-icon">&#8597;&#65039;</span>
          {{ collapsedNodeIds?.has(contextMenu.nodeId) ? '展开子节点' : '折叠子节点' }}
        </div>
      </template>
      <template v-else>
        <div class="menu-item" @click="$emit('add-root-ontology-menu')">
          <span class="menu-icon">&#10133;</span> 在此新增独立本体
        </div>
      </template>
    </div>

    <!-- 画布内容容器 (支持平移和缩放) -->
    <div
      class="canvas-content"
      :style="{
        transform: `translate(${viewOffset.x}px, ${viewOffset.y}px) scale(${zoom})`,
        transformOrigin: '0 0'
      }"
      @click.self="onCanvasClick"
    >
      <!-- SVG 边线层 -->
      <svg class="edges-layer" :class="{ 'is-dragging': draggingNodeId }">
        <defs>
          <marker id="arrow" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto">
            <path d="M0,0 L0,8 L10,4 z" fill="#6366f1" />
          </marker>
          <marker id="arrow-selected" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto">
            <path d="M0,0 L0,8 L10,4 z" fill="#3b82f6" />
          </marker>
          <marker id="arrow-parent" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto">
            <path d="M0,0 L0,8 L10,4 z" fill="#10b981" />
          </marker>
          <marker id="arrow-symmetric" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto">
            <path d="M0,0 L0,8 L10,4 z" fill="#8b5cf6" />
          </marker>
          <marker id="arrow-reverse-symmetric" markerWidth="10" markerHeight="8" refX="1" refY="4" orient="auto">
            <path d="M10,0 L10,8 L0,4 z" fill="#8b5cf6" />
          </marker>
        </defs>

        <EdgeLine
          v-for="ev in edgeViews"
          :key="ev.id"
          :edge="ev"
          :selected="selectedEdgeId === ev.id"
          :highlighted="highlightEnabled && highlightedEdgeIds?.has(ev.id)"
          :dimmed="highlightEnabled && !highlightedEdgeIds?.has(ev.id)"
          @click="onEdgeClick(ev.id)"
        />
      </svg>

      <!-- 节点卡片层 -->
      <NodeCard
        v-for="node in visibleNodes"
        :key="node.id"
        :node="node"
        :selected="selectedNodeId === node.id"
        :connecting="connectMode && connectSourceId === node.id"
        :dragging="draggingNodeId === node.id"
        :highlighted="highlightEnabled && highlightedNodeIds?.has(node.id)"
        :dimmed="highlightEnabled && !highlightedNodeIds?.has(node.id)"
        :has-children="hasChildren(node.id)"
        :collapsed="collapsedNodeIds?.has(node.id)"
        @click="onNodeClick(node.id)"
        @contextmenu="onNodeContextMenu($event, node.id)"
        @drag-start="onNodeDragStart($event, node)"
        @toggle-collapse="onToggleCollapse(node.id)"
      />
    </div>

    <!-- 缩放控件 -->
    <div class="zoom-controls" @click.stop>
      <button class="zoom-btn" @click="zoomIn" title="放大 (或使用滚轮)">&#65291;</button>
      <button class="zoom-btn" @click="zoomReset" title="重置缩放">&#8962;</button>
      <button class="zoom-btn" @click="zoomOut" title="缩小 (或使用滚轮)">&#65293;</button>
    </div>
  </main>
</template>

<style scoped>
/* ======================== 画布容器 ======================== */

.canvas {
  position: relative;
  flex: 1;
  overflow: hidden;
  background-color: #fafbfc;
  cursor: default;
  background-image:
    radial-gradient(circle, rgba(148, 163, 184, 0.22) 1px, transparent 1px);
  background-size: 24px 24px;
}

.canvas-content {
  width: 100%;
  height: 100%;
  position: absolute;
  inset: 0;
  will-change: transform;
}

.canvas.panning,
.canvas:active {
  cursor: grabbing;
}

/* ======================== 空状态提示 ======================== */

.canvas-hint {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  color: #64748b;
  font-size: 15px;
  font-weight: 500;
  pointer-events: none;
  user-select: none;
  background: rgba(255, 255, 255, 0.88);
  padding: 14px 28px;
  border-radius: 12px;
  box-shadow:
    0 4px 6px -1px rgba(0, 0, 0, 0.06),
    0 2px 4px -2px rgba(0, 0, 0, 0.04);
  border: 1px solid #f1f5f9;
  backdrop-filter: blur(4px);
}

/* ======================== 边线图层 ======================== */

.edges-layer {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  overflow: visible;
}

/* ======================== 右键菜单 ======================== */

.context-menu {
  position: absolute;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  box-shadow:
    0 12px 32px -6px rgba(0, 0, 0, 0.1),
    0 8px 12px -6px rgba(0, 0, 0, 0.08);
  padding: 6px;
  min-width: 200px;
  z-index: 1000;
  animation: context-enter 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  transform-origin: top left;
}

@keyframes context-enter {
  from {
    opacity: 0;
    transform: scale(0.92) translateY(-4px);
  }
  to {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
}

.menu-item {
  padding: 10px 12px;
  font-size: 13px;
  font-weight: 500;
  color: #374151;
  cursor: pointer;
  border-radius: 6px;
  display: flex;
  align-items: center;
  gap: 10px;
  transition: all 0.15s cubic-bezier(0.4, 0, 0.2, 1);
}

.menu-item:hover {
  background: #f1f5f9;
  color: #0f172a;
}

.menu-icon {
  font-size: 13px;
  width: 18px;
  text-align: center;
  flex-shrink: 0;
  opacity: 0.8;
}

.menu-divider {
  height: 1px;
  background: #e2e8f0;
  margin: 4px 8px;
}

/* ======================== 缩放控件 ======================== */

.zoom-controls {
  position: absolute;
  bottom: 20px;
  right: 20px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  z-index: 50;
}

.zoom-btn {
  width: 34px;
  height: 34px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.88);
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 600;
  color: #475569;
  cursor: pointer;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  backdrop-filter: blur(8px);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
  line-height: 1;
}

.zoom-btn:hover {
  background: #ffffff;
  border-color: #2563eb;
  color: #2563eb;
  box-shadow:
    0 4px 6px -1px rgba(0, 0, 0, 0.06),
    0 2px 4px -2px rgba(0, 0, 0, 0.04);
  transform: scale(1.08);
}

.zoom-btn:active {
  transform: scale(0.94);
}

/* ======================== 拖拽时禁用过渡 ======================== */

.edges-layer.is-dragging :deep(.edge-line),
.edges-layer.is-dragging :deep(.edge-label-bg),
.edges-layer.is-dragging :deep(.edge-label) {
  transition: none !important;
}
</style>
