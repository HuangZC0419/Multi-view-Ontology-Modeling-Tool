<script setup>
import { ref } from "vue";
import DbConnector from "./DbConnector.vue";
import FileUploader from "./FileUploader.vue";
import SchemaPreview from "./SchemaPreview.vue";

const emit = defineEmits(["import-nodes"]);

const showDbDialog = ref(false);
const showFileDialog = ref(false);
const previewData = ref(null); // {source_id, tables, columns, sourceType:'db'|'file'}

function onPreviewReady(data) {
  previewData.value = data;
  showDbDialog.value = false;
  showFileDialog.value = false;
}

function onImportDone(nodes) {
  emit("import-nodes", nodes);
  previewData.value = null;
}

function onBack() {
  previewData.value = null;
}
</script>

<template>
  <div class="datasource-panel">
    <div class="ds-section">
      <div class="ds-section-title">数据源接入</div>

      <!-- 数据库连接入口 -->
      <button class="ds-entry-btn ds-db-btn" @click="showDbDialog = true">
        <div class="ds-entry-icon">
          <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <ellipse cx="12" cy="5" rx="9" ry="3"/>
            <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/>
            <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>
          </svg>
        </div>
        <div class="ds-entry-text">
          <span class="ds-entry-label">连接数据库</span>
          <span class="ds-entry-desc">达梦 / 模拟数据库</span>
        </div>
        <div class="ds-entry-arrow">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <polyline points="9 18 15 12 9 6"/>
          </svg>
        </div>
      </button>

      <!-- 文件上传入口 -->
      <button class="ds-entry-btn ds-file-btn" @click="showFileDialog = true">
        <div class="ds-entry-icon">
          <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/>
            <polyline points="13 2 13 9 20 9"/>
          </svg>
        </div>
        <div class="ds-entry-text">
          <span class="ds-entry-label">上传文件</span>
          <span class="ds-entry-desc">Excel / CSV</span>
        </div>
        <div class="ds-entry-arrow">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <polyline points="9 18 15 12 9 6"/>
          </svg>
        </div>
      </button>
    </div>

    <!-- 数据库连接弹窗 -->
    <DbConnector
      v-if="showDbDialog"
      @close="showDbDialog = false"
      @preview-ready="onPreviewReady"
    />

    <!-- 文件上传弹窗 -->
    <FileUploader
      v-if="showFileDialog"
      @close="showFileDialog = false"
      @preview-ready="onPreviewReady"
    />

    <!-- Schema 预览面板 -->
    <SchemaPreview
      v-if="previewData"
      :previewData="previewData"
      @import-done="onImportDone"
      @back="onBack"
    />
  </div>
</template>

<style scoped>
/* ======================== CSS 变量 ======================== */
.datasource-panel {
  --color-primary: #2563eb;
  --color-primary-light: #3b82f6;
  --color-primary-dark: #1d4ed8;
  --color-primary-bg: #eff6ff;
  --color-success: #10b981;
  --color-success-bg: #d1fae5;
  --color-text: #0f172a;
  --color-text-secondary: #475569;
  --color-text-muted: #64748b;
  --color-border: #e2e8f0;
  --color-border-light: #f1f5f9;
  --color-bg: #f8fafc;
  --color-surface: #ffffff;
  --shadow-xs: 0 1px 2px rgba(0,0,0,0.04);
  --shadow-sm: 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
  --shadow-md: 0 4px 6px -1px rgba(0,0,0,0.06), 0 2px 4px -2px rgba(0,0,0,0.04);
  --shadow-lg: 0 10px 15px -3px rgba(0,0,0,0.08), 0 4px 6px -4px rgba(0,0,0,0.06);
  --shadow-xl: 0 20px 40px -8px rgba(0,0,0,0.12), 0 10px 15px -3px rgba(0,0,0,0.08);
  --radius-sm: 6px;
  --radius-md: 8px;
  --radius-lg: 12px;
  --radius-xl: 16px;
  --ease-out: cubic-bezier(0.4, 0, 0.2, 1);
}

.datasource-panel {
  width: 100%;
}

.ds-section {
  margin-bottom: 28px;
}

.ds-section-title {
  font-size: 13px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #475569;
  margin: 0 0 16px 4px;
  font-weight: 700;
}

/* ---------- 入口按钮 ---------- */
.ds-entry-btn {
  display: flex;
  align-items: center;
  width: 100%;
  gap: 12px;
  padding: 14px 16px;
  margin-bottom: 10px;
  border: 1px solid #e2e8f0;
  border-radius: var(--radius-lg);
  background: #ffffff;
  cursor: pointer;
  transition: all 0.2s var(--ease-out);
  text-align: left;
  font-family: inherit;
}

.ds-entry-btn:hover {
  transform: translateY(-1px);
  box-shadow: var(--shadow-md);
}

.ds-entry-btn:active {
  transform: translateY(0);
}

.ds-db-btn:hover {
  background: #eff6ff;
  border-color: #bfdbfe;
}

.ds-db-btn:hover .ds-entry-icon {
  color: #2563eb;
}

.ds-file-btn:hover {
  background: #f0fdf4;
  border-color: #bbf7d0;
}

.ds-file-btn:hover .ds-entry-icon {
  color: #10b981;
}

.ds-entry-icon {
  flex-shrink: 0;
  width: 42px;
  height: 42px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-md);
  background: #f1f5f9;
  color: #64748b;
  transition: all 0.2s var(--ease-out);
}

.ds-db-btn .ds-entry-icon {
  background: #eff6ff;
  color: #3b82f6;
}

.ds-file-btn .ds-entry-icon {
  background: #ecfdf5;
  color: #10b981;
}

.ds-entry-text {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.ds-entry-label {
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
  line-height: 1.3;
}

.ds-entry-desc {
  font-size: 12px;
  color: #94a3b8;
  font-weight: 500;
}

.ds-entry-arrow {
  flex-shrink: 0;
  color: #cbd5e1;
  transition: all 0.2s var(--ease-out);
}

.ds-entry-btn:hover .ds-entry-arrow {
  color: #64748b;
  transform: translateX(2px);
}
</style>
