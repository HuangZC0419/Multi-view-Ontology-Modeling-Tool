# 登录界面重新设计 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 LoginView.vue 从左右分栏+SVG动画改为全屏蓝色玻璃拟态居中宽卡片布局

**Architecture:** 单文件修改 — 重写 `<template>` 和 `<style>`，移除 SVG 动画 JS 代码，保留登录 API 逻辑不变。纯 CSS 实现背景渐变、光晕呼吸动画、浮动粒子和玻璃拟态卡片。

**Tech Stack:** Vue 3 SFC, 原生 CSS, Plus Jakarta Sans 字体

---

### Task 1: 移除旧代码，保留登录逻辑

**Files:**
- Modify: `frontend/src/components/auth/LoginView.vue`

**目标:** 删除 SVG 图谱动画相关的 JS 代码、旧模板、旧样式，只保留登录表单逻辑部分。

- [ ] **Step 1: 删除 `<script setup>` 中的图谱动画代码**

删除第 14-145 行（从 `// 知识图谱动画` 到 `onUnmounted` 结束），即移除：`graphCanvas`、`graphNodes`、`graphEdges`、`dynamicEdges`、`dynamicTimer`、`spawnDynamicEdge`、`animate` 函数、`onMounted`/`onUnmounted` 钩子中的所有图谱相关代码。

保留从 `// 登录逻辑` 开始的所有代码：`handleLogin`、`onKeyup`，以及 `ref` 导入、`emit` 声明、`username`、`password`、`loading`、`errorMsg`。

- [ ] **Step 2: 确认 `<script setup>` 最终内容**

最终 `<script setup>` 应只包含：

```js
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
        password: password.value.trim(),
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
```

- [ ] **Step 3: 提交**

```bash
git add frontend/src/components/auth/LoginView.vue
git commit -m "refactor(login): remove old SVG graph animation code, keep login logic"
```

---

### Task 2: 编写新模板

**Files:**
- Modify: `frontend/src/components/auth/LoginView.vue`

- [ ] **Step 1: 替换 `<template>` 为全屏居中卡片布局**

```html
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
          <svg class="brand-icon-svg" viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
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
              type="text"
              placeholder="输入用户名"
              autocomplete="username"
              @keyup="onKeyup"
            />
          </div>

          <div class="field">
            <label for="password">密码</label>
            <input
              id="password"
              v-model="password"
              type="password"
              placeholder="输入密码"
              autocomplete="current-password"
              @keyup="onKeyup"
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
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/components/auth/LoginView.vue
git commit -m "feat(login): new glassmorphism centered card template"
```

---

### Task 3: 编写背景与动画样式

**Files:**
- Modify: `frontend/src/components/auth/LoginView.vue`

- [ ] **Step 1: 替换 `<style>` 为新的完整样式**

先写全局、字体引入和背景动画部分：

```css
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
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
.p-5 { width: 2px; height: 2px; background: rgba(147,197,253,0.4); top: 40%; right: 15%; animation: float-5 8s ease-in-out infinite alternate; }
.p-6 { width: 4px; height: 4px; background: rgba(96,165,250,0.3); top: 60%; left: 22%; box-shadow: 0 0 8px rgba(96,165,250,0.15); animation: float-6 10s ease-in-out infinite alternate; }

@keyframes float-1 { 0% { transform: translate(0, 0); } 100% { transform: translate(30px, -20px); } }
@keyframes float-2 { 0% { transform: translate(0, 0); } 100% { transform: translate(-25px, 15px); } }
@keyframes float-3 { 0% { transform: translate(0, 0); } 100% { transform: translate(-20px, -25px); } }
@keyframes float-4 { 0% { transform: translate(0, 0); } 100% { transform: translate(20px, 20px); } }
@keyframes float-5 { 0% { transform: translate(0, 0); } 100% { transform: translate(-30px, -15px); } }
@keyframes float-6 { 0% { transform: translate(0, 0); } 100% { transform: translate(35px, 10px); } }
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/components/auth/LoginView.vue
git commit -m "feat(login): add background gradient, orb glow and particle animations"
```

---

### Task 4: 编写卡片与表单样式

**Files:**
- Modify: `frontend/src/components/auth/LoginView.vue`

- [ ] **Step 1: 在 `<style scoped>` 中追加卡片和表单样式**

```css
/* ==========================================================
   玻璃拟态卡片
   ========================================================== */
.glass-card {
  position: relative;
  z-index: 2;
  display: flex;
  align-items: center;
  gap: 40px;
  width: 540px;
  max-width: 92vw;
  padding: 40px 44px 36px;
  background: rgba(255,255,255,0.1);
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  border: 1px solid rgba(255,255,255,0.18);
  border-radius: 24px;
  box-shadow: 0 24px 80px rgba(0,0,0,0.25), 0 0 0 0.5px rgba(255,255,255,0.08) inset;
  animation: card-enter 0.6s ease-out;
}

@keyframes card-enter {
  from { opacity: 0; transform: translateY(20px); }
  to   { opacity: 1; transform: translateY(0); }
}

/* ==========================================================
   品牌区（左侧）
   ========================================================== */
.brand-zone {
  flex: 0 0 auto;
  text-align: center;
}

.brand-icon-box {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 56px;
  height: 56px;
  border-radius: 16px;
  background: linear-gradient(135deg, rgba(37,99,235,0.3), rgba(59,130,246,0.15));
  border: 1px solid rgba(255,255,255,0.12);
  margin-bottom: 12px;
}

.brand-icon-svg {
  width: 30px;
  height: 30px;
  color: rgba(255,255,255,0.9);
}

.brand-zone h1 {
  margin: 0;
  font-size: 22px;
  font-weight: 800;
  color: #ffffff;
  letter-spacing: 0.02em;
  white-space: nowrap;
  line-height: 1.3;
}

.brand-sub {
  margin: 4px 0 0 0;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.14em;
  color: rgba(255,255,255,0.4);
}

/* ==========================================================
   表单区（右侧）
   ========================================================== */
.form-zone {
  flex: 1 1 auto;
  min-width: 0;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field label {
  font-size: 12px;
  font-weight: 600;
  color: rgba(255,255,255,0.7);
  letter-spacing: 0.02em;
}

.field input {
  width: 100%;
  padding: 12px 14px;
  background: rgba(255,255,255,0.08);
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: 10px;
  font-size: 14px;
  color: #ffffff;
  outline: none;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, background 0.2s ease;
  box-sizing: border-box;
  font-family: inherit;
}

.field input::placeholder {
  color: rgba(255,255,255,0.3);
}

.field input:focus {
  border-color: rgba(255,255,255,0.35);
  box-shadow: 0 0 0 3px rgba(255,255,255,0.06);
  background: rgba(255,255,255,0.12);
}

/* 错误提示 */
.form-error {
  padding: 9px 14px;
  background: rgba(220,38,38,0.15);
  border: 1px solid rgba(220,38,38,0.3);
  border-radius: 8px;
  font-size: 12px;
  font-weight: 500;
  color: #fca5a5;
  text-align: center;
}

/* 登录按钮 */
.submit-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  padding: 13px 0;
  margin-top: 4px;
  background: rgba(255,255,255,0.9);
  color: var(--primary-dark);
  border: none;
  border-radius: 10px;
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
  transition: background 0.2s ease, box-shadow 0.2s ease, transform 0.15s ease;
  letter-spacing: 0.06em;
  font-family: inherit;
  box-shadow: 0 2px 12px rgba(0,0,0,0.1);
}

.submit-btn:hover:not(:disabled) {
  background: #ffffff;
  box-shadow: 0 4px 20px rgba(0,0,0,0.18);
  transform: translateY(-1px);
}

.submit-btn:active:not(:disabled) {
  transform: translateY(0);
}

.submit-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.spinner {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid rgba(30,64,175,0.2);
  border-top-color: var(--primary-dark);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/components/auth/LoginView.vue
git commit -m "feat(login): add glass card, brand zone and form styles"
```

---

### Task 5: 编写响应式与无障碍样式

**Files:**
- Modify: `frontend/src/components/auth/LoginView.vue`

- [ ] **Step 1: 追加响应式和无障碍媒体查询**

```css
/* ==========================================================
   响应式
   ========================================================== */
@media (max-width: 640px) {
  .glass-card {
    flex-direction: column;
    gap: 24px;
    width: 92vw;
    padding: 32px 28px 28px;
  }

  .brand-zone h1 {
    font-size: 20px;
  }

  .brand-sub {
    font-size: 8px;
  }

  .brand-icon-box {
    width: 44px;
    height: 44px;
    margin-bottom: 8px;
  }

  .brand-icon-svg {
    width: 24px;
    height: 24px;
  }
}

@media (max-width: 400px) {
  .glass-card {
    padding: 24px 20px 22px;
    border-radius: 18px;
  }

  .brand-icon-box {
    width: 36px;
    height: 36px;
    border-radius: 12px;
  }

  .brand-icon-svg {
    width: 20px;
    height: 20px;
  }

  .brand-zone h1 {
    font-size: 18px;
  }

  .brand-sub {
    display: none;
  }

  .field input {
    padding: 10px 12px;
    font-size: 13px;
  }
}

/* 尊重用户减少动画偏好 */
@media (prefers-reduced-motion: reduce) {
  .bg-orb,
  .particle,
  .glass-card {
    animation: none;
  }
}
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/components/auth/LoginView.vue
git commit -m "feat(login): add responsive and reduced-motion styles"
```

---

### Task 6: 验证与最终确认

- [ ] **Step 1: 检查文件一致性**

确保 `LoginView.vue` 结构完整：`<script setup>` → `<template>` → `<style>` → `<style scoped>`。

- [ ] **Step 2: 检查无残留旧代码**

```bash
grep -n "graphCanvas\|graphNodes\|graphEdges\|graph-panel\|graph-overlay\|graph-brand\|login-panel\|login-form-wrap" frontend/src/components/auth/LoginView.vue
```
预期：无匹配（所有旧 class 已移除）

- [ ] **Step 3: 启动前端验证编译**

```bash
cd frontend && npx vite build --mode development 2>&1 | tail -5
```

- [ ] **Step 4: 提交**

```bash
git add frontend/src/components/auth/LoginView.vue
git commit -m "chore(login): verify no old code remnants, build check"
```
