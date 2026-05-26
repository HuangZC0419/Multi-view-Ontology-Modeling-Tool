<script setup>
import { ref } from "vue";

const emit = defineEmits(["login-success"]);

const username = ref("");
const password = ref("");
const loading = ref(false);
const errorMsg = ref("");

async function handleLogin() {
  errorMsg.value = "";
  if (!username.value.trim() || !password.value.trim()) {
    errorMsg.value = "请输入用户名和密码";
    return;
  }
  loading.value = true;
  try {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: username.value.trim(),
        password: password.value,
      }),
    });
    const data = await res.json();
    if (data.success) {
      emit("login-success", {
        token: data.token,
        username: data.username,
        name: data.name,
        role: data.role,
      });
    } else {
      errorMsg.value = data.message || "登录失败";
    }
  } catch (e) {
    errorMsg.value = "网络错误，请确认后端服务已启动";
  } finally {
    loading.value = false;
  }
}

</script>

<template>
  <div class="login-shell">
    <div class="login-card">
      <!-- 左侧品牌区 -->
      <div class="brand-side">
        <div class="brand-inner">
          <div class="brand-logo">
            <svg viewBox="0 0 48 48" fill="none" stroke="#2563eb" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="24" cy="8" r="5"/>
              <circle cx="10" cy="38" r="5"/>
              <circle cx="38" cy="38" r="5"/>
              <line x1="20.5" y1="11.4" x2="13.5" y2="33.5"/>
              <line x1="27.5" y1="11.4" x2="34.5" y2="33.5"/>
              <line x1="16" y1="38" x2="32" y2="38"/>
            </svg>
          </div>
          <h1>本体建模系统</h1>
          <p class="brand-desc">ONTOLOGY MODELING SYSTEM</p>
        </div>
      </div>

      <!-- 右侧表单区 -->
      <div class="form-side">
        <div class="form-card">
          <div class="form-header">
            <h2>欢迎回来</h2>
            <p>登录以访问您的工作台</p>
          </div>

          <form @submit.prevent="handleLogin">
            <label for="username">用户名</label>
            <input
              id="username"
              v-model="username"
              name="username"
              type="text"
              placeholder="输入用户名"
              autocomplete="username"
              @keyup.enter="handleLogin"
            />

            <label for="password">密码</label>
            <input
              id="password"
              v-model="password"
              name="password"
              type="password"
              placeholder="输入密码"
              autocomplete="current-password"
              @keyup.enter="handleLogin"
            />

            <div v-if="errorMsg" class="form-error">{{ errorMsg }}</div>

            <button type="submit" :disabled="loading">
              <template v-if="!loading">登 录</template>
              <template v-else>
                <span class="spinner"></span> 验证中...
              </template>
            </button>
          </form>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.login-shell {
  width: 100vw;
  height: 100vh;
  padding: 8px;
  background: #f8fafc;
  box-sizing: border-box;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, "Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif;
}

.login-card {
  display: flex;
  width: 100%;
  height: 100%;
  background: #ffffff;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -1px rgba(0,0,0,0.06);
  border: 1px solid #e2e8f0;
}

/* ======== 左侧品牌区 ======== */
.brand-side {
  flex: 0 0 40%;
  background: #f1f5f9;
  display: flex;
  align-items: flex-start;
  padding: 48px 44px;
}

.brand-logo {
  width: 48px;
  height: 48px;
  margin-bottom: 16px;
}

.brand-logo svg {
  width: 48px;
  height: 48px;
}

.brand-inner h1 {
  margin: 0 0 4px 0;
  font-size: 22px;
  font-weight: 700;
  color: #1e293b;
  letter-spacing: -0.025em;
}

.brand-desc {
  margin: 0;
  font-size: 11px;
  font-weight: 500;
  color: #64748b;
  letter-spacing: 0.08em;
}

/* ======== 右侧表单区 ======== */
.form-side {
  flex: 1 1 auto;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
}

.form-card {
  width: 340px;
  max-width: 100%;
}

.form-header {
  margin-bottom: 28px;
}

.form-header h2 {
  margin: 0 0 4px 0;
  font-size: 1.15rem;
  font-weight: 600;
  color: #1e293b;
}

.form-header p {
  margin: 0;
  font-size: 0.875rem;
  color: #64748b;
}

/* 表单元素 — 对齐 RAG 设计系统 */
form {
  display: flex;
  flex-direction: column;
}

label {
  display: flex;
  flex-direction: column;
  font-size: 0.875rem;
  font-weight: 500;
  color: #64748b;
  gap: 6px;
  margin-bottom: 14px;
}

input {
  font-family: inherit;
  font-size: 0.95rem;
  padding: 8px 14px;
  min-height: 44px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background-color: #f8fafc;
  color: #1e293b;
  outline: none;
  transition: all 0.2s ease;
  box-sizing: border-box;
  width: 100%;
}

input::placeholder {
  color: #94a3b8;
}

input:focus {
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37,99,235,0.1);
  background-color: #ffffff;
}

.form-error {
  padding: 10px 14px;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 8px;
  font-size: 0.875rem;
  font-weight: 500;
  color: #dc2626;
  text-align: center;
  margin-bottom: 14px;
}

button {
  font-family: inherit;
  font-weight: 600;
  font-size: 0.95rem;
  padding: 8px 20px;
  min-height: 44px;
  background-color: #2563eb;
  color: #ffffff;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
  margin-top: 4px;
}

button:hover:not(:disabled) {
  background-color: #1d4ed8;
  transform: translateY(-1px);
}

button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.spinner {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: #ffffff;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ======== 响应式 ======== */
@media (max-width: 768px) {
  .login-card {
    flex-direction: column;
  }

  .brand-side {
    flex: 0 0 auto;
    padding: 28px 24px;
  }

  .brand-logo {
    width: 36px;
    height: 36px;
    margin-bottom: 10px;
  }

  .brand-logo svg {
    width: 36px;
    height: 36px;
  }

  .brand-inner h1 {
    font-size: 18px;
  }

  .brand-desc {
    font-size: 10px;
  }

  .form-side {
    flex: 1 1 auto;
    align-items: flex-start;
    padding: 24px;
  }

  .form-card {
    width: 100%;
  }
}

@media (max-width: 480px) {
  .login-shell {
    padding: 4px;
  }

  .login-card {
    border-radius: 8px;
  }

  .brand-side {
    padding: 20px 18px;
  }

  .form-side {
    padding: 18px;
  }
}
</style>
