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
    <!-- 背景光晕球体 -->
    <div class="bg-orb orb-1"></div>
    <div class="bg-orb orb-2"></div>
    <div class="bg-orb orb-3"></div>

    <!-- 浮动粒子 -->
    <div class="particle p-1"></div>
    <div class="particle p-2"></div>
    <div class="particle p-3"></div>
    <div class="particle p-4"></div>
    <div class="particle p-5"></div>
    <div class="particle p-6"></div>

    <!-- 主玻璃卡片 -->
    <div class="glass-card">
      <!-- 左侧品牌区 -->
      <div class="brand-zone">
        <div class="brand-icon-box">
          <svg class="brand-icon-svg" viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" role="img" aria-label="本体建模系统图标">
            <circle cx="24" cy="8" r="5"/>
            <circle cx="10" cy="38" r="5"/>
            <circle cx="38" cy="38" r="5"/>
            <line x1="20.5" y1="11.4" x2="13.5" y2="33.5"/>
            <line x1="27.5" y1="11.4" x2="34.5" y2="33.5"/>
            <line x1="16" y1="38" x2="32" y2="38"/>
          </svg>
        </div>
        <h1>本体建模系统</h1>
        <p class="brand-sub">ONTOLOGY MODELING SYSTEM</p>
      </div>

      <!-- 右侧表单区 -->
      <div class="form-zone">
        <form class="login-form" @submit.prevent="handleLogin">
          <div class="field">
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
          </div>

          <div class="field">
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
          </div>

          <div v-if="errorMsg" class="form-error">{{ errorMsg }}</div>

          <button type="submit" class="submit-btn" :disabled="loading">
            <template v-if="!loading">登 录</template>
            <template v-else>
              <span class="spinner"></span> 验证中...
            </template>
          </button>
        </form>
      </div>
    </div>
  </div>
</template>

<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');
</style>

<style scoped>
/* ==========================================================
   全局与背景
   ========================================================== */
.login-shell {
  --primary: #2563eb;
  --primary-light: #3b82f6;
  --primary-dark: #1d4ed8;

  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100vw;
  height: 100vh;
  overflow: hidden;
  background: linear-gradient(135deg, #0f2744 0%, #1a3a6b 25%, #1e40af 50%, #2560d0 75%, #3075f0 100%);
  font-family: "Plus Jakarta Sans", "Noto Sans SC", "PingFang SC", "Microsoft YaHei", system-ui, -apple-system, sans-serif;
  -webkit-font-smoothing: antialiased;
}

/* 光晕球体 */
.bg-orb {
  position: absolute;
  border-radius: 50%;
  pointer-events: none;
}

.orb-1 {
  width: 500px;
  height: 500px;
  background: radial-gradient(circle, rgba(96,165,250,0.12) 0%, rgba(37,99,235,0.05) 40%, transparent 70%);
  top: 50%;
  left: 50%;
  transform: translate(-65%, -45%);
  animation: orb-breathe-1 8s ease-in-out infinite;
}

.orb-2 {
  width: 350px;
  height: 350px;
  background: radial-gradient(circle, rgba(147,197,253,0.08) 0%, rgba(59,130,246,0.03) 40%, transparent 70%);
  top: 50%;
  left: 50%;
  transform: translate(-25%, -55%);
  animation: orb-breathe-2 6s ease-in-out infinite;
}

.orb-3 {
  width: 250px;
  height: 250px;
  background: radial-gradient(circle, rgba(59,130,246,0.06) 0%, transparent 60%);
  bottom: -60px;
  right: -40px;
  animation: orb-drift 12s ease-in-out infinite alternate;
}

@keyframes orb-breathe-1 {
  0%, 100% { transform: translate(-65%, -45%) scale(1); opacity: 1; }
  50% { transform: translate(-65%, -45%) scale(1.08); opacity: 0.7; }
}

@keyframes orb-breathe-2 {
  0%, 100% { transform: translate(-25%, -55%) scale(1.05); opacity: 0.8; }
  50% { transform: translate(-25%, -55%) scale(0.95); opacity: 1; }
}

@keyframes orb-drift {
  0% { transform: translate(0, 0); }
  100% { transform: translate(-30px, -20px); }
}

/* 浮动粒子 */
.particle {
  position: absolute;
  border-radius: 50%;
  pointer-events: none;
}

.p-1 { width: 4px; height: 4px; background: rgba(147,197,253,0.5); top: 15%; left: 20%; box-shadow: 0 0 8px rgba(147,197,253,0.3); animation: float-1 7s ease-in-out infinite alternate; }
.p-2 { width: 3px; height: 3px; background: rgba(96,165,250,0.4); top: 22%; right: 25%; box-shadow: 0 0 6px rgba(96,165,250,0.25); animation: float-2 5s ease-in-out infinite alternate; }
.p-3 { width: 5px; height: 5px; background: rgba(59,130,246,0.35); bottom: 20%; left: 30%; box-shadow: 0 0 10px rgba(59,130,246,0.2); animation: float-3 9s ease-in-out infinite alternate; }
.p-4 { width: 3px; height: 3px; background: rgba(191,219,254,0.5); bottom: 28%; right: 20%; box-shadow: 0 0 6px rgba(191,219,254,0.3); animation: float-4 6s ease-in-out infinite alternate; }
.p-5 { width: 2px; height: 2px; background: rgba(147,197,253,0.4); top: 40%; right: 15%; box-shadow: 0 0 6px rgba(147,197,253,0.2); animation: float-5 8s ease-in-out infinite alternate; }
.p-6 { width: 4px; height: 4px; background: rgba(96,165,250,0.3); top: 60%; left: 22%; box-shadow: 0 0 8px rgba(96,165,250,0.15); animation: float-6 10s ease-in-out infinite alternate; }

@keyframes float-1 { 0% { transform: translate(0, 0); } 100% { transform: translate(30px, -20px); } }
@keyframes float-2 { 0% { transform: translate(0, 0); } 100% { transform: translate(-25px, 15px); } }
@keyframes float-3 { 0% { transform: translate(0, 0); } 100% { transform: translate(-20px, -25px); } }
@keyframes float-4 { 0% { transform: translate(0, 0); } 100% { transform: translate(20px, 20px); } }
@keyframes float-5 { 0% { transform: translate(0, 0); } 100% { transform: translate(-30px, -15px); } }
@keyframes float-6 { 0% { transform: translate(0, 0); } 100% { transform: translate(35px, 10px); } }
</style>
