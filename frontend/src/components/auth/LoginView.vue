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

<style scoped>
</style>
