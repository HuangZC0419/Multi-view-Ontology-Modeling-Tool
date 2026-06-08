<script setup>
import { ref } from "vue";
import OceanBreath from "../OceanBreath.vue";
import coverImage from "../../assets/封面图片.png";

const emit = defineEmits(["login-success"]);

const username = ref("");
const password = ref("");
const loading = ref(false);
const loginError = ref("");

async function handleLogin() {
  loginError.value = "";
  if (!username.value.trim() || !password.value.trim()) {
    loginError.value = "请输入用户名和密码";
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
      loginError.value = data.message || "登录失败";
    }
  } catch (e) {
    loginError.value = "网络错误，请确认后端服务已启动";
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="modern-login-page">
    <header class="modern-header">
      <div class="modern-logo">
        <svg class="logo-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="18" cy="5" r="3"/>
          <circle cx="6" cy="12" r="3"/>
          <circle cx="18" cy="19" r="3"/>
          <line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/>
          <line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/>
        </svg>
        <span class="logo-text">SCU</span>
      </div>
      <nav class="modern-nav">
        <a href="#" class="active">首页</a>
        <a href="/help.html">文档中心</a>
      </nav>
      <div class="modern-actions">
        <button class="modern-icon-btn" type="button" aria-label="设置">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="3"/>
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V22a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.6 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.6a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
          </svg>
        </button>
      </div>
    </header>

    <main class="modern-main">
      <OceanBreath :speed="0.7" :intensity="0.6" theme="day" :density="1.0" />

      <div class="modern-content">
        <div class="modern-left">
          <div class="user-badge-top">
            <span class="badge-icon">&#x2B50;</span> 自研本体建模分析工具
          </div>
          <h1 class="modern-title">本体建模系统</h1>
          <p class="modern-subtitle">专注于关系建模分析，实现多视角可视化。</p>

          <div class="modern-features">
            <div class="feature-item">
              <span class="feature-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
                  <path d="M3.3 7l8.7 5 8.7-5" />
                  <path d="M12 22V12" />
                </svg>
              </span>
              <div class="feature-text">
                <div class="feature-title">高效建模</div>
                <div class="feature-desc">智能工具提升建模效率</div>
              </div>
            </div>
            <div class="feature-item">
              <span class="feature-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M12 2l7 4v6c0 5-3 9-7 10-4-1-7-5-7-10V6l7-4z" />
                  <path d="M9 12l2 2 4-4" />
                </svg>
              </span>
              <div class="feature-text">
                <div class="feature-title">精准控制</div>
                <div class="feature-desc">规则引擎与精确可视化</div>
              </div>
            </div>
          </div>

          <form @submit.prevent="handleLogin" class="modern-login-form">
            <div class="modern-field" :class="{ disabled: loading }">
              <span class="field-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                  <circle cx="12" cy="7" r="4"/>
                </svg>
              </span>
              <input
                type="text"
                v-model="username"
                placeholder="用户名"
                required
                class="modern-input"
                :disabled="loading"
                autocomplete="username"
              />
            </div>
            <div class="modern-field" :class="{ disabled: loading }">
              <span class="field-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
                  <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                </svg>
              </span>
              <input
                type="password"
                v-model="password"
                placeholder="密码"
                required
                class="modern-input"
                :disabled="loading"
                autocomplete="current-password"
              />
            </div>
            <button type="submit" class="modern-btn-primary" :disabled="loading">
              <span class="btn-text">{{ loading ? "登录中..." : "登录系统" }}</span>
              <svg class="btn-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M5 12h12"/>
                <path d="M13 6l6 6-6 6"/>
              </svg>
            </button>
            <p v-if="loginError" class="modern-login-error">{{ loginError }}</p>
          </form>

          <div class="modern-status">
            <span class="status-left"><span class="status-dot"></span> 系统运行正常 · 四川大学开发 v1.2.4</span>
          </div>
        </div>

        <div class="modern-right">
          <div class="modern-image-container">
            <div class="peach-gradient"></div>
            <img :src="coverImage" alt="封面图片" class="modern-profile-img" />
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<style scoped>
.modern-login-page {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background-color: var(--bg-elevated);
  z-index: 9999;
  display: flex;
  flex-direction: column;
  overflow-x: hidden;
  overflow-y: auto;
  font-family: 'Inter', sans-serif;
}

/* ===== Header / Nav Bar ===== */
.modern-header {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1.5rem 2rem;
  position: relative;
  z-index: 10;
}

.modern-logo {
  position: absolute;
  left: 2rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0 0.8rem;
  height: 32px;
  background-color: var(--primary-active);
  color: var(--text-inverse);
  border-radius: 6px;
  font-weight: bold;
  font-size: 1rem;
  letter-spacing: 0.05em;
}

.logo-svg {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
}

.logo-text {
  white-space: nowrap;
}

.modern-nav {
  display: flex;
  gap: 2rem;
  background: var(--surface);
  padding: 0.5rem 1.5rem;
  border-radius: 99px;
  backdrop-filter: blur(10px);
  border: 1px solid var(--border);
}

.modern-nav a {
  text-decoration: none;
  color: var(--text-muted);
  font-size: 0.9rem;
  font-weight: 500;
  transition: color 0.2s;
}

.modern-nav a.active,
.modern-nav a:hover {
  color: var(--text-main);
}

.modern-actions {
  position: absolute;
  right: 2rem;
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.modern-icon-btn {
  width: 34px;
  height: 34px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text-main);
  cursor: pointer;
  backdrop-filter: blur(10px);
  transition: transform 0.15s ease, background 0.15s ease;
}

.modern-icon-btn svg {
  width: 18px;
  height: 18px;
}

.modern-icon-btn:hover {
  transform: translateY(-1px);
  background: var(--surface-solid);
}

/* ===== Main Layout ===== */
.modern-main {
  position: relative;
  flex: 1;
  padding: 0 4rem 2.25rem;
  max-width: 1440px;
  margin: 0 auto;
  width: 100%;
  background: var(--content-hero-gradient);
}

.modern-content {
  position: relative;
  z-index: 10;
  display: grid;
  grid-template-columns: 1.05fr 0.95fr;
  grid-template-rows: 1fr auto;
  align-items: center;
  gap: 2.5rem;
  min-height: calc(100vh - 96px);
}

.modern-left {
  max-width: 600px;
  padding-right: 4rem;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

/* ===== Badge ===== */
.user-badge-top {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.85rem;
  color: var(--text-muted);
  margin-bottom: 1.5rem;
  background: var(--surface-muted);
  padding: 0.4rem 0.8rem;
  border-radius: 99px;
  width: fit-content;
}

/* ===== Title ===== */
.modern-title {
  font-size: clamp(3rem, 5vw, 4.5rem);
  line-height: 1.1;
  font-weight: 700;
  color: var(--text-main);
  margin: 0 0 1.5rem 0;
  letter-spacing: -0.03em;
}

.modern-italic {
  font-family: "Georgia", "Times New Roman", serif;
  font-style: italic;
  font-weight: 400;
  color: var(--text-muted);
}

/* ===== Subtitle ===== */
.modern-subtitle {
  font-size: 1.1rem;
  line-height: 1.6;
  color: var(--text-muted);
  margin: 0 0 2.5rem 0;
  max-width: 90%;
}

.modern-features {
  display: flex;
  gap: 0.9rem;
  flex-wrap: wrap;
  margin-bottom: 1.4rem;
}

.feature-item {
  display: inline-flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.65rem 0.85rem;
  border: 1px solid var(--border);
  border-radius: 14px;
  background: var(--surface-muted);
  backdrop-filter: blur(10px);
  box-shadow: var(--shadow-soft);
  min-width: 180px;
}

.feature-icon {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--primary-light);
  color: var(--primary);
  border: 1px solid rgba(0, 0, 0, 0.04);
  flex-shrink: 0;
}

.feature-icon svg {
  width: 18px;
  height: 18px;
}

.feature-title {
  font-size: 0.92rem;
  font-weight: 600;
  color: var(--text-main);
  line-height: 1.1;
}

.feature-desc {
  font-size: 0.78rem;
  color: var(--text-muted);
  margin-top: 0.12rem;
  line-height: 1.25;
}

/* ===== Login Form ===== */
.modern-login-form {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.9rem;
  align-items: stretch;
  margin-bottom: 0.85rem;
}

.modern-input {
  width: 100%;
  border: none;
  outline: none;
  font-size: 1.06rem;
  background: transparent;
  font-family: inherit;
  color: var(--text-main);
}

.modern-field {
  height: 58px;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0 1.05rem;
  border: 2px solid var(--border-strong);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.88);
  box-shadow: var(--shadow-sm);
  transition: border-color 0.2s, box-shadow 0.2s;
}

.modern-field:focus-within {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px var(--focus-ring);
}

.modern-field.disabled {
  opacity: 0.75;
}

.field-icon {
  width: 20px;
  height: 20px;
  color: var(--text-muted);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.field-icon svg {
  width: 20px;
  height: 20px;
}

.modern-input::placeholder {
  color: var(--text-muted);
}

.modern-input:disabled {
  cursor: not-allowed;
}

.modern-btn-primary {
  height: 58px;
  padding: 0 1.2rem 0 1.35rem;
  display: inline-flex;
  align-items: center;
  gap: 0.6rem;
  background: var(--primary);
  color: var(--text-inverse);
  border: none;
  border-radius: 16px;
  font-size: 1.06rem;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.2s, background 0.2s;
  white-space: nowrap;
  font-family: inherit;
  grid-column: 1 / -1;
}

.modern-btn-primary:hover:not(:disabled) {
  background: var(--primary-hover);
  transform: translateY(-1px);
}

.modern-btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-arrow {
  width: 18px;
  height: 18px;
}

.modern-login-error {
  width: 100%;
  color: var(--danger);
  font-size: 0.9rem;
  margin-top: 0;
  grid-column: 1 / -1;
}

.modern-status {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 1rem;
  font-size: 0.85rem;
  color: var(--text-muted);
  margin-bottom: 2rem;
}

.status-left {
  display: inline-flex;
  align-items: center;
  gap: 0.55rem;
}

.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: #23a26d;
  box-shadow: 0 0 0 4px rgba(35, 162, 109, 0.16);
}


/* ===== Right-side Image ===== */
.modern-right {
  height: 100%;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
}

.modern-image-container {
  position: relative;
  width: 100%;
  height: 80vh;
  max-height: 800px;
  border-radius: 24px;
  overflow: hidden;
  isolation: isolate;
  background: var(--login-card-gradient);
}

.peach-gradient {
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  background: var(--login-image-overlay);
  z-index: 1;
}

.modern-profile-img {
  position: absolute;
  bottom: 0;
  right: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: 62% center;
  z-index: 2;
}

/* ===== Responsive ===== */
@media (max-width: 1024px) {
  .modern-main {
    padding: 2rem;
  }

  .modern-left {
    max-width: 100%;
    padding-right: 0;
    align-items: center;
    text-align: center;
  }

  .modern-subtitle {
    max-width: 100%;
  }

  .modern-login-form {
    width: 100%;
    max-width: 400px;
    grid-template-columns: 1fr;
  }

  .modern-input {
    width: 100%;
  }

  .modern-btn-primary {
    width: 100%;
  }

  .modern-right {
    width: 100%;
    max-height: 400px;
  }

  .modern-image-container {
    height: 100%;
    max-height: 400px;
  }

  .modern-content {
    grid-template-columns: 1fr;
    grid-template-rows: auto auto auto;
    gap: 2rem;
    min-height: auto;
  }
}

@media (max-width: 768px) {
  .modern-header {
    padding: 1rem;
  }

  .modern-logo {
    position: static;
    margin-right: auto;
  }

  .modern-actions {
    right: 1rem;
  }

  .modern-nav {
    gap: 1rem;
    padding: 0.45rem 1rem;
  }

  .modern-main {
    padding: 1.5rem;
  }

  .modern-title {
    font-size: 1.8rem;
  }

  .modern-right {
    display: none;
  }
}

@media (max-width: 480px) {
  .modern-main {
    padding: 1rem;
  }

  .modern-title {
    font-size: 1.5rem;
  }

  .modern-login-form {
    max-width: 320px;
    width: 100%;
  }

  .modern-input {
    min-width: 0;
    width: 100%;
  }
}
</style>
