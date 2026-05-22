<script setup>
/**
 * NodeCard.vue - 单个本体节点卡片组件
 * 显示节点名称、ID、属性列表，支持选中/拖拽/高亮等视觉状态
 */

defineProps({
  /** 节点数据对象 { id, name, x, y, attributes?, parent_id? } */
  node: {
    type: Object,
    required: true
  },
  /** 是否选中 */
  selected: {
    type: Boolean,
    default: false
  },
  /** 是否为连线模式的源节点 */
  connecting: {
    type: Boolean,
    default: false
  },
  /** 是否正在拖拽 */
  dragging: {
    type: Boolean,
    default: false
  },
  /** 贝叶斯分析高亮 */
  highlighted: {
    type: Boolean,
    default: false
  },
  /** 贝叶斯分析时非关注节点的弱化 */
  dimmed: {
    type: Boolean,
    default: false
  },
  /** 该节点是否拥有子节点 */
  hasChildren: {
    type: Boolean,
    default: false
  },
  /** 该节点是否处于折叠状态 */
  collapsed: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits([
  'click',
  'contextmenu',
  'drag-start',
  'toggle-collapse'
]);

function onClick() {
  emit('click');
}

function onContextMenu(event) {
  emit('contextmenu', event);
}

function onPointerDown(event) {
  emit('drag-start', event);
}

function onToggleCollapse() {
  emit('toggle-collapse');
}
</script>

<template>
  <div
    :class="[
      'node-card',
      { selected, connecting, dragging, highlighted, dimmed }
    ]"
    :style="{
      '--node-x': node.x + 'px',
      '--node-y': node.y + 'px'
    }"
    @click.stop="onClick"
    @pointerdown.stop="onPointerDown"
    @contextmenu.prevent.stop="onContextMenu"
  >
    <!-- 顶部色条 -->
    <div class="node-topbar" :class="{ 'has-children': hasChildren }"></div>

    <!-- 节点头部 -->
    <div class="node-header">
      <div class="node-icon">
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <path d="M12 2L2 7l10 5 10-5-10-5z"/>
          <path d="M2 17l10 5 10-5"/>
          <path d="M2 12l10 5 10-5"/>
        </svg>
      </div>
      <span class="node-title" :title="node.name" v-html="node.name"></span>
    </div>

    <!-- 节点内容区 -->
    <div class="node-body">
      <div class="node-id">ID: {{ node.id?.slice(0, 6) }}</div>
    </div>

    <!-- 展开/折叠按钮 -->
    <div
      v-if="hasChildren"
      class="collapse-btn"
      @click.stop="onToggleCollapse"
    >
      {{ collapsed ? '+' : '-' }}
    </div>
  </div>
</template>

<style scoped>
/* ======================== Node Card 卡片样式 ======================== */

.node-card {
  position: absolute;
  top: 0;
  left: 0;
  width: 200px;
  transform: translate(var(--node-x, 0px), var(--node-y, 0px));
  background: linear-gradient(135deg, #ffffff 0%, #fafbfc 100%);
  border-radius: 14px;
  border: 1px solid rgba(203, 213, 225, 0.6);
  box-shadow:
    0 1px 2px rgba(0, 0, 0, 0.04),
    0 2px 8px rgba(0, 0, 0, 0.04),
    0 6px 16px rgba(0, 0, 0, 0.03);
  cursor: grab;
  user-select: none;
  transition:
    border-color 0.25s cubic-bezier(0.4, 0, 0.2, 1),
    box-shadow 0.25s cubic-bezier(0.4, 0, 0.2, 1),
    background 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  will-change: transform, box-shadow;
  z-index: 1;
  overflow: hidden;
}

/* 卡片顶部光晕条 */
.node-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(148, 163, 184, 0.2), transparent);
  z-index: 2;
  pointer-events: none;
}

.node-card:hover {
  transform: translate(var(--node-x, 0px), var(--node-y, 0px)) translateY(-2px);
  box-shadow:
    0 2px 4px rgba(0, 0, 0, 0.05),
    0 4px 14px rgba(0, 0, 0, 0.06),
    0 8px 28px rgba(0, 0, 0, 0.05);
  border-color: rgba(148, 163, 184, 0.8);
  z-index: 10;
}

.node-card:active {
  cursor: grabbing;
}

/* 拖拽中 */
.node-card.dragging {
  cursor: grabbing;
  transform: translate(var(--node-x, 0px), var(--node-y, 0px)) scale(1.03);
  box-shadow:
    0 4px 8px rgba(0, 0, 0, 0.08),
    0 8px 24px rgba(0, 0, 0, 0.08),
    0 16px 48px rgba(0, 0, 0, 0.1),
    0 0 0 1px rgba(37, 99, 235, 0.15);
  border-color: rgba(37, 99, 235, 0.35);
  background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
  z-index: 100;
  opacity: 0.94;
  filter: saturate(1.05);
}

/* 选中态 */
.node-card.selected {
  border-color: #2563eb;
  box-shadow:
    0 0 0 3px rgba(37, 99, 235, 0.1),
    0 0 20px rgba(37, 99, 235, 0.06),
    0 4px 14px rgba(0, 0, 0, 0.06),
    0 8px 28px rgba(0, 0, 0, 0.04);
  z-index: 5;
  animation: node-pulse 0.6s cubic-bezier(0.16, 1, 0.3, 1);
  background: linear-gradient(135deg, #ffffff 0%, #eff6ff 100%);
}

@keyframes node-pulse {
  0% {
    box-shadow: 0 0 0 0 rgba(37, 99, 235, 0.25);
    border-color: #93c5fd;
  }
  100% {
    box-shadow:
      0 0 0 3px rgba(37, 99, 235, 0.1),
      0 0 20px rgba(37, 99, 235, 0.06),
      0 4px 14px rgba(0, 0, 0, 0.06),
      0 8px 28px rgba(0, 0, 0, 0.04);
    border-color: #2563eb;
  }
}

/* 连线模式源节点 */
.node-card.connecting {
  border-color: #d97706;
  box-shadow:
    0 0 0 3px rgba(217, 119, 6, 0.12),
    0 0 24px rgba(217, 119, 6, 0.05),
    0 4px 14px rgba(0, 0, 0, 0.05);
  animation: pulse-connecting 2.2s cubic-bezier(0.4, 0, 0.2, 1) infinite;
  background: linear-gradient(135deg, #ffffff 0%, #fffbeb 100%);
}

@keyframes pulse-connecting {
  0%, 100% {
    box-shadow:
      0 0 0 3px rgba(217, 119, 6, 0.12),
      0 0 24px rgba(217, 119, 6, 0.05),
      0 4px 14px rgba(0, 0, 0, 0.05);
  }
  50% {
    box-shadow:
      0 0 0 5px rgba(217, 119, 6, 0.06),
      0 0 32px rgba(217, 119, 6, 0.02),
      0 4px 14px rgba(0, 0, 0, 0.05);
  }
}

/* ======================== 顶部色条 ======================== */

.node-topbar {
  height: 4px;
  background: linear-gradient(90deg, #cbd5e1, #e2e8f0);
  border-radius: 0;
  transition: background 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  z-index: 1;
}

.node-topbar::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 1px;
  background: rgba(255, 255, 255, 0.6);
}

.node-topbar.has-children {
  background: linear-gradient(90deg, #10b981, #34d399);
}

.node-card.selected .node-topbar {
  background: linear-gradient(90deg, #2563eb, #6366f1);
}

.node-card.selected .node-topbar.has-children {
  background: linear-gradient(90deg, #2563eb, #10b981);
}

/* ======================== 节点头部 ======================== */

.node-header {
  padding: 14px 16px 12px 16px;
  display: flex;
  align-items: center;
  gap: 10px;
  border-bottom: 1px solid rgba(241, 245, 249, 0.8);
  background: transparent;
  border-radius: 0;
  transition:
    background 0.25s cubic-bezier(0.4, 0, 0.2, 1),
    border-color 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

.node-card.selected .node-header {
  background: rgba(239, 246, 255, 0.55);
  border-bottom-color: rgba(191, 219, 254, 0.8);
}

/* ======================== 节点图标 ======================== */

.node-icon {
  color: #64748b;
  display: flex;
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  background: linear-gradient(135deg, #f1f5f9, #e2e8f0);
  border-radius: 8px;
  align-items: center;
  justify-content: center;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

.node-card.selected .node-icon {
  color: #2563eb;
  background: linear-gradient(135deg, #dbeafe, #bfdbfe);
}

.node-icon svg {
  width: 16px;
  height: 16px;
}

/* ======================== 节点标题 ======================== */

.node-title {
  font-size: 14px;
  font-weight: 650;
  color: #0f172a;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  letter-spacing: -0.01em;
  line-height: 1.3;
}

/* ======================== 节点内容区 ======================== */

.node-body {
  padding: 10px 16px 14px 16px;
}

.node-id {
  font-size: 11px;
  color: #94a3b8;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-weight: 500;
  background: rgba(241, 245, 249, 0.7);
  display: inline-block;
  padding: 2px 8px;
  border-radius: 5px;
  letter-spacing: 0.02em;
}

.node-card.selected .node-id {
  background: rgba(219, 234, 254, 0.6);
  color: #3b82f6;
}

/* ======================== 折叠按钮 ======================== */

.collapse-btn {
  position: absolute;
  bottom: -11px;
  left: 50%;
  transform: translateX(-50%);
  width: 22px;
  height: 22px;
  background: #ffffff;
  border: 1.5px solid #e2e8f0;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  color: #64748b;
  cursor: pointer;
  z-index: 10;
  box-shadow:
    0 1px 3px rgba(0, 0, 0, 0.06),
    0 2px 8px rgba(0, 0, 0, 0.04);
  transition: all 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);
  line-height: 1;
}

.collapse-btn:hover {
  border-color: #2563eb;
  color: #2563eb;
  background: #eff6ff;
  box-shadow:
    0 2px 6px rgba(37, 99, 235, 0.12),
    0 4px 14px rgba(37, 99, 235, 0.08);
  transform: translateX(-50%) scale(1.18);
}

.collapse-btn:active {
  transform: translateX(-50%) scale(0.92);
}

/* ======================== 贝叶斯高亮联动 ======================== */

.node-card.highlighted {
  box-shadow:
    0 0 0 3px rgba(30, 64, 175, 0.5),
    0 0 16px rgba(30, 64, 175, 0.25);
}

.node-card.dimmed {
  opacity: 0.3;
  transition: opacity 0.35s ease;
}
</style>
