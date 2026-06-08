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
      label: "概览",
    },
    {
      key: "engineer",
      label: "数据映射",
    },
    {
      key: "process",
      label: "本体推理",
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

    <!-- 下划线指示条 -->
    <div class="nav-indicator-track">
      <div
        class="nav-indicator-bar"
        :style="{
          left: `calc(${tabs.findIndex((t) => t.key === activeTab) * (100 / tabs.length)}% + 0px)`,
          width: `calc(${100 / tabs.length}%)`,
        }"
      ></div>
    </div>
  </nav>
</template>

<style scoped>
/* ======================== 导航栏容器 ======================== */

.perspective-navbar {
  width: 100%;
  display: flex;
  flex-direction: column;
  background: #ffffff;
  border-bottom: 1px solid #e2e8f0;
  flex-shrink: 0;
  user-select: none;
}

/* ======================== Tab 行 ======================== */

.nav-tabs {
  display: flex;
  align-items: stretch;
  height: 48px;
  padding: 0;
  gap: 0;
}

.nav-tab {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 0 20px;
  border: none;
  background: transparent;
  color: #64748b;
  cursor: pointer;
  font-family: inherit;
  font-size: 13.5px;
  font-weight: 500;
  letter-spacing: 0.01em;
  transition: color 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  outline: none;
  position: relative;
}

.nav-tab:hover {
  color: #334155;
  background: rgba(241, 245, 249, 0.6);
}

.nav-tab.active {
  color: #1e3a5f;
  font-weight: 600;
}

.tab-svg {
  flex-shrink: 0;
  opacity: 0.7;
  transition: opacity 0.2s ease;
}

.nav-tab.active .tab-svg {
  opacity: 1;
}

.nav-tab:hover .tab-svg {
  opacity: 0.9;
}

.tab-label-text {
  white-space: nowrap;
}

/* ======================== 下划线指示轨 ======================== */

.nav-indicator-track {
  position: relative;
  height: 3px;
  background: transparent;
}

.nav-indicator-bar {
  position: absolute;
  bottom: 0;
  height: 3px;
  background: #1e3a5f;
  border-radius: 0;
  transition: left 0.3s cubic-bezier(0.16, 1, 0.3, 1),
              width 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}
</style>
