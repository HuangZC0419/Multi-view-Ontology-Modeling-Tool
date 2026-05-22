<script setup>
import { ref, onMounted, watch } from "vue";

const props = defineProps({
  projectId: { type: String, required: true },
});

const emit = defineEmits(["graph-loaded", "stats"]);

// API_BASE 常量定义
const defaultApiBase =
  typeof window !== "undefined"
    ? `http://${window.location.hostname}:8000`
    : "http://127.0.0.1:8000";
const API_BASE = import.meta.env.VITE_API_BASE || defaultApiBase;

const nodes = ref([]);
const edges = ref([]);
const inferenceRules = ref([]);
const mutexRules = ref([]);
const domainCount = ref(0);
const loading = ref(true);
const error = ref(null);

async function loadData() {
  loading.value = true;
  error.value = null;
  try {
    // 并行加载图数据和业务域数量
    const [graphResp, domainsResp] = await Promise.all([
      fetch(`${API_BASE}/api/perspective/${props.projectId}/process`),
      fetch(`${API_BASE}/api/perspective/${props.projectId}/domains`),
    ]);

    if (!graphResp.ok) {
      throw new Error(`HTTP ${graphResp.status}: ${await graphResp.text()}`);
    }
    const graph = await graphResp.json();
    nodes.value = graph.nodes || [];
    edges.value = graph.edges || [];
    inferenceRules.value = graph.inference_rules || [];
    mutexRules.value = graph.mutex_rules || [];

    // 解析业务域数量（该接口可能返回 404 若无配置）
    if (domainsResp.ok) {
      const domainsData = await domainsResp.json();
      domainCount.value = (domainsData.domains || []).length;
    } else {
      domainCount.value = 0;
    }

    emit("graph-loaded", {
      nodes: nodes.value,
      edges: edges.value,
      inferenceRules: inferenceRules.value,
      mutexRules: mutexRules.value,
    });

    emit("stats", {
      nodes: nodes.value.length,
      edges: edges.value.length,
      inferenceRules: inferenceRules.value.length,
      mutexRules: mutexRules.value.length,
      domains: domainCount.value,
    });
  } catch (e) {
    error.value = e.message;
    console.error("ProcessView: 加载图数据失败:", e);
  } finally {
    loading.value = false;
  }
}

onMounted(loadData);
watch(() => props.projectId, loadData);

defineExpose({ nodes, edges, inferenceRules, mutexRules, loading, error });
</script>

<template>
  <div class="process-view" :class="{ 'is-hidden': !loading && !error }">
    <!-- 加载状态 -->
    <div v-if="loading" class="process-loading">
      <div class="loading-spinner"></div>
      <span>正在加载本体图数据...</span>
    </div>

    <!-- 错误状态 -->
    <div v-else-if="error" class="process-error">
      <svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">
        <circle cx="12" cy="12" r="10" />
        <line x1="12" y1="8" x2="12" y2="12" />
        <line x1="12" y1="16" x2="12.01" y2="16" />
      </svg>
      <h3>图数据加载失败</h3>
      <p>{{ error }}</p>
      <button class="btn-retry" @click="loadData">重新加载</button>
    </div>

    <!-- 数据就绪后不渲染任何可见内容，统计信息通过 emit 传给父组件 -->
  </div>
</template>

<style scoped>
/* ======================== 容器 ======================== */

.process-view {
  /* 默认不占空间，仅加载/错误时展开 */
}

.process-view:not(.is-hidden) {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 200px;
}

.process-view.is-hidden {
  height: 0;
  overflow: hidden;
  flex: none;
}

/* ======================== 加载状态 ======================== */

.process-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  color: #64748b;
  font-size: 14px;
  font-weight: 500;
}

.loading-spinner {
  width: 36px;
  height: 36px;
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

/* ======================== 错误状态 ======================== */

.process-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  color: #94a3b8;
  text-align: center;
  padding: 32px;
}

.process-error h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #475569;
}

.process-error p {
  margin: 0;
  font-size: 13px;
  color: #94a3b8;
  max-width: 400px;
}

.btn-retry {
  margin-top: 8px;
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
</style>
