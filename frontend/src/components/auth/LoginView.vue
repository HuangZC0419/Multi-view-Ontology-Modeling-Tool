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

function onKeyup(e) {
  if (e.key === "Enter") handleLogin();
}
</script>

<template>
</template>

<style>
</style>

<style scoped>
</style>
