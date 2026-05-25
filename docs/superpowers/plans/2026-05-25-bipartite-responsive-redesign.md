# 二部图响应式布局优化 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 LeaderView.vue 中"数据底座与本体支撑关系"的 SVG 二部图从固定尺寸改为响应式布局，充分利用容器宽度，放大字体和间距。

**Architecture:** 使用 ResizeObserver 监听 `.lv-svg-wrap` 容器宽度，所有布局参数（源区宽度、芯片列数、芯片宽高、字体大小）改为基于 `containerWidth` 的动态计算。SVG 模板改为使用动态值渲染。

**Tech Stack:** Vue 3 (Composition API), SVG

---

## 变更范围

仅一个文件: `frontend/src/components/perspective/LeaderView.vue`

### Task 1: 新增 ResizeObserver + 容器宽度追踪

**Files:**
- Modify: `frontend/src/components/perspective/LeaderView.vue` (script setup, template)

- [ ] **Step 1: 添加 containerWidth ref、ResizeObserver 逻辑、动态布局参数 computed**

在 `<script setup>` 中，将第 133-145 行（所有固定常量）替换为以下代码:

```js
// ========== 响应式二部图布局 ==========
const svgContainer = ref(null);
const containerWidth = ref(700); // 默认宽度，ResizeObserver 就绪后更新

let resizeObserver = null;
onMounted(() => {
  if (svgContainer.value) {
    resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const w = entry.contentRect.width;
        if (w > 0) containerWidth.value = w;
      }
    });
    resizeObserver.observe(svgContainer.value);
  }
});

import { onUnmounted } from "vue";
onUnmounted(() => {
  if (resizeObserver) resizeObserver.disconnect();
});
```

- [ ] **Step 2: 添加动态布局参数 computed**

在 containerWidth 下面添加:

```js
const layoutParams = computed(() => {
  const W = containerWidth.value;
  const padding = 16;

  // 源节点区: ~20% 宽度，最小 100px
  const sourceX = 8;
  const sourceW = Math.max(100, Math.floor(W * 0.20));
  const sourceH = 40;

  // 连线区: ~8% 宽度
  const gapArea = Math.floor(W * 0.08);
  const midX = sourceX + sourceW + gapArea / 2;

  // 芯片区: 剩余宽度
  const chipAreaStart = sourceX + sourceW + gapArea;
  const chipAreaWidth = W - chipAreaStart - padding;

  // 动态列数: max(2, floor((chipArea + gap) / (minChipW + gap)))
  const chipGapX = 6;
  const chipGapY = 8;
  const minChipW = 80;
  const maxChipW = 140;
  const cols = Math.max(2, Math.floor((chipAreaWidth + chipGapX) / (minChipW + chipGapX)));

  // 动态芯片宽度
  const chipW = Math.min(maxChipW, Math.max(minChipW,
    Math.floor((chipAreaWidth - (cols - 1) * chipGapX) / cols)
  ));
  const chipH = 28;

  // 列宽和行高
  const colW = chipW + chipGapX;
  const rowH = chipH + chipGapY;

  // 组间距
  const groupGap = 32;

  // 字体大小: 随容器宽度线性变化
  const sourceFontSize = Math.max(11, Math.min(13, Math.floor(W / 55)));
  const chipFontSize = Math.max(10, Math.min(12, Math.floor(W / 65)));

  // shortName 截断长度: 根据芯片宽度估算
  const nameMaxLen = Math.floor(chipW / (chipFontSize * 0.6));

  return {
    padding, sourceX, sourceW, sourceH, gapArea, midX,
    chipAreaStart, chipAreaWidth, chipGapX, chipGapY,
    minChipW, maxChipW, cols, chipW, chipH, colW, rowH,
    groupGap, sourceFontSize, chipFontSize, nameMaxLen,
  };
});
```

- [ ] **Step 3: 修改 shortName 函数**

将原有的 `shortName` 函数改为接收动态 `nameMaxLen`:

```js
function shortName(name, maxLen) {
  if (!name) return "";
  return name.length > maxLen ? name.slice(0, maxLen - 1) + "…" : name;
}
```

- [ ] **Step 4: 重写 svgLayout computed**

完整替换原有 `svgLayout` (第 152-268 行):

```js
const svgLayout = computed(() => {
  if (!data.value?.data_sources?.length) return { groups: [], totalHeight: 0 };

  const sources = data.value.data_sources;
  const manualNames = data.value?.summary?.manual_node_names || [];
  if (!sources.length && !manualNames.length) return { groups: [], totalHeight: 0 };

  const LP = layoutParams.value;
  let y = LP.padding;
  const groups = [];

  function buildGroup(id, name, type, names) {
    const fullCount = names.length;
    const isExpanded = expandedSources.value.has(id);
    const showAll = isExpanded || fullCount <= COLLAPSE_LIMIT;
    const visibleCount = showAll ? fullCount : COLLAPSE_LIMIT;
    const visibleNames = showAll ? names : names.slice(0, COLLAPSE_LIMIT);

    const rows = fullCount === 0 ? 0 : Math.ceil(visibleCount / LP.cols);
    let blockH = Math.max(rows * LP.rowH, LP.sourceH + 8);
    const needsButton = fullCount > COLLAPSE_LIMIT;
    if (needsButton && !isExpanded) {
      blockH += 8 + LP.chipH;
    }

    const sourceY = y + (blockH - LP.sourceH) / 2;

    const chips = [];
    for (let i = 0; i < visibleCount; i++) {
      const row = Math.floor(i / LP.cols);
      const col = i % LP.cols;
      chips.push({
        name: visibleNames[i],
        x: LP.chipAreaStart + col * LP.colW,
        y: y + row * LP.rowH,
      });
    }

    const buttonX = LP.chipAreaStart;
    const buttonY = rows === 0 ? y + 4 : y + rows * LP.rowH + 6;

    groups.push({
      id, name, type,
      sourceX: LP.sourceX, sourceY, sourceW: LP.sourceW, sourceH: LP.sourceH,
      chips, rows, hasContent: fullCount > 0,
      needsButton, hiddenCount: fullCount - COLLAPSE_LIMIT, isExpanded,
      buttonX, buttonY, blockTop: y, blockH,
      midX: LP.midX, chipX: LP.chipAreaStart,
    });

    y += blockH + LP.groupGap;
  }

  for (const src of sources) {
    buildGroup(src.id, src.name, (src.type || "").toLowerCase(), src.covered_ontology_names || []);
  }

  if (manualNames.length > 0) {
    buildGroup("src-manual", "人工维护", "manual", manualNames);
  }

  return { groups, totalHeight: y - LP.groupGap + LP.padding };
});
```

---

### Task 2: 更新 SVG 模板使用动态参数

**Files:**
- Modify: `frontend/src/components/perspective/LeaderView.vue` (template)

- [ ] **Step 1: 在 `.lv-svg-wrap` 上添加 ref**

将第 446 行的:
```html
<div v-if="svgLayout.groups.length" class="lv-svg-wrap">
```
替换为:
```html
<div v-if="svgLayout.groups.length" class="lv-svg-wrap" ref="svgContainer">
```

- [ ] **Step 2: SVG width/height/viewBox 改为动态**

将第 448-453 行:
```html
<svg
  :width="SVG_W"
  :height="svgLayout.totalHeight"
  :viewBox="`0 0 ${SVG_W} ${svgLayout.totalHeight}`"
  class="lv-svg"
  xmlns="http://www.w3.org/2000/svg"
>
```
替换为:
```html
<svg
  :width="containerWidth - 32"
  :height="svgLayout.totalHeight"
  :viewBox="`0 0 ${containerWidth - 32} ${svgLayout.totalHeight}`"
  class="lv-svg"
  xmlns="http://www.w3.org/2000/svg"
>
```

- [ ] **Step 3: SVG 内部元素尺寸改为使用 layoutParams + group 属性**

将源节点 rect 的尺寸和字体、芯片的尺寸和字体改为动态值:

源节点 rect (第 479-487 行):
```html
<rect
  :x="g.sourceX" :y="g.sourceY"
  :width="g.sourceW" :height="g.sourceH"
  :rx="8"
  :fill="sourceTypeStyle(g.type).fill"
  filter="url(#card-shadow)"
/>
<text
  :x="g.sourceX + g.sourceW / 2"
  :y="g.sourceY + g.sourceH / 2 + 1"
  text-anchor="middle" dominant-baseline="central"
  fill="#ffffff"
  :font-size="layoutParams.sourceFontSize"
  font-weight="700" letter-spacing="0.02em"
>{{ shortName(g.name, layoutParams.nameMaxLen) }}</text>
```

芯片 rect + text (第 499-519 行):
```html
<rect
  :x="chip.x" :y="chip.y"
  :width="layoutParams.chipW" :height="layoutParams.chipH"
  :rx="layoutParams.chipH / 2"
  fill="#ffffff" stroke="#e2e8f0" stroke-width="1"
  filter="url(#chip-shadow)"
/>
<text
  :x="chip.x + layoutParams.chipW / 2"
  :y="chip.y + layoutParams.chipH / 2 + 1"
  text-anchor="middle" dominant-baseline="central"
  fill="#334155"
  :font-size="layoutParams.chipFontSize"
  font-weight="600"
>{{ shortName(chip.name, layoutParams.nameMaxLen) }}</text>
```

展开按钮 rect + text (第 522-542 行):
```html
<rect
  :x="g.buttonX" :y="g.buttonY"
  :width="layoutParams.chipW" :height="layoutParams.chipH"
  :rx="layoutParams.chipH / 2"
  fill="#f8fafc" stroke="#cbd5e1" stroke-width="1"
  stroke-dasharray="2 2"
/>
<text
  :x="g.buttonX + layoutParams.chipW / 2"
  :y="g.buttonY + layoutParams.chipH / 2 + 1"
  text-anchor="middle" dominant-baseline="central"
  fill="#64748b"
  :font-size="layoutParams.chipFontSize"
  font-weight="600"
>{{ g.isExpanded ? '收起' : '+' + g.hiddenCount + ' 个' }}</text>
```

暂无关联本体提示文本 (第 545-553 行):
```html
<text
  v-if="!g.hasContent"
  :x="g.chipX" :y="g.sourceY + g.sourceH / 2 + 1"
  dominant-baseline="central"
  fill="#94a3b8"
  :font-size="layoutParams.chipFontSize"
  font-style="italic"
>暂无关联本体</text>
```

---

### Task 3: 调整样式

**Files:**
- Modify: `frontend/src/components/perspective/LeaderView.vue` (style)

- [ ] **Step 1: `.lv-svg-wrap` 样式调整**

将第 918-925 行:
```css
.lv-svg-wrap {
  border: 1px solid #e8ecf1;
  border-radius: 12px;
  background: #ffffff;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
  overflow-x: auto;
  padding: 14px;
}
```
替换为:
```css
.lv-svg-wrap {
  border: 1px solid #e8ecf1;
  border-radius: 12px;
  background: #ffffff;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
  overflow-x: hidden;
  padding: 12px;
  width: 100%;
  box-sizing: border-box;
}
```

注意：将 `overflow-x: auto` 改为 `overflow-x: hidden`，因为现在 SVG 自适应宽度不需要横向滚动。添加 `width: 100%; box-sizing: border-box;` 确保容器占满宽度。

---

### Task 4: 验证并提交

- [ ] **Step 1: 启动前端 dev server 验证**

```bash
cd H:\Git\OCR_benti-main_win7\frontend && npm run dev
```
在浏览器中检查 LeaderView 的二部图区域是否响应式适应容器宽度。

- [ ] **Step 2: 提交代码**

```bash
git add frontend/src/components/perspective/LeaderView.vue
git commit -m "feat: 二部图响应式布局 — ResizeObserver驱动动态列数/芯片宽度/字体"
```
