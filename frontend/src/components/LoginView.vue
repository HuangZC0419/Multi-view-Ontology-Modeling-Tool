<script setup>
import { ref } from "vue";

const emit = defineEmits(["login-success"]);

const API_BASE = import.meta.env.VITE_API_BASE || "";

const username = ref("");
const password = ref("");
const loading = ref(false);
const error = ref("");

async function handleLogin() {
  if (!username.value.trim() || !password.value.trim()) {
    error.value = "请输入用户名和密码";
    return;
  }
  loading.value = true;
  error.value = "";
  try {
    const resp = await fetch(`${API_BASE}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: username.value.trim(),
        password: password.value,
      }),
    });
    const data = await resp.json();
    if (data.success) {
      emit("login-success", {
        token: data.token,
        username: data.username,
        name: data.name,
        role: data.role,
      });
    } else {
      error.value = data.message || "登录失败，请检查用户名和密码";
    }
  } catch (e) {
    error.value = "网络错误，请稍后重试";
  } finally {
    loading.value = false;
  }
}

function onKeyup(e) {
  if (e.key === "Enter") handleLogin();
}
</script>

<template>
  <div class="login-container">
    <div class="login-card">
      <!-- 系统 Logo / 名称 -->
      <div class="login-header">
        <div class="login-logo">
          <svg
            viewBox="0 0 24 24"
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
        </div>
        <h1 class="login-title">本体建模系统</h1>
        <p class="login-subtitle">登录您的账号以继续</p>
      </div>

      <!-- 登录表单 -->
      <form class="login-form" @submit.prevent="handleLogin">
        <!-- 错误提示 -->
        <div v-if="error" class="login-error">
          <svg
            viewBox="0 0 24 24"
            width="16"
            height="16"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
          >
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
          <span>{{ error }}</span>
        </div>

        <!-- 用户名 -->
        <div class="input-group">
          <label class="input-label" for="login-username">用户名</label>
          <div class="input-wrapper">
            <svg
              class="input-icon"
              viewBox="0 0 24 24"
              width="18"
              height="18"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
              <circle cx="12" cy="7" r="4" />
            </svg>
            <input
              id="login-username"
              v-model="username"
              type="text"
              class="input-field"
              placeholder="请输入用户名"
              autocomplete="username"
              :disabled="loading"
              @keyup="onKeyup"
            />
          </div>
        </div>

        <!-- 密码 -->
        <div class="input-group">
          <label class="input-label" for="login-password">密码</label>
          <div class="input-wrapper">
            <svg
              class="input-icon"
              viewBox="0 0 24 24"
              width="18"
              height="18"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
              <path d="M7 11V7a5 5 0 0 1 10 0v4" />
            </svg>
            <input
              id="login-password"
              v-model="password"
              type="password"
              class="input-field"
              placeholder="请输入密码"
              autocomplete="current-password"
              :disabled="loading"
              @keyup="onKeyup"
            />
          </div>
        </div>

        <!-- 登录按钮 -->
        <button
          type="submit"
          class="login-button"
          :class="{ loading }"
          :disabled="loading"
        >
          <span v-if="loading" class="button-spinner"></span>
          <svg
            v-else
            viewBox="0 0 24 24"
            width="18"
            height="18"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <polyline points="9 10 4 15 9 20" />
            <path d="M20 4v7a4 4 0 0 1-4 4H4" />
          </svg>
          <span>{{ loading ? "登录中..." : "登 录" }}</span>
        </button>
      </form>
    </div>
  </div>
</template>

<style scoped>
.login-container {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: #f8fafc;
  padding: 24px;
}

.login-card {
  width: 100%;
  max-width: 420px;
  background: #ffffff;
  border-radius: 12px;
  box-shadow:
    0 1px 3px rgba(0, 0, 0, 0.06),
    0 4px 16px rgba(0, 0, 0, 0.04);
  padding: 40px 36px;
}

/* ======================== Header ======================== */

.login-header {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-bottom: 32px;
}

.login-logo {
  width: 56px;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 14px;
  background: linear-gradient(135deg, #1e3a5f, #2563eb);
  color: #ffffff;
  margin-bottom: 16px;
  box-shadow: 0 4px 12px rgba(30, 58, 95, 0.2);
}

.login-logo svg {
  width: 30px;
  height: 30px;
}

.login-title {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
  color: #1e3a5f;
  letter-spacing: 0.02em;
}

.login-subtitle {
  margin: 6px 0 0;
  font-size: 13px;
  color: #94a3b8;
  font-weight: 400;
}

/* ======================== Form ======================== */

.login-form {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

/* ======================== Error ======================== */

.login-error {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-left: 3px solid #ef4444;
  border-radius: 8px;
  color: #dc2626;
  font-size: 13px;
  font-weight: 500;
}

.login-error svg {
  flex-shrink: 0;
  color: #ef4444;
}

/* ======================== Input Group ======================== */

.input-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.input-label {
  font-size: 13px;
  font-weight: 600;
  color: #334155;
}

.input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}

.input-icon {
  position: absolute;
  left: 14px;
  color: #94a3b8;
  pointer-events: none;
}

.input-field {
  width: 100%;
  padding: 11px 14px 11px 42px;
  border: 1.5px solid #e2e8f0;
  border-radius: 10px;
  background: #f8fafc;
  font-size: 14px;
  font-family: inherit;
  color: #1e293b;
  outline: none;
  transition: border-color 0.2s ease, background 0.2s ease, box-shadow 0.2s ease;
}

.input-field::placeholder {
  color: #cbd5e1;
}

.input-field:focus {
  border-color: #2563eb;
  background: #ffffff;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.08);
}

.input-field:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* ======================== Button ======================== */

.login-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  padding: 12px 20px;
  margin-top: 4px;
  border: none;
  border-radius: 10px;
  background: #1e3a5f;
  color: #ffffff;
  font-size: 15px;
  font-weight: 600;
  font-family: inherit;
  letter-spacing: 0.04em;
  cursor: pointer;
  transition:
    background 0.2s ease,
    transform 0.2s ease,
    box-shadow 0.2s ease;
}

.login-button:hover:not(:disabled) {
  background: #162e4a;
  transform: translateY(-1px);
  box-shadow:
    0 4px 12px rgba(30, 58, 95, 0.25),
    0 2px 4px rgba(30, 58, 95, 0.1);
}

.login-button:active:not(:disabled) {
  transform: translateY(0);
}

.login-button:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.login-button.loading {
  background: #334155;
}

/* ======================== Spinner ======================== */

.button-spinner {
  width: 18px;
  height: 18px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #ffffff;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* ======================== 响应式 ======================== */

@media (max-width: 480px) {
  .login-container {
    padding: 16px;
  }

  .login-card {
    padding: 32px 24px;
  }

  .login-title {
    font-size: 20px;
  }
}
</style>
