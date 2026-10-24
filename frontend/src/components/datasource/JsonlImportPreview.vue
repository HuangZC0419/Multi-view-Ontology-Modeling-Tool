<script setup>
import { computed, ref } from "vue";

const API_BASE = import.meta.env.VITE_API_BASE || "";

const props = defineProps({
  previewData: {
    type: Object,
    required: true,
  },
});

const emit = defineEmits(["import-done", "back"]);

const summary = computed(() => props.previewData.summary || {});
const mappings = computed(() => summary.value.mappings || {});
const labels = computed(() => Object.entries(summary.value.labels || {}));
const fileNames = computed(() => summary.value.file_names || []);
const warnings = computed(() => summary.value.warnings || []);
const isImporting = ref(false);
const errorMessage = ref("");

const hasContent = computed(
  () => (summary.value.files || 0) > 0 && (summary.value.entities || 0) > 0
);

function mappingText(key, fallback) {
  return mappings.value[key] || fallback;
}

async function confirmImport() {
  if (!hasContent.value || isImporting.value) return;
  isImporting.value = true;
  errorMessage.value = "";
  try {
    const resp = await fetch(`${API_BASE}/api/datasource/jsonl/import`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source_id: props.previewData.source_id }),
    });
    if (!resp.ok) {
      const errData = await resp.json().catch(() => ({}));
      throw new Error(errData.detail || errData.message || "导入失败");
    }
    const data = await resp.json();
    if (!data.nodes || data.nodes.length === 0) {
      throw new Error("未解析到可导入的知识节点");
    }
    emit("import-done", data.nodes, data.edges || [], [], [], { merge: true });
  } catch (err) {
    errorMessage.value = err.message || "导入请求失败";
  } finally {
    isImporting.value = false;
  }
}
</script>

<template>
  <div class="jp-overlay" @click.self="emit('back')">
    <div class="jp-dialog" @click.stop>
      <div class="jp-header">
        <div class="jp-header-left">
          <button class="jp-back" @click="emit('back')">‹</button>
          <h2>JSONL 导入预览</h2>
          <span class="jp-source">{{ previewData.sourceName }}</span>
        </div>
        <button class="jp-close" @click="emit('back')">×</button>
      </div>

      <div class="jp-body">
        <div v-if="errorMessage" class="jp-error">{{ errorMessage }}</div>

        <div class="jp-section">
          <div class="jp-section-title">识别到的字段</div>
          <div class="jp-mapping-row">
            <span>文件名</span><code>{{ mappingText("file", "未识别（使用上传文件名）") }}</code>
          </div>
          <div class="jp-mapping-row">
            <span>实体</span><code>{{ mappingText("entities", "未识别") }}</code>
          </div>
          <div class="jp-mapping-row">
            <span>关系</span><code>{{ mappingText("relations", "未识别") }}</code>
          </div>
        </div>

        <div class="jp-stats">
          <div class="jp-stat"><strong>{{ summary.records || 0 }}</strong><span>记录</span></div>
          <div class="jp-stat"><strong>{{ summary.files || 0 }}</strong><span>文件</span></div>
          <div class="jp-stat"><strong>{{ summary.entities || 0 }}</strong><span>实体</span></div>
          <div class="jp-stat"><strong>{{ summary.relations || 0 }}</strong><span>关系</span></div>
        </div>

        <div class="jp-section" v-if="labels.length">
          <div class="jp-section-title">标签分布</div>
          <div class="jp-label-list">
            <span v-for="[name, count] in labels" :key="name" class="jp-label-chip">
              {{ name }} <b>{{ count }}</b>
            </span>
          </div>
        </div>

        <div class="jp-section" v-if="fileNames.length">
          <div class="jp-section-title">文件（前 20 个）</div>
          <ul class="jp-file-list">
            <li v-for="name in fileNames.slice(0, 20)" :key="name">{{ name }}</li>
          </ul>
        </div>

        <div class="jp-section" v-if="warnings.length || summary.unresolved_relations">
          <div class="jp-section-title">警告（前 20 条）</div>
          <ul class="jp-warning-list">
            <li v-if="summary.unresolved_relations">
              {{ summary.unresolved_relations }} 条关系的端点无法解析，已跳过
            </li>
            <li v-for="(item, index) in warnings.slice(0, 20)" :key="index">{{ item }}</li>
          </ul>
        </div>

        <div class="jp-empty" v-if="!hasContent">未识别到有效记录，请检查文件格式。</div>
      </div>

      <div class="jp-footer">
        <button class="jp-btn jp-btn-ghost" @click="emit('back')">返回</button>
        <button
          class="jp-btn jp-btn-primary"
          :disabled="isImporting || !hasContent"
          @click="confirmImport"
        >
          {{ isImporting ? "导入中..." : `确认导入（${summary.entities || 0} 实体 / ${summary.relations || 0} 关系）` }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.jp-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.5);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 152;
}

.jp-dialog {
  width: 640px;
  max-width: 95vw;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  background: #ffffff;
  border-radius: 14px;
  box-shadow: 0 20px 40px -8px rgba(0, 0, 0, 0.16);
}

.jp-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid #f1f5f9;
}

.jp-header-left {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.jp-header-left h2 {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: #0f172a;
  white-space: nowrap;
}

.jp-source {
  font-size: 12.5px;
  color: #94a3b8;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.jp-back,
.jp-close {
  border: 1px solid #e2e8f0;
  background: #ffffff;
  color: #64748b;
  border-radius: 8px;
  width: 30px;
  height: 30px;
  cursor: pointer;
  font-size: 16px;
  line-height: 1;
}

.jp-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 18px 20px;
}

.jp-error {
  margin-bottom: 12px;
  padding: 10px 12px;
  border: 1px solid #fecaca;
  border-radius: 8px;
  background: #fef2f2;
  color: #dc2626;
  font-size: 13px;
}

.jp-section {
  margin-bottom: 16px;
}

.jp-section-title {
  margin-bottom: 8px;
  font-size: 12px;
  font-weight: 700;
  color: #475569;
  letter-spacing: 0.03em;
}

.jp-mapping-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 4px 0;
  font-size: 13px;
  color: #334155;
}

.jp-mapping-row code {
  color: #1d4ed8;
  background: #eff6ff;
  border-radius: 4px;
  padding: 1px 6px;
  font-size: 12px;
}

.jp-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  margin-bottom: 16px;
}

.jp-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 12px 8px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #f8fafc;
}

.jp-stat strong {
  font-size: 20px;
  color: #1d4ed8;
}

.jp-stat span {
  font-size: 12px;
  color: #64748b;
}

.jp-label-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.jp-label-chip {
  padding: 3px 8px;
  border-radius: 999px;
  background: #eef2ff;
  color: #3730a3;
  font-size: 12px;
}

.jp-label-chip b {
  margin-left: 4px;
  color: #1e40af;
}

.jp-file-list,
.jp-warning-list {
  margin: 0;
  padding-left: 18px;
  max-height: 160px;
  overflow-y: auto;
  font-size: 12.5px;
  color: #475569;
  line-height: 1.7;
}

.jp-warning-list {
  color: #b45309;
}

.jp-empty {
  padding: 32px 12px;
  text-align: center;
  color: #94a3b8;
  font-size: 14px;
}

.jp-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 14px 20px;
  border-top: 1px solid #f1f5f9;
  background: #f8fafc;
  border-radius: 0 0 14px 14px;
}

.jp-btn {
  padding: 9px 18px;
  border-radius: 8px;
  border: 1px solid transparent;
  font-size: 13.5px;
  font-weight: 600;
  cursor: pointer;
}

.jp-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.jp-btn-ghost {
  background: transparent;
  color: #475569;
}

.jp-btn-primary {
  background: #2563eb;
  color: #ffffff;
}
</style>
