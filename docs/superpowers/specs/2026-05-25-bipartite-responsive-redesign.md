# 二部图响应式布局优化

日期: 2026-05-25 | 状态: 已确认

## 背景

LeaderView 的"数据底座与本体支撑关系" SVG 二部图使用固定尺寸（464px 宽），所有字体、间距、列数均为硬编码。导致：字体过小看不清、元素拥挤、右侧大量空白。

## 设计

### 核心改动

废弃所有硬编码尺寸，改用 `ResizeObserver` 监听容器宽度，动态计算布局参数。

### 布局参数对比

| 参数 | 当前（固定） | 优化后（动态） |
|---|---|---|
| SVG 总宽 | 464px | 容器 100% |
| 源节点区宽 | 固定 116px (16+100) | max(100, 容器宽 × 0.2) |
| 连线区宽 | 24px | 容器宽 × 0.08 |
| 芯片区 | 304px | 剩余宽度 |
| 芯片列数 | 固定 4 | max(2, floor(芯片区 / (minChipW + gap))) |
| 芯片宽度 | 72px | 芯片区 / 列数 - gap, clamp(80, 140) |
| 芯片高度 | 22px | 28px |
| 源名字体 | 10px | clamp(11, 13) |
| 芯片字体 | 9.5px | clamp(10, 12) |
| 组间距 | 24px | 32px |
| 行间距 | 4px | 8px |
| 源节点高 | 34px | 40px |

### 计算流程

```
ResizeObserver → containerWidth
  ├── sourceAreaWidth = max(100, containerWidth × 0.20)
  ├── gapArea = containerWidth × 0.08
  ├── chipAreaWidth = containerWidth - sourceAreaWidth - gapArea - padding
  ├── cols = max(2, floor((chipAreaWidth + chipGap) / (minChipW + chipGap)))
  ├── chipW = min(maxChipW, max(minChipW, (chipAreaWidth - (cols-1)×chipGap) / cols))
  ├── fontSizeBase = clamp(containerWidth / 55, 10, 13)
  └── SVG height = sum of all group block heights + gaps
```

### 受影响文件

- `frontend/src/components/perspective/LeaderView.vue` — 唯一改动文件
  - 新增 `containerWidth` ref + `ResizeObserver`
  - 重写 `svgLayout` computed：所有固定常量改为基于 `containerWidth` 的计算
  - 模板中 SVG `width` 使用 `containerWidth` 替代 `SVG_W`
  - 小幅调整样式（`lv-svg-wrap` 占满宽度）

### 不改变

- 二部图结构（左侧源节点 → 右侧本体芯片）
- 贝塞尔曲线连线
- 折叠/展开交互
- 颜色体系
- 后端 API
