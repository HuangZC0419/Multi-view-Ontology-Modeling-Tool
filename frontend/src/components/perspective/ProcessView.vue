<script setup>
/**
 * ProcessView.vue — 工艺视角数据加载器
 *
 * 不渲染画布。画布由 App.vue 的现有拖拽编辑系统负责。
 * 本组件只负责：加载图数据 → emit 给 App.vue → App.vue 渲染画布。
 */

import { ref, watch, onMounted } from "vue";

const props = defineProps({
  projectId: { type: String, required: true },
});

const emit = defineEmits(["graph-loaded", "stats"]);

const loading = ref(false);
const error = ref("");

const API_BASE = import.meta.env.VITE_API_BASE || "";

async function loadGraph() {
  if (!props.projectId) return;
  loading.value = true;
  error.value = "";

  try {
    const resp = await fetch(`${API_BASE}/api/graph?project_id=${props.projectId}`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const graph = await resp.json();

    const nodes = graph.nodes || [];
    const edges = graph.edges || [];
    const inferenceRules = graph.inference_rules || [];
    const mutexRules = graph.mutex_rules || [];

    emit("graph-loaded", { nodes, edges, inferenceRules, mutexRules });

    // 获取业务域数量作为统计
    let domains = 0;
    try {
      const dr = await fetch(`${API_BASE}/api/perspective/${props.projectId}/domains`);
      if (dr.ok) {
        const dj = await dr.json();
        domains = (dj.domains || []).length;
      }
    } catch (_) { /* 项目可能没有视角配置 */ }

    emit("stats", { nodes: nodes.length, edges: edges.length, inferenceRules: inferenceRules.length, mutexRules: mutexRules.length, domains });
  } catch (e) {
    error.value = e.message || "加载失败";
  } finally {
    loading.value = false;
  }
}

onMounted(loadGraph);
watch(() => props.projectId, loadGraph);
</script>

<template>
  <div class="pv-loader" :class="{ 'is-hidden': !loading && !error }">
    <div v-if="loading" class="pv-spinner">
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#2563eb" stroke-width="2.5" stroke-linecap="round">
        <circle cx="12" cy="12" r="10" stroke="#e2e8f0" />
        <path d="M12 2a10 10 0 0 1 10 10" stroke="#2563eb"><animateTransform attributeName="transform" type="rotate" values="0 12 12;360 12 12" dur="1s" repeatCount="indefinite"/></path>
      </svg>
      <span>加载中...</span>
    </div>
    <div v-if="error" class="pv-error">
      <span>{{ error }}</span>
      <button @click="loadGraph">重试</button>
    </div>
  </div>
</template>

<style scoped>
.pv-loader { display: flex; align-items: center; justify-content: center; padding: 24px; }
.pv-loader.is-hidden { height: 0; padding: 0; overflow: hidden; }
.pv-spinner { display: flex; flex-direction: column; align-items: center; gap: 8px; color: #64748b; font-size: 13px; }
.pv-error { display: flex; flex-direction: column; align-items: center; gap: 8px; color: #dc2626; font-size: 13px; }
.pv-error button { padding: 4px 16px; border: 1px solid #dc2626; border-radius: 6px; background: #fff; color: #dc2626; cursor: pointer; font-size: 12px; }
</style>
