<script setup>
/**
 * EngineerView.vue — 数据映射思维导图
 *
 * 展示 业务域 → 本体概念 → 数据源(表) → 属性映射 的树形结构。
 * 纯 SVG 自绘，手动树布局算法。
 */
import { ref, reactive, watch, computed, onMounted } from 'vue'

const props = defineProps({
  projectId: { type: String, required: true }
})

const API_BASE = import.meta.env.VITE_API_BASE || ''

const rawData = ref(null)
const loading = ref(true)
const error = ref(null)

async function loadData() {
  loading.value = true
  error.value = null
  try {
    const resp = await fetch(API_BASE + '/api/perspective/' + props.projectId + '/engineer')
    if (!resp.ok) throw new Error('HTTP ' + resp.status + ': ' + (await resp.text()))
    rawData.value = await resp.json()
  } catch (e) {
    error.value = e.message || String(e)
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
watch(function () { return props.projectId; }, loadData)

/* ==========================================================================
   设计系统常量
   ========================================================================== */

const COLORS = {
  primary: '#1E3A5F',
  secondary: '#2563EB',
  bg: '#F8FAFC',
  conceptGray: '#334155',
  lineDefault: '#CBD5E1',
  textMuted: '#94A3B8',
  white: '#FFFFFF'
}

const DOMAIN_COLORS = ['#E65100', '#059669', '#2563EB', '#7C3AED', '#DC2626', '#0891B2', '#CA8A04']

const SOURCE_STYLES = {
  dameng: { bg: '#EDE9FE', text: '#7C3AED', label: '达梦', badge: '#A78BFA' },
  excel: { bg: '#DCFCE7', text: '#16A34A', label: 'Excel', badge: '#4ADE80' },
  csv: { bg: '#FFF7ED', text: '#EA580C', label: 'CSV', badge: '#FB923C' }
}

function getSourceStyle(type) {
  return SOURCE_STYLES[(type || '').toLowerCase()] || { bg: '#F1F5F9', text: '#64748B', label: type || '其他', badge: '#94A3B8' }
}

/* ==========================================================================
   节点尺寸常量 — 收紧间距，减少空白
   ========================================================================== */

const NODE_PAD = 10

const NODE_DIMS = {
  root: { w: 56, h: 56, r: 28 },
  domain: { h: 30, rx: 7, fontSize: 13 },
  concept: { h: 26, rx: 5, fontSize: 12 },
  source: { h: 26, rx: 5, fontSize: 11 },
  attrField: { h: 22, fontSize: 10 }
}

// 水平间距：减小以避免空白过多
const H_GAPS = [130, 140, 140, 140]
const V_GAPS = [20, 12, 12, 12]

const ROOT_X = 36
const TOP_MARGIN = 36
const RIGHT_MARGIN = 36
const BOTTOM_MARGIN = 36

/* ==========================================================================
   文本宽度测量 — 提高中文字符宽度，避免溢出
   ========================================================================== */

function rawTextWidth(text, fontSize) {
  if (!text) return 0
  var w = 0
  for (var i = 0; i < text.length; i++) {
    var ch = text[i]
    if (/[^\x00-\x7F]/.test(ch)) {
      w += fontSize * 1.2 // 中文/全角更宽
    } else {
      w += fontSize * 0.62
    }
  }
  return Math.ceil(w)
}

function estimateTextWidth(text, fontSize) {
  return rawTextWidth(text, fontSize) + NODE_PAD * 2
}

/** 截断过长文本 */
function truncateText(text, maxWidth, fontSize) {
  if (!text) return ''
  if (rawTextWidth(text, fontSize) <= maxWidth - NODE_PAD * 2) return text
  var w = 0
  for (var i = 0; i < text.length; i++) {
    var ch = text[i]
    w += /[^\x00-\x7F]/.test(ch) ? fontSize * 1.2 : fontSize * 0.62
    if (w > maxWidth - NODE_PAD * 2 - rawTextWidth('…', fontSize)) {
      return text.substring(0, i) + '…'
    }
  }
  return text
}

function computeNodeWidth(node) {
  switch (node.type) {
    case 'root': return NODE_DIMS.root.w
    case 'domain': return estimateTextWidth(node.label, NODE_DIMS.domain.fontSize)
    case 'concept': return estimateTextWidth(node.label, NODE_DIMS.concept.fontSize)
    case 'source': {
      var style = getSourceStyle(node.sourceType)
      var labelTW = rawTextWidth(style.label, 9)
      var nameTW = rawTextWidth(node.label, NODE_DIMS.source.fontSize)
      return labelTW + 6 + nameTW + NODE_PAD * 2
    }
    case 'attr-field': {
      var keyW = rawTextWidth(node.attrKey, NODE_DIMS.attrField.fontSize)
      var sepW = rawTextWidth(' ← ', NODE_DIMS.attrField.fontSize)
      var fieldW = rawTextWidth(node.label, NODE_DIMS.attrField.fontSize)
      return keyW + sepW + fieldW + NODE_PAD * 2
    }
    default: return 60
  }
}

/* ==========================================================================
   折叠状态
   ========================================================================== */

const collapsedNodeIds = reactive(new Set())

function isNodeCollapsed(nodeId) { return collapsedNodeIds.has(nodeId) }

function toggleNodeCollapse(nodeId) {
  if (collapsedNodeIds.has(nodeId)) collapsedNodeIds.delete(nodeId)
  else collapsedNodeIds.add(nodeId)
}

function expandAllNodes() { collapsedNodeIds.clear() }

function collapseAllNodes() {
  var root = treeRoot.value
  if (!root) return
  collapseRecursive(root)
}

function collapseRecursive(node) {
  if (node.children && node.children.length > 0) {
    collapsedNodeIds.add(node.id)
    node.children.forEach(function (child) { collapseRecursive(child) })
  }
}

/* ==========================================================================
   构建树结构 — 使用后端返回的 node_name 和 domain_id
   ========================================================================== */

const projectName = computed(function () {
  var d = rawData.value
  if (d && d.project_name) return d.project_name
  return props.projectId || '项目'
})

const treeRoot = computed(function () {
  var data = rawData.value
  if (!data || !data.mappings || !data.mappings.length) return null

  // 域名映射
  var domainMap = new Map()
  ;(data.domains || []).forEach(function (d) {
    domainMap.set(String(d.id), String(d.name))
  })

  // 按 domain_id → concept(node_name) → source(table) → field_mappings 分组
  var domainGroups = new Map()

  data.mappings.forEach(function (m) {
    var did = String(m.domain_id || '_other')
    var dname = domainMap.get(did) || did
    if (!domainGroups.has(dname)) domainGroups.set(dname, { concepts: new Map(), domainId: did })

    var domain = domainGroups.get(dname)
    var cname = String(m.node_name || m.ontology_node_id || '')
    if (!domain.concepts.has(cname)) domain.concepts.set(cname, { sources: new Map() })

    var concept = domain.concepts.get(cname)
    var skey = (m.source_type || '') + '|' + (m.source_name || '') + '|' + (m.table_name || '')
    if (!concept.sources.has(skey)) {
      concept.sources.set(skey, {
        sourceType: (m.source_type || '').toLowerCase(),
        sourceName: m.source_name || '',
        tableName: m.table_name || '',
        fields: []
      })
    }

    // 遍历 field_mappings 添加字段节点
    ;(m.field_mappings || []).forEach(function (fm) {
      concept.sources.get(skey).fields.push({
        name: String(fm.field_name || ''),
        attrKey: String(fm.attribute_key || ''),
        dataType: String(fm.data_type || '')
      })
    })
  })

  // 构建树节点
  var root = {
    id: '__root__',
    type: 'root',
    label: projectName.value,
    children: [],
    _depth: 0,
    _parentId: null
  }

  var colorIdx = 0
  domainGroups.forEach(function (domain, dname) {
    var domainNode = {
      id: 'd|' + dname,
      type: 'domain',
      label: dname,
      domainColor: DOMAIN_COLORS[colorIdx % DOMAIN_COLORS.length],
      children: [],
      _depth: 1,
      _parentId: root.id
    }
    colorIdx++

    domain.concepts.forEach(function (concept, cname) {
      var conceptNode = {
        id: 'c|' + dname + '|' + cname,
        type: 'concept',
        label: cname,
        children: [],
        _depth: 2,
        _parentId: domainNode.id
      }

      concept.sources.forEach(function (source, skey) {
        var sourceNode = {
          id: 's|' + dname + '|' + cname + '|' + skey,
          type: 'source',
          label: source.tableName,
          sourceType: source.sourceType,
          sourceName: source.sourceName,
          children: [],
          _depth: 3,
          _parentId: conceptNode.id
        }

        source.fields.forEach(function (field) {
          sourceNode.children.push({
            id: 'f|' + dname + '|' + cname + '|' + skey + '|' + field.attrKey,
            type: 'attr-field',
            label: field.name,
            attrKey: field.attrKey,
            dataType: field.dataType,
            children: [],
            _depth: 4,
            _parentId: sourceNode.id
          })
        })

        conceptNode.children.push(sourceNode)
      })

      domainNode.children.push(conceptNode)
    })

    root.children.push(domainNode)
  })

  return root
})

/* ==========================================================================
   树布局算法
   ========================================================================== */

function computeSubtreeHeight(node) {
  node._w = computeNodeWidth(node)
  switch (node.type) {
    case 'root': node._h = NODE_DIMS.root.h; break
    case 'domain': node._h = NODE_DIMS.domain.h; break
    case 'concept': node._h = NODE_DIMS.concept.h; break
    case 'source': node._h = NODE_DIMS.source.h; break
    case 'attr-field': node._h = NODE_DIMS.attrField.h; break
    default: node._h = 20
  }

  var depth = node._depth || 0
  var collapsed = isNodeCollapsed(node.id)
  if (collapsed || !node.children || node.children.length === 0) {
    node._subtreeH = node._h
    return
  }

  var totalH = 0
  for (var i = 0; i < node.children.length; i++) {
    computeSubtreeHeight(node.children[i])
    totalH += node.children[i]._subtreeH
  }
  totalH += (node.children.length - 1) * V_GAPS[Math.min(depth, V_GAPS.length - 1)]
  node._subtreeH = Math.max(node._h, totalH)
}

function assignPositions(node, x, top) {
  node._x = x
  var depth = node._depth || 0
  var collapsed = isNodeCollapsed(node.id)

  if (collapsed || !node.children || node.children.length === 0) {
    node._y = top + (node._subtreeH - node._h) / 2
    return
  }

  var childTop = top
  var gapIdx = Math.min(depth, V_GAPS.length - 1)
  var hGapIdx = Math.min(depth, H_GAPS.length - 1)
  var childX = x + node._w + H_GAPS[hGapIdx]

  for (var i = 0; i < node.children.length; i++) {
    assignPositions(node.children[i], childX, childTop)
    childTop += node.children[i]._subtreeH + V_GAPS[gapIdx]
  }

  var first = node.children[0]
  var last = node.children[node.children.length - 1]
  var childrenMidY = (first._y + first._h / 2 + last._y + last._h / 2) / 2
  node._y = childrenMidY - node._h / 2
}

function collectVisibleNodes(node, result) {
  result.push(node)
  var collapsed = isNodeCollapsed(node.id)
  if (collapsed || !node.children) return
  for (var i = 0; i < node.children.length; i++) {
    collectVisibleNodes(node.children[i], result)
  }
}

const layoutResult = computed(function () {
  var root = treeRoot.value
  if (!root) return null
  var copy = JSON.parse(JSON.stringify(root))
  computeSubtreeHeight(copy)
  assignPositions(copy, ROOT_X, TOP_MARGIN)
  var visibleNodes = []
  collectVisibleNodes(copy, visibleNodes)
  var maxRight = 0, maxBottom = 0
  visibleNodes.forEach(function (n) {
    if (n._x + n._w > maxRight) maxRight = n._x + n._w
    if (n._y + n._h > maxBottom) maxBottom = n._y + n._h
  })
  return { root: copy, visibleNodes: visibleNodes, viewW: maxRight + RIGHT_MARGIN, viewH: maxBottom + BOTTOM_MARGIN }
})

const svgViewBox = computed(function () {
  var lay = layoutResult.value
  if (!lay) return '0 0 100 100'
  return '0 0 ' + lay.viewW + ' ' + lay.viewH
})

/* ==========================================================================
   边列表
   ========================================================================== */

const edgeList = computed(function () {
  var lay = layoutResult.value
  if (!lay) return []
  var edges = []
  function walk(node) {
    var collapsed = isNodeCollapsed(node.id)
    if (collapsed || !node.children) return
    node.children.forEach(function (child) {
      edges.push({
        id: node.id + '->' + child.id,
        parentId: node.id, childId: child.id,
        parentType: node.type, childType: child.type,
        x1: node._x + node._w,
        y1: node._y + node._h / 2,
        x2: child._x,
        y2: child._y + child._h / 2,
        lineColor: node.type === 'root' ? COLORS.primary
          : node.type === 'domain' ? node.domainColor
          : COLORS.lineDefault
      })
      walk(child)
    })
  }
  walk(lay.root)
  return edges
})

/* ==========================================================================
   hover 高亮
   ========================================================================== */

const hoverNodeId = ref(null)
const hoverEdgeId = ref(null)

const hoverHighlightNodeIds = computed(function () {
  var targetId = hoverNodeId.value || hoverEdgeId.value
  if (!targetId) return new Set()
  var ids = new Set()
  if (hoverNodeId.value) {
    ids.add(hoverNodeId.value)
    var allNodes = layoutResult.value && layoutResult.value.visibleNodes
    if (allNodes) {
      var parentMap = new Map()
      allNodes.forEach(function (n) { if (n._parentId) parentMap.set(n.id, n._parentId) })
      var current = hoverNodeId.value
      while (current) { var p = parentMap.get(current); if (!p) break; ids.add(p); current = p }
    }
  } else if (hoverEdgeId.value) {
    var edge = edgeList.value.find(function (e) { return e.id === hoverEdgeId.value })
    if (edge) {
      ids.add(edge.parentId); ids.add(edge.childId)
      var allN = layoutResult.value && layoutResult.value.visibleNodes
      if (allN) {
        var pm = new Map()
        allN.forEach(function (n) { if (n._parentId) pm.set(n.id, n._parentId) })
        var cur = edge.parentId
        while (cur) { var pp = pm.get(cur); if (!pp) break; ids.add(pp); cur = pp }
      }
    }
  }
  return ids
})

const hoverHighlightEdgeIds = computed(function () {
  var nodeIds = hoverHighlightNodeIds.value
  if (!nodeIds.size) return new Set()
  var eIds = new Set()
  edgeList.value.forEach(function (e) {
    if (nodeIds.has(e.parentId) && nodeIds.has(e.childId)) eIds.add(e.id)
  })
  return eIds
})

function onNodeEnter(nodeId) { hoverNodeId.value = nodeId }
function onNodeLeave() { hoverNodeId.value = null }
function onEdgeEnter(edgeId) { hoverEdgeId.value = edgeId }
function onEdgeLeave() { hoverEdgeId.value = null }

/* ==========================================================================
   缩放 / 平移 — 与本体推理画布完全一致
   ========================================================================== */

const viewTransform = reactive({ x: 0, y: 0, scale: 1 })
const isDragging = ref(false)
var dragStartX = 0, dragStartY = 0, dragTransX0 = 0, dragTransY0 = 0
var _rafId = null, _latestEvent = null

function _handleDragMouseMove(e) {
  _latestEvent = e
  if (!_rafId) {
    _rafId = requestAnimationFrame(function () {
      _rafId = null
      if (!_latestEvent || !isDragging.value) return
      var scale = getSVGScale()
      viewTransform.x = dragTransX0 + (_latestEvent.clientX - dragStartX) / scale.x
      viewTransform.y = dragTransY0 + (_latestEvent.clientY - dragStartY) / scale.y
      _latestEvent = null
    })
  }
}

function _handleDragMouseUp() {
  if (_rafId) { cancelAnimationFrame(_rafId); _rafId = null }
  _latestEvent = null
  window.removeEventListener('mousemove', _handleDragMouseMove)
  window.removeEventListener('mouseup', _handleDragMouseUp)
  isDragging.value = false
}

function onSvgMouseDown(e) {
  var target = e.target
  if (target && target.closest && (target.closest('.mm-node') || target.closest('.mm-collapse'))) return
  isDragging.value = true
  dragStartX = e.clientX; dragStartY = e.clientY
  dragTransX0 = viewTransform.x; dragTransY0 = viewTransform.y
  window.addEventListener('mousemove', _handleDragMouseMove)
  window.addEventListener('mouseup', _handleDragMouseUp)
  e.preventDefault()
}

// 与 App.vue onWheel 完全相同的缩放公式
function onSvgWheel(event) {
  var rect = svgContainer.value ? svgContainer.value.getBoundingClientRect() : null
  if (!rect) return

  var zoomSensitivity = 0.001
  var delta = -event.deltaY * zoomSensitivity
  var newScale = viewTransform.scale * (1 + delta)
  newScale = Math.max(0.1, Math.min(newScale, 5))

  var scale = getSVGScale()
  var mouseXSvg = (event.clientX - scale.e) / scale.x
  var mouseYSvg = (event.clientY - scale.f) / scale.y
  var scaleRatio = newScale / viewTransform.scale
  viewTransform.x = mouseXSvg - (mouseXSvg - viewTransform.x) * scaleRatio
  viewTransform.y = mouseYSvg - (mouseYSvg - viewTransform.y) * scaleRatio
  viewTransform.scale = newScale
}

// 与 App.vue 完全相同的缩放控件方法
function zoomIn() {
  viewTransform.scale = Math.min(viewTransform.scale * 1.2, 5)
}

function zoomOut() {
  viewTransform.scale = Math.max(viewTransform.scale / 1.2, 0.1)
}

function zoomReset() {
  viewTransform.scale = 1
  viewTransform.x = 0
  viewTransform.y = 0
}

const svgContainer = ref(null)

function getSVGScale() {
  var svgEl = svgContainer.value?.querySelector('svg')
  if (!svgEl) return { x: 1, y: 1, e: 0, f: 0 }
  var ctm = svgEl.getScreenCTM()
  if (!ctm) return { x: 1, y: 1, e: 0, f: 0 }
  return { x: ctm.a, y: ctm.d, e: ctm.e, f: ctm.f }
}

/* ==========================================================================
   统计
   ========================================================================== */

const stats = computed(function () {
  var root = treeRoot.value
  if (!root || !rawData.value) return null
  var domainCount = root.children.length
  var conceptCount = 0, sourceSet = new Set()
  var fieldCount = rawData.value.mappings
    ? rawData.value.mappings.reduce(function (sum, m) { return sum + (m.field_mappings ? m.field_mappings.length : 0) }, 0)
    : 0
  root.children.forEach(function (d) {
    conceptCount += d.children.length
    d.children.forEach(function (c) { c.children.forEach(function (s) { sourceSet.add(s.sourceType + '|' + s.label) }) })
  })
  return { domainCount, conceptCount, sourceCount: sourceSet.size, fieldCount }
})
</script>

<template>
  <div class="mindmap-view">
    <!-- 加载状态 -->
    <div v-if="loading" class="state-overlay">
      <div class="loading-spinner"></div>
      <span>正在加载数据映射...</span>
    </div>

    <!-- 错误状态 -->
    <div v-else-if="error" class="state-overlay state-error">
      <svg viewBox="0 0 24 24" width="32" height="32" fill="none" stroke="#94A3B8" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>
      </svg>
      <p>数据加载失败：{{ error }}</p>
      <button class="btn-retry" @click="loadData">重新加载</button>
    </div>

    <!-- 空状态 -->
    <div v-else-if="!treeRoot || !layoutResult" class="state-overlay state-empty">
      <svg viewBox="0 0 24 24" width="40" height="40" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">
        <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
        <line x1="3" y1="9" x2="21" y2="9"/><line x1="9" y1="21" x2="9" y2="9"/>
      </svg>
      <span>暂无数据映射信息</span>
    </div>

    <!-- 正常内容 -->
    <div v-else class="mindmap-content">
      <!-- 工具栏 -->
      <div class="toolbar">
        <div class="toolbar-title">数据映射 · {{ projectName }}</div>
        <div class="toolbar-spacer"></div>
        <button class="action-btn" @click="expandAllNodes" title="展开全部">
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <polyline points="6 9 12 15 18 9"/>
          </svg>
          展开全部
        </button>
        <button class="action-btn" @click="collapseAllNodes" title="折叠全部">
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <polyline points="6 15 12 9 18 15"/>
          </svg>
          折叠全部
        </button>
        <div class="toolbar-meta" v-if="stats">
          {{ stats.domainCount }} 域 · {{ stats.conceptCount }} 概念 · {{ stats.sourceCount }} 源 · {{ stats.fieldCount }} 映射
        </div>
      </div>

      <!-- 图例 -->
      <div class="legend-bar">
        <span class="legend-item"><span class="legend-dot dameng"></span>达梦数据库</span>
        <span class="legend-item"><span class="legend-dot excel"></span>Excel文件</span>
        <span class="legend-item"><span class="legend-dot csv"></span>CSV文件</span>
      </div>

      <!-- SVG 视口 -->
      <div ref="svgContainer" class="svg-viewport"
        @mousedown="onSvgMouseDown"
        @wheel.prevent="onSvgWheel">
        <svg :viewBox="svgViewBox" class="mindmap-svg" @wheel.prevent.stop="onSvgWheel">
          <defs>
            <filter id="mm-glow" x="-10%" y="-10%" width="120%" height="120%">
              <feGaussianBlur in="SourceGraphic" stdDeviation="1.5" result="blur"/>
              <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
            </filter>
            <filter id="mm-drop" x="-20%" y="-20%" width="140%" height="140%">
              <feDropShadow dx="0" dy="1" stdDeviation="2" flood-color="#0F172A" flood-opacity="0.08"/>
            </filter>
          </defs>

          <g :transform="`translate(${viewTransform.x},${viewTransform.y}) scale(${viewTransform.scale})`"
            :style="isDragging ? { willChange: 'transform' } : {}">
            <!-- 连线层 -->
            <g class="edges-layer">
              <template v-for="edge in edgeList" :key="edge.id">
                <path
                  :d="'M' + edge.x1 + ' ' + edge.y1
                    + ' L' + ((edge.x1 + edge.x2) / 2) + ' ' + edge.y1
                    + ' L' + ((edge.x1 + edge.x2) / 2) + ' ' + edge.y2
                    + ' L' + edge.x2 + ' ' + edge.y2"
                  fill="none"
                  :stroke="hoverHighlightEdgeIds.has(edge.id) ? COLORS.secondary : edge.lineColor"
                  :stroke-width="hoverHighlightEdgeIds.has(edge.id) ? 2 : 1"
                  :opacity="hoverHighlightEdgeIds.size > 0 && !hoverHighlightEdgeIds.has(edge.id) ? 0.15 : (edge.parentType === 'concept' ? 0.65 : 1)"
                  stroke-linecap="round" stroke-linejoin="round"
                  style="cursor: pointer; transition: opacity 0.2s, stroke-width 0.2s;"
                  @mouseenter="onEdgeEnter(edge.id)" @mouseleave="onEdgeLeave"
                />
              </template>
            </g>

            <!-- 节点层 -->
            <g class="nodes-layer">
              <template v-for="node in layoutResult.visibleNodes" :key="node.id">
                <g class="mm-node"
                  :class="{ 'mm-node-hover': hoverHighlightNodeIds.has(node.id) }"
                  :opacity="hoverHighlightNodeIds.size > 0 && !hoverHighlightNodeIds.has(node.id) && node.type !== 'root' ? 0.22 : 1"
                  style="cursor: pointer; transition: opacity 0.2s;"
                  @mouseenter="onNodeEnter(node.id)" @mouseleave="onNodeLeave"
                  @click.stop="toggleNodeCollapse(node.id)">

                  <!-- 根节点 -->
                  <template v-if="node.type === 'root'">
                    <circle :cx="node._x + NODE_DIMS.root.r" :cy="node._y + NODE_DIMS.root.r"
                      :r="NODE_DIMS.root.r" :fill="COLORS.primary"
                      :filter="hoverHighlightNodeIds.has(node.id) ? 'url(#mm-glow)' : 'url(#mm-drop)'"
                      :stroke="hoverHighlightNodeIds.has(node.id) ? COLORS.secondary : COLORS.primary" stroke-width="2"/>
                    <text :x="node._x + NODE_DIMS.root.r" :y="node._y + NODE_DIMS.root.r + 5"
                      text-anchor="middle" :fill="COLORS.white" font-size="14" font-weight="700"
                      font-family="system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
                      style="user-select: none; pointer-events: none;">{{ node.label.length > 8 ? node.label.substring(0, 8) + '…' : node.label }}</text>
                  </template>

                  <!-- 域节点 -->
                  <template v-else-if="node.type === 'domain'">
                    <rect :x="node._x" :y="node._y" :width="node._w" :height="node._h"
                      :rx="NODE_DIMS.domain.rx" :fill="node.domainColor" fill-opacity="0.1"
                      :stroke="node.domainColor" :stroke-width="hoverHighlightNodeIds.has(node.id) ? 2 : 1.5"
                      :filter="hoverHighlightNodeIds.has(node.id) ? 'url(#mm-glow)' : 'url(#mm-drop)'"/>
                    <text :x="node._x + node._w / 2" :y="node._y + node._h / 2 + 4.5"
                      text-anchor="middle" :fill="node.domainColor"
                      :font-size="NODE_DIMS.domain.fontSize" font-weight="700"
                      font-family="system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
                      style="user-select: none; pointer-events: none;">{{ node.label }}</text>
                  </template>

                  <!-- 概念节点（本体名称） -->
                  <template v-else-if="node.type === 'concept'">
                    <rect :x="node._x" :y="node._y" :width="node._w" :height="node._h"
                      :rx="NODE_DIMS.concept.rx" fill="#FFFFFF"
                      :stroke="hoverHighlightNodeIds.has(node.id) ? COLORS.secondary : '#94A3B8'"
                      :stroke-width="hoverHighlightNodeIds.has(node.id) ? 1.5 : 1"
                      :filter="hoverHighlightNodeIds.has(node.id) ? 'url(#mm-glow)' : ''"/>
                    <text :x="node._x + node._w / 2" :y="node._y + node._h / 2 + 4"
                      text-anchor="middle" :fill="COLORS.conceptGray"
                      :font-size="NODE_DIMS.concept.fontSize" font-weight="600"
                      font-family="system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
                      style="user-select: none; pointer-events: none;">{{ node.label }}</text>
                  </template>

                  <!-- 数据源节点（表名 + 类型标签） -->
                  <template v-else-if="node.type === 'source'">
                    <rect :x="node._x" :y="node._y" :width="node._w" :height="node._h"
                      :rx="NODE_DIMS.source.rx"
                      :fill="getSourceStyle(node.sourceType).bg"
                      :stroke="hoverHighlightNodeIds.has(node.id) ? getSourceStyle(node.sourceType).text : 'transparent'"
                      :stroke-width="hoverHighlightNodeIds.has(node.id) ? 1 : 0"
                      :filter="hoverHighlightNodeIds.has(node.id) ? 'url(#mm-glow)' : ''"/>
                    <text :x="node._x + NODE_PAD" :y="node._y + NODE_DIMS.source.h / 2 + 3.5"
                      :fill="getSourceStyle(node.sourceType).text" font-size="9" font-weight="700"
                      font-family="system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
                      style="user-select: none; pointer-events: none;">{{ getSourceStyle(node.sourceType).label }}</text>
                    <text :x="node._x + NODE_PAD + rawTextWidth(getSourceStyle(node.sourceType).label, 9) + 6"
                      :y="node._y + NODE_DIMS.source.h / 2 + 3.5"
                      :fill="getSourceStyle(node.sourceType).text" font-size="10.5" font-weight="500"
                      font-family="'SF Mono','Cascadia Code',Consolas,monospace"
                      style="user-select: none; pointer-events: none;">{{ node.label }}</text>
                  </template>

                  <!-- 属性映射字段节点：属性键 ← 数据库字段 -->
                  <template v-else-if="node.type === 'attr-field'">
                    <text :x="node._x + NODE_PAD" :y="node._y + node._h / 2 + 3.5"
                      :fill="hoverHighlightNodeIds.has(node.id) ? COLORS.secondary : '#0f172a'"
                      font-size="10" font-weight="600"
                      font-family="system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
                      style="user-select: none; pointer-events: none;">{{ node.attrKey }}</text>
                    <text :x="node._x + NODE_PAD + rawTextWidth(node.attrKey, 10) + 4"
                      :y="node._y + node._h / 2 + 3.5"
                      :fill="hoverHighlightNodeIds.has(node.id) ? COLORS.secondary : '#94A3B8'"
                      font-size="9" font-weight="400"
                      style="user-select: none; pointer-events: none;">←</text>
                    <text :x="node._x + NODE_PAD + rawTextWidth(node.attrKey, 10) + 14"
                      :y="node._y + node._h / 2 + 3.5"
                      :fill="hoverHighlightNodeIds.has(node.id) ? COLORS.secondary : '#64748B'"
                      font-size="10" font-weight="500"
                      font-family="'SF Mono','Cascadia Code',Consolas,monospace"
                      style="user-select: none; pointer-events: none;">{{ node.label }}</text>
                    <text :x="node._x + NODE_PAD + rawTextWidth(node.attrKey, 10) + 14 + rawTextWidth(node.label, 10) + 4"
                      :y="node._y + node._h / 2 + 3.5"
                      :fill="hoverHighlightNodeIds.has(node.id) ? COLORS.secondary : '#CBD5E1'"
                      font-size="8" font-weight="400"
                      font-family="'SF Mono','Cascadia Code',Consolas,monospace"
                      style="user-select: none; pointer-events: none;">{{ node.dataType }}</text>
                  </template>

                  <!-- 折叠按钮 -->
                  <g v-if="node.children && node.children.length > 0" class="mm-collapse"
                    :transform="'translate('
                      + (node.type === 'root' ? (node._x + NODE_DIMS.root.w + 4) : (node._x + node._w + 4))
                      + ',' + (node._y + node._h / 2) + ')'">
                    <circle cx="0" cy="0" r="7" fill="#FFFFFF" :stroke="COLORS.lineDefault" stroke-width="1"/>
                    <text x="0" y="3.5" text-anchor="middle" :fill="COLORS.textMuted"
                      font-size="12" font-weight="700"
                      font-family="system-ui, -apple-system, sans-serif">{{ isNodeCollapsed(node.id) ? '+' : '−' }}</text>
                  </g>
                </g>
              </template>
            </g>
          </g>
        </svg>

        <!-- 缩放控件 -->
        <div class="zoom-controls" @click.stop>
          <button class="zoom-btn" @click="zoomIn" title="放大">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          </button>
          <button class="zoom-btn" @click="zoomReset" title="适合窗口">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="8" y1="12" x2="16" y2="12"/></svg>
          </button>
          <button class="zoom-btn" @click="zoomOut" title="缩小">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="5" y1="12" x2="19" y2="12"/></svg>
          </button>
        </div>

      </div>
    </div>
  </div>
</template>

<style scoped>
/* 容器 */
.mindmap-view {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: #F8FAFC;
}

/* 状态覆盖层 */
.state-overlay {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  padding: 60px 24px;
  color: #64748B;
  font-size: 14px;
  font-weight: 500;
}
.state-error { color: #94A3B8; }
.state-error p { margin: 0; color: #64748B; font-weight: 600; }
.state-empty { color: #94A3B8; }

.loading-spinner {
  width: 34px; height: 34px;
  border: 3px solid #E2E8F0;
  border-top-color: #2563EB;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

.btn-retry {
  padding: 8px 22px;
  border: 1px solid #CBD5E1;
  border-radius: 8px;
  background: #FFFFFF;
  color: #334155;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  font-family: inherit;
}
.btn-retry:hover { background: #F1F5F9; border-color: #94A3B8; }

/* 内容区 */
.mindmap-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
}

/* 工具栏 */
.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 20px;
  background: #FFFFFF;
  border-bottom: 1px solid #E2E8F0;
  flex-shrink: 0;
  user-select: none;
}
.toolbar-title {
  font-size: 14px;
  font-weight: 700;
  color: #1E3A5F;
  flex-shrink: 0;
}
.toolbar-spacer { flex: 1; }

.action-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 12px;
  border: 1px solid #E2E8F0;
  border-radius: 7px;
  background: #FFFFFF;
  color: #475569;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
  font-family: inherit;
  white-space: nowrap;
}
.action-btn:hover { background: #F1F5F9; border-color: #CBD5E1; color: #1E3A5F; }

.toolbar-meta {
  font-size: 12px;
  font-weight: 500;
  color: #94A3B8;
  white-space: nowrap;
  flex-shrink: 0;
}

/* 图例栏 */
.legend-bar {
  display: flex;
  gap: 20px;
  padding: 6px 20px;
  background: #FFFFFF;
  border-bottom: 1px solid #F1F5F9;
  flex-shrink: 0;
  user-select: none;
}
.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  font-weight: 500;
  color: #64748B;
}
.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 3px;
  flex-shrink: 0;
}
.legend-dot.dameng { background: #7C3AED; }
.legend-dot.excel { background: #16A34A; }
.legend-dot.csv { background: #EA580C; }

/* SVG 视口 */
.svg-viewport {
  flex: 1;
  overflow: hidden;
  cursor: grab;
  position: relative;
  background: #F8FAFC;
  background-image: radial-gradient(circle, #E2E8F0 1px, transparent 1px);
  background-size: 20px 20px;
}
.svg-viewport:active { cursor: grabbing; }
.mindmap-svg { width: 100%; height: 100%; display: block; }

/* 缩放控件 — 与本体推理画布相同：右下角竖排 */
.zoom-controls {
  position: absolute;
  bottom: 20px;
  right: 20px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  z-index: 50;
}

.zoom-btn {
  width: 34px;
  height: 34px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.88);
  border: 1px solid #E2E8F0;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 600;
  color: #475569;
  cursor: pointer;
  transition: all 0.2s ease;
  box-shadow: 0 1px 2px rgba(0,0,0,0.04);
  line-height: 1;
}

.zoom-btn:hover {
  background: #F1F5F9;
  border-color: #CBD5E1;
  color: #1E3A5F;
}

.zoom-btn:active {
  transform: scale(0.93);
}

/* 响应式 */
@media (max-width: 800px) {
  .toolbar { padding: 8px 12px; gap: 6px; }
  .toolbar-meta { display: none; }
  .legend-bar { padding: 4px 12px; gap: 12px; }
}
</style>
