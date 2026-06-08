# 登录界面重新设计 V2 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 LoginView.vue 重写为灰白配色、8px留白、非对称左右分栏（左38%浅灰+右62%白色）、同心圆几何装饰的纯静态登录页

**Architecture:** 单文件完整重写 — `<script setup>` 保留登录逻辑不变，`<template>` 和 `<style>` 全部替换。无CSS动画，使用系统字体栈。

**Tech Stack:** Vue 3 SFC, 原生 CSS, 系统字体

---

### Task 1: 重写模板

**Files:**
- Modify: `frontend/src/components/auth/LoginView.vue`

- [ ] **Step 1: 替换 `<template>` 为新布局**

读当前文件，将 `<template>` 块（从 `<template>` 到 `</template>`）替换为：

```html
<template>
  <div class="login-shell">
    <div class="login-card">
      <!-- 左侧品牌面板 -->
      <div class="brand-panel">
        <div class="brand-content">
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

          <!-- 同心圆几何装饰 -->
          <div class="geo-decor">
            <div class="geo-ring outer"></div>
            <div class="geo-ring middle"></div>
            <div class="geo-dot"></div>
          </div>
        </div>
      </div>

      <!-- 右侧表单面板 -->
      <div class="form-panel">
        <div class="form-wrap">
          <div class="form-header">
            <h2>欢迎回来</h2>
            <p>登录以访问您的工作台</p>
          </div>

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
  </div>
</template>
```

- [ ] **Step 2: 删除旧的 `<style>` 块（全局字体导入）**

删除整个 `<style>` 非 scoped 块（第 123-125 行，包含 `@import url(...)`）。V2 使用系统字体。

- [ ] **Step 3: 提交**

```bash
git add frontend/src/components/auth/LoginView.vue
git commit -m "feat(login): rewrite template with 8px padding, asymmetric gray-white layout"
```

---

### Task 2: 重写样式

**Files:**
- Modify: `frontend/src/components/auth/LoginView.vue`

- [ ] **Step 1: 替换 `<style scoped>` 为完整灰白配色样式**

将 `<style scoped>` 块的完整内容替换为：

```css
<style scoped>
/* ==========================================================
   外层容器：8px 留白
   ========================================================== */
.login-shell {
  width: 100vw;
  height: 100vh;
  padding: 8px;
  background: #f8f9fa;
  box-sizing: border-box;
  font-family: "Noto Sans SC", "PingFang SC", "Microsoft YaHei", system-ui, -apple-system, sans-serif;
  -webkit-font-smoothing: antialiased;
}

.login-card {
  display: flex;
  width: 100%;
  height: 100%;
  background: #ffffff;
  border-radius: 12px;
  overflow: hidden;
}

/* ==========================================================
   左侧品牌面板 (38%)
   ========================================================== */
.brand-panel {
  flex: 0 0 38%;
  background: #f4f6f8;
  display: flex;
  align-items: flex-start;
  padding: 44px 40px;
  min-width: 0;
}

.brand-content {
  display: flex;
  flex-direction: column;
}

.brand-icon-box {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: #1e293b;
  margin-bottom: 14px;
}

.brand-icon-svg {
  width: 22px;
  height: 22px;
  color: #ffffff;
}

.brand-content h1 {
  margin: 0 0 3px 0;
  font-size: 20px;
  font-weight: 800;
  color: #1e293b;
  letter-spacing: 0.02em;
  line-height: 1.3;
}

.brand-sub {
  margin: 0;
  font-size: 8px;
  font-weight: 600;
  letter-spacing: 0.12em;
  color: #94a3b8;
}

/* 同心圆几何装饰 */
.geo-decor {
  position: relative;
  width: 100px;
  height: 100px;
  margin-top: 36px;
}

.geo-ring {
  position: absolute;
  border-radius: 50%;
}

.geo-ring.outer {
  width: 100px;
  height: 100px;
  border: 2px solid #d1d5db;
  top: 0;
  left: 0;
}

.geo-ring.middle {
  width: 60px;
  height: 60px;
  border: 1.5px solid #e5e7eb;
  top: 20px;
  left: 20px;
}

.geo-dot {
  position: absolute;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: #1e293b;
  opacity: 0.08;
  top: 36px;
  left: 36px;
}

/* ==========================================================
   右侧表单面板 (62%)
   ========================================================== */
.form-panel {
  flex: 1 1 auto;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #ffffff;
  min-width: 0;
  padding: 40px;
}

.form-wrap {
  width: 300px;
  max-width: 100%;
}

.form-header {
  margin-bottom: 28px;
}

.form-header h2 {
  margin: 0 0 4px 0;
  font-size: 18px;
  font-weight: 700;
  color: #1e293b;
  letter-spacing: -0.01em;
}

.form-header p {
  margin: 0;
  font-size: 13px;
  color: #64748b;
}

/* 表单 */
.login-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field label {
  font-size: 12px;
  font-weight: 600;
  color: #334155;
  letter-spacing: 0.02em;
}

.field input {
  width: 100%;
  padding: 12px 14px;
  background: #f8fafc;
  border: 1.5px solid #e2e8f0;
  border-radius: 8px;
  font-size: 14px;
  color: #1e293b;
  outline: none;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
  box-sizing: border-box;
  font-family: inherit;
}

.field input::placeholder {
  color: #94a3b8;
}

.field input:focus {
  border-color: #94a3b8;
  box-shadow: 0 0 0 3px rgba(148,163,184,0.15);
}

/* 错误提示 */
.form-error {
  padding: 9px 14px;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 500;
  color: #dc2626;
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
  margin-top: 6px;
  background: #1e293b;
  color: #ffffff;
  border: none;
  border-radius: 8px;
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
  transition: background 0.2s ease, transform 0.15s ease;
  letter-spacing: 0.06em;
  font-family: inherit;
}

.submit-btn:hover:not(:disabled) {
  background: #0f172a;
  transform: translateY(-1px);
}

.submit-btn:focus-visible {
  outline: 2px solid #94a3b8;
  outline-offset: 2px;
}

.submit-btn:active:not(:disabled) {
  transform: translateY(0);
}

.submit-btn:disabled {
  opacity: 0.5;
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

/* ==========================================================
   响应式
   ========================================================== */
@media (max-width: 768px) {
  .login-card {
    flex-direction: column;
  }

  .brand-panel {
    flex: 0 0 auto;
    padding: 28px 24px 20px;
  }

  .geo-decor {
    display: none;
  }

  .brand-content {
    flex-direction: row;
    align-items: center;
    gap: 12px;
  }

  .brand-icon-box {
    width: 32px;
    height: 32px;
    border-radius: 8px;
    margin-bottom: 0;
  }

  .brand-icon-svg {
    width: 18px;
    height: 18px;
  }

  .brand-content h1 {
    font-size: 16px;
  }

  .brand-sub {
    display: none;
  }

  .form-panel {
    flex: 1 1 auto;
    align-items: flex-start;
    padding: 24px;
  }
}

@media (max-width: 480px) {
  .login-shell {
    padding: 4px;
  }

  .login-card {
    border-radius: 8px;
  }

  .brand-panel {
    padding: 18px 16px 14px;
  }

  .form-panel {
    padding: 16px;
  }

  .form-wrap {
    width: 100%;
  }

  .form-header h2 {
    font-size: 16px;
  }
}
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/components/auth/LoginView.vue
git commit -m "feat(login): gray-white color scheme, geometric decor, responsive layout"
```

---

### Task 3: 验证

- [ ] **Step 1: 检查无 V1 残留代码**

```bash
grep -n "glass-card\|bg-orb\|particle\|backdrop-filter\|#0f2744\|#3075f0\|#2563eb" frontend/src/components/auth/LoginView.vue
```
预期：无匹配

- [ ] **Step 2: 构建验证**

```bash
cd frontend && npx vite build --mode development 2>&1 | tail -5
```
预期：built successfully

- [ ] **Step 3: 提交**

```bash
git add frontend/src/components/auth/LoginView.vue
git commit -m "chore(login): verify V2 build, no V1 remnants"
```
