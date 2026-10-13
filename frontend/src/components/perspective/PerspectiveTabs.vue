<script setup>
import { ref, computed, watch } from "vue";

const props = defineProps({
  projectId: { type: String, default: null },
  modelValue: { type: String, default: "process" },
});

const emit = defineEmits(["update:modelValue", "change"]);

const activeTab = ref(props.modelValue || "process");

watch(
  () => props.modelValue,
  (val) => {
    if (val) activeTab.value = val;
  }
);

// 简化的标签定义：Heroicons 风格 SVG 图标，纯文字无 emoji
const tabs = computed(() => {
  return [
    {
      key: "leader",
      label: "概览模式",
    },
    {
      key: "engineer",
      label: "数据映射模式",
    },
    {
      key: "process",
      label: "本体推理模式",
    },
  ];
});

function switchTab(key) {
  if (activeTab.value === key) return;
  activeTab.value = key;
  emit("update:modelValue", key);
  emit("change", key);
}
</script>

<template>
  <nav class="perspective-navbar">
    <!-- 总栏目：标题 + 三种模式同属"知识组织"，整体水平居中 -->
    <div class="nav-group">
      <h3 class="nav-group-title">知识组织</h3>

      <div class="nav-tabs">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          :class="['nav-tab', { active: activeTab === tab.key }]"
          @click="switchTab(tab.key)"
          :title="tab.label"
        >
          <!-- 概览图标：四格 -->
          <svg
            v-if="tab.key === 'leader'"
            class="tab-svg"
            viewBox="0 0 24 24"
            width="16"
            height="16"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <rect x="3" y="3" width="7" height="7" rx="1" />
            <rect x="14" y="3" width="7" height="7" rx="1" />
            <rect x="3" y="14" width="7" height="7" rx="1" />
            <rect x="14" y="14" width="7" height="7" rx="1" />
          </svg>
          <!-- 数据映射图标：数据库 -->
          <svg
            v-if="tab.key === 'engineer'"
            class="tab-svg"
            viewBox="0 0 24 24"
            width="16"
            height="16"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <ellipse cx="12" cy="5" rx="9" ry="3" />
            <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
            <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
          </svg>
          <!-- 本体推理图标：网络 -->
          <svg
            v-if="tab.key === 'process'"
            class="tab-svg"
            viewBox="0 0 24 24"
            width="16"
            height="16"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <circle cx="18" cy="5" r="3" />
            <circle cx="6" cy="12" r="3" />
            <circle cx="18" cy="19" r="3" />
            <line x1="8.59" y1="13.51" x2="15.42" y2="17.49" />
            <line x1="15.41" y1="6.51" x2="8.59" y2="10.49" />
          </svg>
          <span class="tab-label-text">{{ tab.label }}</span>
        </button>
      </div>
    </div>
  </nav>
</template>

<style scoped>
/* ======================== 导航栏容器 ======================== */

.perspective-navbar {
  width: 100%;
  display: flex;
  justify-content: center; /* 总栏目内容整体相对主内容区水平居中 */
  background: #ffffff;
  border-bottom: 1px solid #e2e8f0;
  flex-shrink: 0;
  user-select: none;
}

/* 总栏目容器：标题 + 三种模式作为一个整体居中，并限制横向铺开形成视觉焦点 */
.nav-group {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px; /* 标题行与模式选项行之间的层级留白 */
  width: 100%;
  max-width: 640px;
  padding: 20px 24px 18px;
}

/* ======================== 总栏目标题 ======================== */

.nav-group-title {
  margin: 0;
  font-size: 20px; /* 20px vs 模式名 14px，约 1.43 倍，一眼可辨的总栏目层级 */
  font-weight: 700;
  color: #1e3a5f; /* 主题色：总栏目标题是区域视觉锚点 */
  letter-spacing: 0.04em;
  line-height: 1;
}

/* ======================== 模式选项卡 ======================== */

.nav-tabs {
  display: flex;
  gap: 12px; /* 三项之间等距 */
  width: 100%;
}

.nav-tab {
  flex: 1; /* 并排、等宽 */
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  height: 52px;
  padding: 0 12px;
  border: 1.5px solid #e2e8f0;
  border-radius: 12px;
  background: #ffffff;
  color: #475569;
  font-family: inherit;
  font-size: 14px; /* 模式名下限，不再缩小 */
  font-weight: 600;
  white-space: nowrap;
  cursor: pointer;
  transition: background 0.2s ease, border-color 0.2s ease, color 0.2s ease,
    box-shadow 0.2s ease;
}

/* 悬停：同色系的浅色反馈，给出可点击暗示但不与选中态争夺注意力 */
.nav-tab:hover {
  border-color: rgba(30, 58, 95, 0.25);
  background: #f8fafc;
  color: #1e3a5f;
}

/* 选中：仅用主题色实底这一种手段表达，不叠加下划线等第二种指示 */
.nav-tab.active {
  background: #1e3a5f;
  border-color: #1e3a5f;
  color: #ffffff;
  box-shadow: 0 4px 12px rgba(30, 58, 95, 0.18);
}

/* 键盘聚焦可见性：主题色描边，鼠标点击不触发（仅 :focus-visible） */
.nav-tab:focus-visible {
  outline: 2px solid #1e3a5f;
  outline-offset: 2px;
}

/* 图标跟随文字颜色，不做单独的透明度变化 */
.tab-svg {
  width: 17px;
  height: 17px;
  flex-shrink: 0;
}

.tab-label-text {
  white-space: nowrap;
}

/* ======================== 窄屏：纵向堆叠，避免文字被挤压错位 ======================== */

@media (max-width: 640px) {
  .nav-tabs {
    flex-direction: column;
  }

  .nav-tab {
    width: 100%;
  }
}
</style>
