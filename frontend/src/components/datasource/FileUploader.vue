<script setup>
import { ref } from "vue";

const API_BASE = import.meta.env.VITE_API_BASE ||
  (typeof window !== "undefined" ? `http://${window.location.hostname}:8000` : "http://127.0.0.1:8000");

const emit = defineEmits(["close", "preview-ready"]);

// ---------- 状态 ----------
const fileInputRef = ref(null);
const selectedFile = ref(null);
const isDragging = ref(false);
const isUploading = ref(false);
const uploadStatus = ref(""); // "" | "uploading" | "parsing" | "done" | "error"
const statusMessage = ref("");
const errorMessage = ref("");

const ACCEPTED_TYPES = ".xlsx,.xls,.csv";

// ---------- 拖拽事件 ----------
function onDragEnter(e) {
  e.preventDefault();
  isDragging.value = true;
}

function onDragOver(e) {
  e.preventDefault();
  isDragging.value = true;
}

function onDragLeave(e) {
  e.preventDefault();
  isDragging.value = false;
}

function onDrop(e) {
  e.preventDefault();
  isDragging.value = false;

  const files = e.dataTransfer?.files;
  if (files && files.length > 0) {
    handleFile(files[0]);
  }
}

// ---------- 点击选择 ----------
function onFileInputChange(e) {
  const files = e.target.files;
  if (files && files.length > 0) {
    handleFile(files[0]);
  }
}

function triggerFileInput() {
  fileInputRef.value?.click();
}

// ---------- 文件校验与上传 ----------
function handleFile(file) {
  const name = file.name.toLowerCase();
  const ext = name.substring(name.lastIndexOf("."));

  if (![".xlsx", ".xls", ".csv"].includes(ext)) {
    errorMessage.value = `不支持的文件格式: ${ext}，仅支持 .xlsx .xls .csv`;
    uploadStatus.value = "error";
    return;
  }

  selectedFile.value = file;
  errorMessage.value = "";
  uploadFile(file);
}

async function uploadFile(file) {
  uploadStatus.value = "uploading";
  statusMessage.value = "正在上传文件...";

  const formData = new FormData();
  formData.append("file", file);

  try {
    const resp = await fetch(`${API_BASE}/api/datasource/file/upload`, {
      method: "POST",
      body: formData,
    });

    if (!resp.ok) {
      const errData = await resp.json().catch(() => ({}));
      throw new Error(errData.detail || errData.message || "上传失败");
    }

    uploadStatus.value = "parsing";
    statusMessage.value = "正在解析文件结构...";

    const data = await resp.json();

    uploadStatus.value = "done";
    statusMessage.value = `解析完成：${data.file_name}`;

    // 构建 columns 映射 {tableName: [columns]}
    const columnsMap = data.columns || {};
    const tablesList = data.tables || [];

    emit("preview-ready", {
      source_id: data.file_id,
      tables: tablesList,
      columns: columnsMap,
      sourceType: "file",
      sourceName: data.file_name,
    });
  } catch (err) {
    uploadStatus.value = "error";
    errorMessage.value = err.message || "上传请求失败";
  }
}

function handleClose() {
  emit("close");
}

// ---------- 格式化文件大小 ----------
function formatSize(bytes) {
  if (!bytes) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
</script>

<template>
  <div class="fu-overlay" @click.self="handleClose">
    <div class="fu-dialog" @click.stop>
      <!-- 头部 -->
      <div class="fu-header">
        <div class="fu-header-left">
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/>
            <polyline points="13 2 13 9 20 9"/>
          </svg>
          <h2>上传文件</h2>
        </div>
        <button
          class="fu-close"
          @click="handleClose"
          :disabled="uploadStatus === 'uploading' || uploadStatus === 'parsing'"
        >
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </div>

      <!-- 体部 -->
      <div class="fu-body">
        <!-- 未开始上传 / 可重新上传 -->
        <template v-if="uploadStatus !== 'uploading' && uploadStatus !== 'parsing' && uploadStatus !== 'done'">
          <!-- 拖拽区域 -->
          <div
            class="fu-dropzone"
            :class="{ dragging: isDragging, error: uploadStatus === 'error' }"
            @dragenter="onDragEnter"
            @dragover="onDragOver"
            @dragleave="onDragLeave"
            @drop="onDrop"
            @click="triggerFileInput"
          >
            <!-- 拖拽中 -->
            <div v-if="isDragging" class="fu-drop-content">
              <div class="fu-drop-icon active">
                <svg viewBox="0 0 24 24" width="32" height="32" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                  <polyline points="17 8 12 3 7 8"/>
                  <line x1="12" y1="3" x2="12" y2="15"/>
                </svg>
              </div>
              <p class="fu-drop-title">释放以上传文件</p>
            </div>

            <!-- 默认状态 -->
            <div v-else class="fu-drop-content">
              <div class="fu-drop-icon">
                <svg viewBox="0 0 24 24" width="32" height="32" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                  <polyline points="17 8 12 3 7 8"/>
                  <line x1="12" y1="3" x2="12" y2="15"/>
                </svg>
              </div>
              <p class="fu-drop-title">拖拽文件到此处，或点击选择</p>
              <p class="fu-drop-hint">支持 Excel (.xlsx / .xls) 和 CSV (.csv) 格式</p>
            </div>
          </div>

          <!-- 隐藏的文件 input -->
          <input
            ref="fileInputRef"
            type="file"
            :accept="ACCEPTED_TYPES"
            style="display: none"
            @change="onFileInputChange"
          />

          <!-- 错误提示 -->
          <div v-if="uploadStatus === 'error'" class="fu-error-box">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
              <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
            <span>{{ errorMessage }}</span>
          </div>
        </template>

        <!-- 上传中 -->
        <template v-if="uploadStatus === 'uploading' || uploadStatus === 'parsing'">
          <div class="fu-progress-area">
            <div class="fu-spinner"></div>
            <p class="fu-progress-text">{{ statusMessage }}</p>
            <p v-if="selectedFile" class="fu-progress-file">{{ selectedFile.name }} ({{ formatSize(selectedFile.size) }})</p>
          </div>
        </template>

        <!-- 完成 -->
        <template v-if="uploadStatus === 'done'">
          <div class="fu-success-area">
            <div class="fu-success-icon">
              <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                <polyline points="22 4 12 14.01 9 11.01"/>
              </svg>
            </div>
            <p class="fu-success-text">{{ statusMessage }}</p>
            <button class="fu-btn fu-btn-outline" @click="uploadStatus = ''; selectedFile = null; errorMessage = ''">
              重新选择文件
            </button>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* ======================== 变量 ======================== */
.fu-overlay {
  --color-primary: #2563eb;
  --color-primary-dark: #1d4ed8;
  --color-primary-bg: #eff6ff;
  --color-success: #10b981;
  --color-success-bg: #d1fae5;
  --color-danger: #dc2626;
  --color-danger-bg: #fef2f2;
  --color-text: #0f172a;
  --color-text-secondary: #475569;
  --color-text-muted: #64748b;
  --color-border: #e2e8f0;
  --color-bg: #f8fafc;
  --color-surface: #ffffff;
  --shadow-xl: 0 20px 40px -8px rgba(0,0,0,0.12), 0 10px 15px -3px rgba(0,0,0,0.08);
  --radius-sm: 6px;
  --radius-md: 8px;
  --radius-lg: 12px;
  --radius-xl: 16px;
}

/* ---------- 遮罩 ---------- */
.fu-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.5);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 150;
  animation: fu-overlay-in 0.15s ease-out;
}

@keyframes fu-overlay-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

/* ---------- 弹窗卡片 ---------- */
.fu-dialog {
  background: #ffffff;
  border-radius: var(--radius-xl);
  width: 480px;
  max-width: 95vw;
  box-shadow: var(--shadow-xl);
  animation: fu-dialog-in 0.2s ease-out;
}

@keyframes fu-dialog-in {
  from { opacity: 0; transform: scale(0.95) translateY(10px); }
  to { opacity: 1; transform: scale(1) translateY(0); }
}

/* ---------- 头部 ---------- */
.fu-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 22px 26px 18px 26px;
  border-bottom: 1px solid #f1f5f9;
}

.fu-header-left {
  display: flex;
  align-items: center;
  gap: 12px;
  color: #10b981;
}

.fu-header-left h2 {
  margin: 0;
  font-size: 17px;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.01em;
}

.fu-close {
  width: 34px;
  height: 34px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: 1px solid transparent;
  border-radius: var(--radius-md);
  color: #94a3b8;
  cursor: pointer;
  transition: all 0.2s ease;
  flex-shrink: 0;
}

.fu-close:hover:not(:disabled) {
  background: #f1f5f9;
  border-color: #e2e8f0;
  color: #475569;
}

.fu-close:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* ---------- 体部 ---------- */
.fu-body {
  padding: 26px;
}

/* ---------- 拖拽区域 ---------- */
.fu-dropzone {
  border: 2px dashed #cbd5e1;
  border-radius: var(--radius-lg);
  padding: 48px 24px;
  text-align: center;
  cursor: pointer;
  transition: all 0.25s ease;
  background: #fafbfc;
}

.fu-dropzone:hover {
  border-color: #93c5fd;
  background: #f8faff;
}

.fu-dropzone.dragging {
  border-color: #2563eb;
  background: #eff6ff;
  border-style: solid;
  box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.08);
}

.fu-dropzone.error {
  border-color: #fca5a5;
  background: #fff5f5;
}

.fu-drop-content {
  pointer-events: none;
}

.fu-drop-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: #f1f5f9;
  color: #64748b;
  margin-bottom: 14px;
  transition: all 0.25s ease;
}

.fu-dropzone:hover .fu-drop-icon {
  background: #eff6ff;
  color: #3b82f6;
}

.fu-dropzone.dragging .fu-drop-icon,
.fu-drop-icon.active {
  background: #dbeafe;
  color: #2563eb;
}

.fu-drop-title {
  margin: 0 0 6px 0;
  font-size: 15px;
  font-weight: 600;
  color: #334155;
}

.fu-drop-hint {
  margin: 0;
  font-size: 12.5px;
  color: #94a3b8;
  font-weight: 500;
}

/* ---------- 错误 ---------- */
.fu-error-box {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-top: 14px;
  padding: 12px 14px;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: var(--radius-md);
  color: #dc2626;
  font-size: 13.5px;
  font-weight: 500;
  line-height: 1.5;
}

.fu-error-box svg {
  flex-shrink: 0;
  margin-top: 1px;
}

/* ---------- 进度 ---------- */
.fu-progress-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 40px 24px 32px 24px;
  gap: 14px;
}

.fu-spinner {
  width: 36px;
  height: 36px;
  border: 3px solid #e2e8f0;
  border-top-color: #2563eb;
  border-radius: 50%;
  animation: fu-spin 0.7s linear infinite;
}

@keyframes fu-spin {
  to { transform: rotate(360deg); }
}

.fu-progress-text {
  margin: 0;
  font-size: 14.5px;
  color: #475569;
  font-weight: 600;
}

.fu-progress-file {
  margin: 0;
  font-size: 12.5px;
  color: #94a3b8;
  font-weight: 500;
}

/* ---------- 完成 ---------- */
.fu-success-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 40px 24px 32px 24px;
  gap: 12px;
}

.fu-success-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: #d1fae5;
  color: #059669;
  margin-bottom: 4px;
}

.fu-success-text {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: #15803d;
}

/* ---------- 按钮 ---------- */
.fu-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 10px 20px;
  border-radius: var(--radius-md);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  border: 1px solid transparent;
  outline: none;
  font-family: inherit;
}

.fu-btn-outline {
  background: transparent;
  color: #2563eb;
  border-color: #bfdbfe;
}

.fu-btn-outline:hover {
  background: #eff6ff;
}
</style>
