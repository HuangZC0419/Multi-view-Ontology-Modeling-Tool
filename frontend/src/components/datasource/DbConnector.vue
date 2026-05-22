<script setup>
import { ref, reactive } from "vue";

const API_BASE = import.meta.env.VITE_API_BASE ||
  (typeof window !== "undefined" ? `http://${window.location.hostname}:8000` : "http://127.0.0.1:8000");

const emit = defineEmits(["close", "preview-ready"]);

// ---------- 表单状态 ----------
const dbType = ref("sim_dameng");
const form = reactive({
  host: "127.0.0.1",
  port: "5236",
  user: "",
  password: "",
  schema: "",
});

// ---------- 流程状态 ----------
const step = ref("form"); // form | testing | connecting | fetching_tables | fetching_columns | ready | error
const statusText = ref("");
const errorText = ref("");
const sessionId = ref("");
const tables = ref([]);
const columns = ref({});

// ---------- 测试连接 ----------
async function testConnection() {
  step.value = "testing";
  statusText.value = "正在测试连接...";
  errorText.value = "";

  try {
    const resp = await fetch(`${API_BASE}/api/datasource/db/test`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        type: dbType.value,
        host: form.host,
        port: parseInt(form.port) || 5236,
        user: form.user,
        password: form.password,
        schema: form.schema,
      }),
    });
    const data = await resp.json();
    if (data.success) {
      statusText.value = "连接测试成功";
      step.value = "form";
    } else {
      throw new Error(data.message || "连接测试失败");
    }
  } catch (err) {
    step.value = "error";
    errorText.value = err.message || "网络请求失败";
  }
}

// ---------- 建立连接 ----------
async function connectDb() {
  step.value = "connecting";
  statusText.value = "正在建立连接...";
  errorText.value = "";

  try {
    const resp = await fetch(`${API_BASE}/api/datasource/db/connect`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        type: dbType.value,
        host: form.host,
        port: parseInt(form.port) || 5236,
        user: form.user,
        password: form.password,
        schema: form.schema,
      }),
    });
    if (!resp.ok) {
      const errData = await resp.json().catch(() => ({}));
      throw new Error(errData.detail || "连接失败");
    }
    const data = await resp.json();
    sessionId.value = data.session_id;
    statusText.value = "连接成功，正在获取表结构...";
    await fetchTables();
  } catch (err) {
    step.value = "error";
    errorText.value = err.message || "连接请求失败";
  }
}

// ---------- 获取表列表 ----------
async function fetchTables() {
  step.value = "fetching_tables";
  statusText.value = "正在获取表列表...";

  try {
    const resp = await fetch(
      `${API_BASE}/api/datasource/db/tables?session_id=${encodeURIComponent(sessionId.value)}`
    );
    if (!resp.ok) {
      const errData = await resp.json().catch(() => ({}));
      throw new Error(errData.detail || "获取表列表失败");
    }
    const data = await resp.json();
    tables.value = data.tables || [];

    if (tables.value.length === 0) {
      statusText.value = "数据库中未找到表";
      step.value = "form";
      return;
    }

    await fetchAllColumns();
  } catch (err) {
    step.value = "error";
    errorText.value = err.message || "获取表列表失败";
  }
}

// ---------- 获取所有表的所有列 ----------
async function fetchAllColumns() {
  step.value = "fetching_columns";
  statusText.value = "正在获取列信息...";

  const cols = {};
  try {
    for (const table of tables.value) {
      const tableName = table.name || table;
      const resp = await fetch(
        `${API_BASE}/api/datasource/db/tables/${encodeURIComponent(tableName)}/columns?session_id=${encodeURIComponent(sessionId.value)}`
      );
      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        throw new Error(errData.detail || `获取表 ${tableName} 列信息失败`);
      }
      const data = await resp.json();
      cols[tableName] = data.columns || [];
    }
    columns.value = cols;
    step.value = "ready";

    // 通知父组件预览已就绪
    emit("preview-ready", {
      source_id: sessionId.value,
      tables: tables.value,
      columns: cols,
      sourceType: "db",
    });
  } catch (err) {
    step.value = "error";
    errorText.value = err.message || "获取列信息失败";
  }
}

// ---------- 关闭 ----------
function handleClose() {
  emit("close");
}

// ---------- 是否正在加载 ----------
const isLoading = ref(false);
</script>

<template>
  <div class="db-overlay" @click.self="handleClose">
    <div class="db-dialog" @click.stop>
      <!-- 头部 -->
      <div class="db-header">
        <div class="db-header-left">
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <ellipse cx="12" cy="5" rx="9" ry="3"/>
            <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/>
            <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>
          </svg>
          <h2>连接数据库</h2>
        </div>
        <button class="db-close" @click="handleClose">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </div>

      <!-- 加载状态 -->
      <div v-if="step !== 'form' && step !== 'error'" class="db-status-area">
        <div class="db-spinner"></div>
        <p class="db-status-text">{{ statusText }}</p>
      </div>

      <!-- 错误状态 -->
      <div v-if="step === 'error'" class="db-error-area">
        <div class="db-error-box">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
          </svg>
          <span>{{ errorText }}</span>
        </div>
        <div class="db-error-actions">
          <button class="db-btn db-btn-secondary" @click="step = 'form'; errorText = ''">返回修改</button>
        </div>
      </div>

      <!-- 表单 -->
      <div v-show="step === 'form' || step === 'error'" class="db-body">
        <div class="db-form">
          <!-- 数据库类型 -->
          <div class="db-form-group">
            <label class="db-label">数据库类型</label>
            <div class="db-type-selector">
              <label
                class="db-type-option"
                :class="{ active: dbType === 'sim_dameng' }"
              >
                <input type="radio" v-model="dbType" value="sim_dameng" />
                <div class="db-type-content">
                  <span class="db-type-name">模拟达梦</span>
                  <span class="db-type-hint">内置 SQLite 模拟数据库</span>
                </div>
              </label>
              <label
                class="db-type-option"
                :class="{ active: dbType === 'dameng' }"
              >
                <input type="radio" v-model="dbType" value="dameng" />
                <div class="db-type-content">
                  <span class="db-type-name">真实达梦</span>
                  <span class="db-type-hint">连接达梦数据库实例</span>
                </div>
              </label>
            </div>
          </div>

          <!-- 连接参数 -->
          <div class="db-form-row">
            <div class="db-form-group db-col-half">
              <label class="db-label">主机地址</label>
              <input
                v-model="form.host"
                class="db-input"
                type="text"
                placeholder="127.0.0.1"
              />
            </div>
            <div class="db-form-group db-col-half">
              <label class="db-label">端口</label>
              <input
                v-model="form.port"
                class="db-input"
                type="text"
                placeholder="5236"
              />
            </div>
          </div>

          <div class="db-form-row">
            <div class="db-form-group db-col-half">
              <label class="db-label">用户名</label>
              <input
                v-model="form.user"
                class="db-input"
                type="text"
                placeholder="用户名"
              />
            </div>
            <div class="db-form-group db-col-half">
              <label class="db-label">密码</label>
              <input
                v-model="form.password"
                class="db-input"
                type="password"
                placeholder="密码"
              />
            </div>
          </div>

          <div class="db-form-group">
            <label class="db-label">Schema</label>
            <input
              v-model="form.schema"
              class="db-input"
              type="text"
              placeholder="可选，留空则使用默认"
            />
          </div>
        </div>

        <!-- 状态提示 -->
        <div v-if="statusText && step === 'form'" class="db-status-hint" :class="{ success: statusText.includes('成功') }">
          {{ statusText }}
        </div>

        <!-- 操作按钮 -->
        <div class="db-actions">
          <button class="db-btn db-btn-outline" @click="testConnection" :disabled="step === 'testing'">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
              <polyline points="22 4 12 14.01 9 11.01"/>
            </svg>
            {{ step === 'testing' ? '测试中...' : '测试连接' }}
          </button>
          <button class="db-btn db-btn-primary" @click="connectDb" :disabled="step === 'connecting'">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M5 12h14"/><path d="M12 5l7 7-7 7"/>
            </svg>
            {{ step === 'connecting' ? '连接中...' : '连接' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* ======================== 变量 ======================== */
.db-overlay {
  --color-primary: #2563eb;
  --color-primary-dark: #1d4ed8;
  --color-primary-bg: #eff6ff;
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
.db-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.5);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 150;
  animation: db-overlay-in 0.15s ease-out;
}

@keyframes db-overlay-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

/* ---------- 弹窗卡片 ---------- */
.db-dialog {
  background: #ffffff;
  border-radius: var(--radius-xl);
  width: 520px;
  max-width: 95vw;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: var(--shadow-xl);
  animation: db-dialog-in 0.2s ease-out;
}

@keyframes db-dialog-in {
  from { opacity: 0; transform: scale(0.95) translateY(10px); }
  to { opacity: 1; transform: scale(1) translateY(0); }
}

/* ---------- 头部 ---------- */
.db-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 22px 26px 18px 26px;
  border-bottom: 1px solid #f1f5f9;
}

.db-header-left {
  display: flex;
  align-items: center;
  gap: 12px;
  color: #2563eb;
}

.db-header-left h2 {
  margin: 0;
  font-size: 17px;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.01em;
}

.db-close {
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

.db-close:hover {
  background: #f1f5f9;
  border-color: #e2e8f0;
  color: #475569;
}

/* ---------- 加载状态 ---------- */
.db-status-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 24px;
  gap: 16px;
}

.db-spinner {
  width: 36px;
  height: 36px;
  border: 3px solid #e2e8f0;
  border-top-color: #2563eb;
  border-radius: 50%;
  animation: db-spin 0.7s linear infinite;
}

@keyframes db-spin {
  to { transform: rotate(360deg); }
}

.db-status-text {
  margin: 0;
  font-size: 14px;
  color: #64748b;
  font-weight: 500;
}

/* ---------- 错误 ---------- */
.db-error-area {
  padding: 24px 26px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.db-error-box {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 14px 16px;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: var(--radius-md);
  color: #dc2626;
  font-size: 14px;
  font-weight: 500;
  line-height: 1.5;
}

.db-error-box svg {
  flex-shrink: 0;
  margin-top: 1px;
}

/* ---------- 表单体 ---------- */
.db-body {
  padding: 20px 26px 24px 26px;
}

.db-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.db-form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.db-form-row {
  display: flex;
  gap: 12px;
}

.db-col-half {
  flex: 1;
}

.db-label {
  font-size: 13px;
  font-weight: 600;
  color: #475569;
  letter-spacing: 0.01em;
}

.db-input {
  width: 100%;
  padding: 10px 14px;
  border: 1px solid #cbd5e1;
  border-radius: var(--radius-md);
  font-size: 14px;
  color: #0f172a;
  background: #f8fafc;
  outline: none;
  transition: all 0.2s ease;
  box-sizing: border-box;
  font-family: inherit;
}

.db-input:focus {
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.15);
  background: #ffffff;
}

.db-input::placeholder {
  color: #94a3b8;
}

/* ---------- 数据库类型选择器 ---------- */
.db-type-selector {
  display: flex;
  gap: 10px;
}

.db-type-option {
  flex: 1;
  padding: 12px 14px;
  border: 1.5px solid #e2e8f0;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all 0.2s ease;
  background: #f8fafc;
}

.db-type-option:hover {
  border-color: #cbd5e1;
  background: #f1f5f9;
}

.db-type-option.active {
  border-color: #bfdbfe;
  background: #eff6ff;
}

.db-type-option input[type="radio"] {
  display: none;
}

.db-type-content {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.db-type-name {
  font-size: 13.5px;
  font-weight: 600;
  color: #0f172a;
}

.db-type-hint {
  font-size: 11.5px;
  color: #94a3b8;
  font-weight: 500;
}

.db-type-option.active .db-type-name {
  color: #1e40af;
}

.db-type-option.active .db-type-hint {
  color: #64748b;
}

/* ---------- 状态提示 ---------- */
.db-status-hint {
  padding: 10px 14px;
  margin-top: 14px;
  background: #fff7ed;
  border: 1px solid #fed7aa;
  border-radius: var(--radius-md);
  font-size: 13px;
  color: #c2410c;
  font-weight: 500;
}

.db-status-hint.success {
  background: #f0fdf4;
  border-color: #bbf7d0;
  color: #15803d;
}

/* ---------- 按钮 ---------- */
.db-actions {
  display: flex;
  gap: 12px;
  margin-top: 20px;
}

.db-error-actions {
  display: flex;
  justify-content: flex-end;
}

.db-btn {
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

.db-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.db-btn-primary {
  flex: 1;
  background: #2563eb;
  color: #ffffff;
  box-shadow: 0 4px 6px -1px rgba(37, 99, 235, 0.2);
}

.db-btn-primary:hover:not(:disabled) {
  background: #1d4ed8;
  box-shadow: 0 6px 8px -1px rgba(37, 99, 235, 0.3);
  transform: translateY(-1px);
}

.db-btn-outline {
  background: transparent;
  color: #2563eb;
  border-color: #bfdbfe;
}

.db-btn-outline:hover:not(:disabled) {
  background: #eff6ff;
}

.db-btn-secondary {
  background: #f1f5f9;
  color: #1e293b;
  border-color: #cbd5e1;
}

.db-btn-secondary:hover:not(:disabled) {
  background: #e2e8f0;
  color: #0f172a;
}
</style>
