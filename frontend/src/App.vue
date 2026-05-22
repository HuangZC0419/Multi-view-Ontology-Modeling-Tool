<script setup>
import { computed, onMounted, onUnmounted, ref, nextTick } from "vue";
import PerspectiveTabs from "./components/perspective/PerspectiveTabs.vue";
import LeaderView from "./components/perspective/LeaderView.vue";
import EngineerView from "./components/perspective/EngineerView.vue";
import ProcessView from "./components/perspective/ProcessView.vue";
import DataSourcePanel from "./components/datasource/DataSourcePanel.vue";

// Use relative path for same-origin or explicit API_BASE. Fallback to current hostname with 8000 port.
const defaultApiBase = typeof window !== 'undefined' ? `http://${window.location.hostname}:8000` : "http://127.0.0.1:8000";
const API_BASE = import.meta.env.VITE_API_BASE || defaultApiBase;

const nodes = ref([]);
const edges = ref([]);
const inferenceRules = ref([]);
const mutexRules = ref([]);
const selectedNodeId = ref(null);
const selectedEdgeId = ref(null);

// 多视角
const currentPerspective = ref("process");
const perspectiveGraphData = ref(null);
const processViewRef = ref(null);

const connectMode = ref(false);
const connectSourceId = ref(null);
const statusMessage = ref("就绪");
const perspectiveStats = ref({ nodes: 0, edges: 0, inferenceRules: 0, mutexRules: 0, domains: 0 });

// 项目管理
const projects = ref([]);
const currentProjectId = ref(null);
const projectMenuOpen = ref(false);
const renamingProjectId = ref(null);
const renameValue = ref('');

const draggingNodeId = ref(null);
const dragOffset = ref({ x: 0, y: 0 });
const canvasRef = ref(null);

// 画布平移与缩放状态
const viewOffset = ref({ x: 0, y: 0 });
const zoom = ref(1);
const dragTick = ref(0); // 拖拽计数器，强制边线实时跟随
const isPanning = ref(false);
const panStart = ref({ x: 0, y: 0 });

function onWheel(event) {
  if (!canvasRef.value) return;
  
  // 缩放灵敏度
  const zoomSensitivity = 0.001;
  const delta = -event.deltaY * zoomSensitivity;
  let newZoom = zoom.value * (1 + delta);
  
  // 限制缩放范围 (10% 到 500%)
  newZoom = Math.max(0.1, Math.min(newZoom, 5));

  // 以鼠标位置为中心进行缩放
  const rect = canvasRef.value.getBoundingClientRect();
  const mouseX = event.clientX - rect.left;
  const mouseY = event.clientY - rect.top;

  const scaleRatio = newZoom / zoom.value;
  
  viewOffset.value = {
    x: mouseX - (mouseX - viewOffset.value.x) * scaleRatio,
    y: mouseY - (mouseY - viewOffset.value.y) * scaleRatio
  };
  
  zoom.value = newZoom;
}

// LLM OCR 暂停使用状态（部署至内网，暂停使用）
const llmOcrPaused = ref(true);

// 缩放控件方法
function zoomIn() {
  zoom.value = Math.min(zoom.value * 1.2, 5);
}

function zoomOut() {
  zoom.value = Math.max(zoom.value / 1.2, 0.1);
}

function zoomReset() {
  zoom.value = 1;
  viewOffset.value = { x: 0, y: 0 };
}

// 自定义 Prompt 状态
const promptState = ref({
  visible: false,
  title: "",
  value: "",
  defaultValue: "",
  placeholder: "",
  resolve: null,
  reject: null
});
const promptInputRef = ref(null);

// 自定义 Confirm 状态
const confirmState = ref({
  visible: false,
  title: "",
  message: "",
  resolve: null
});

// OCR 导入状态
const ocrFile = ref(null);
const ocrLoading = ref(false);
const ocrResult = ref(null);
const ocrCandidates = ref([]);
const ocrDialogVisible = ref(false);
const ocrPreviewUrl = ref("");
const ocrPreviewText = ref("");
const ocrPreviewType = ref("");

// 已有节点重挂载（转为子本体）状态
const reparentMode = ref(false);
const reparentSourceId = ref(null);

// 右键菜单状态
const contextMenu = ref({
  visible: false,
  x: 0,
  y: 0,
  type: 'canvas', // 'canvas' 或 'node'
  nodeId: null
});

// 节点折叠状态 (记录被折叠的节点 ID)
const collapsedNodeIds = ref(new Set());

// ========================
// 弹窗逻辑
// ========================
async function customPrompt(title, defaultValue = "", placeholder = "请输入") {
  return new Promise((resolve, reject) => {
    promptState.value = {
      visible: true,
      title,
      value: defaultValue,
      defaultValue,
      placeholder,
      resolve,
      reject
    };
    nextTick(() => {
      if (promptInputRef.value) {
        promptInputRef.value.focus();
        promptInputRef.value.select();
      }
    });
  });
}

async function customConfirm(title, message) {
  return new Promise((resolve) => {
    confirmState.value = {
      visible: true,
      title,
      message,
      resolve
    };
  });
}

function handleConfirm(result) {
  if (confirmState.value.resolve) {
    confirmState.value.resolve(result);
  }
  confirmState.value.visible = false;
}

function submitPrompt() {
  if (!promptState.value.visible) return;
  const val = promptState.value.value.trim();
  if (promptState.value.resolve) {
    promptState.value.resolve(val || null);
  }
  closePrompt();
}

function cancelPrompt() {
  if (!promptState.value.visible) return;
  if (promptState.value.resolve) {
    promptState.value.resolve(null);
  }
  closePrompt();
}

function closePrompt() {
  promptState.value.visible = false;
  promptState.value.resolve = null;
  promptState.value.reject = null;
}

function setOcrFile(file) {
  ocrFile.value = file;
  ocrResult.value = null;
  ocrCandidates.value = [];
  ocrDialogVisible.value = false;

  if (ocrPreviewUrl.value) {
    URL.revokeObjectURL(ocrPreviewUrl.value);
    ocrPreviewUrl.value = "";
  }
  ocrPreviewText.value = "";
  ocrPreviewType.value = "";

  if (file) {
    if (file.type.startsWith("image/")) {
      ocrPreviewType.value = "image";
      ocrPreviewUrl.value = URL.createObjectURL(file);
    } else {
      ocrPreviewType.value = "text";
      const reader = new FileReader();
      reader.onload = (e) => {
        ocrPreviewText.value = e.target.result;
      };
      reader.readAsText(file);
    }
  }
}

function onOcrFileChange(event) {
  const file = event.target.files?.[0] || null;
  setOcrFile(file);
}

async function useSampleOcrFile() {
  try {
    const response = await fetch(`${API_BASE}/api/ocr/sample-file`);
    if (!response.ok) {
      throw new Error(await response.text());
    }
    const blob = await response.blob();
    const sampleFile = new File([blob], "test.png", { type: blob.type || "image/png" });
    setOcrFile(sampleFile);
    statusMessage.value = "已加载示例文件 test.png，可直接开始识别";
  } catch (error) {
    statusMessage.value = `加载示例文件失败：${error.message}`;
  }
}

function toggleAllOcrCandidates(checked) {
  ocrCandidates.value = ocrCandidates.value.map((item) => ({ ...item, selected: checked }));
}

const selectedOcrEntities = computed(() =>
  ocrCandidates.value.filter((item) => item.selected).map((item) => item.text)
);

// 规则管理
const rulesDialogVisible = ref(false);
const activeTab = ref('mutex'); // 'mutex' | 'inference'

// 贝叶斯分析
const bayesianDialogVisible = ref(false);
const bayesianTab = ref('upstream'); // 'upstream' | 'downstream' | 'overview'
const weightDialogVisible = ref(false); // 独立的权重配置弹窗
const bayesianLoading = ref(false);

// 上游追溯
const upstreamTargetId = ref('');
const upstreamResult = ref(null);

// 下游传播
const downstreamSourceId = ref('');
const downstreamResult = ref(null);

// 全局概览
const overviewResult = ref(null);

// 权重配置
const weightConfig = ref({}); // { "控制": 0.80, "影响": 0.50 }
const newWeightRelation = ref('');
const newWeightValue = ref(0.7);

// 画布高亮
const highlightedNodeIds = ref(new Set());
const highlightedEdgeIds = ref(new Set());
const highlightEnabled = ref(false);
const newMutex = ref({ rel1: '', rel2: '' });
const newInference = ref({ rel1: '', rel2: '', inferred_rel: '' });
const uniqueRelations = computed(() => Array.from(new Set(edges.value.map(e => e.relation))).filter(Boolean));
const maxIncoming = computed(() => {
  if (!overviewResult.value?.vulnerability_ranking?.length) return 1;
  return Math.max(...overviewResult.value.vulnerability_ranking.map(v => v.incoming_links), 1);
});

function addMutexRule() {
  if (!newMutex.value.rel1 || !newMutex.value.rel2) {
    statusMessage.value = "请填写完整的互斥关系";
    return;
  }
  mutexRules.value.push({
    id: Date.now().toString(),
    rel1: newMutex.value.rel1,
    rel2: newMutex.value.rel2
  });
  newMutex.value = { rel1: '', rel2: '' };
  syncGraph();
}

function removeMutexRule(id) {
  mutexRules.value = mutexRules.value.filter(r => r.id !== id);
  syncGraph();
}

function addInferenceRule() {
  if (!newInference.value.rel1 || !newInference.value.rel2 || !newInference.value.inferred_rel) {
    statusMessage.value = "请填写完整的推理关系";
    return;
  }
  inferenceRules.value.push({
    id: Date.now().toString(),
    rel1: newInference.value.rel1,
    rel2: newInference.value.rel2,
    inferred_rel: newInference.value.inferred_rel
  });
  newInference.value = { rel1: '', rel2: '', inferred_rel: '' };
  syncGraph();
}

function removeInferenceRule(id) {
  inferenceRules.value = inferenceRules.value.filter(r => r.id !== id);
  syncGraph();
}

// ========================
// 核心逻辑 & 节点展示
// ========================
const selectedNode = computed(() =>
  nodes.value.find((node) => node.id === selectedNodeId.value)
);

const selectedEdge = computed(() =>
  edges.value.find((edge) => edge.id === selectedEdgeId.value)
);

// 删除逻辑
async function deleteSelectedNode() {
  if (!selectedNode.value) return;
  const confirmed = await customConfirm("删除本体", `确定要删除本体 "${selectedNode.value.name}" 及其所有关联关系吗？`);
  if (!confirmed) return;
  
  const id = selectedNode.value.id;
  nodes.value = nodes.value.filter(n => n.id !== id);
  edges.value = edges.value.filter(e => e.source !== id && e.target !== id);
  selectedNodeId.value = null;
  await syncGraph();
  statusMessage.value = "已删除本体";
}

async function deleteSelectedEdge() {
  if (!selectedEdge.value) return;
  const confirmed = await customConfirm("删除关系", `确定要删除该关系吗？`);
  if (!confirmed) return;

  const id = selectedEdge.value.id;
  edges.value = edges.value.filter(e => e.id !== id);
  selectedEdgeId.value = null;
  await syncGraph();
  statusMessage.value = "已删除关系";
}

// 属性编辑逻辑
function addAttribute() {
  if (!selectedNode.value) return;
  if (!selectedNode.value.attributes) {
    selectedNode.value.attributes = [];
  }
  selectedNode.value.attributes.push({ key: "新属性", value: "" });
  syncGraph();
}

function removeAttribute(idx) {
  if (!selectedNode.value) return;
  selectedNode.value.attributes.splice(idx, 1);
  syncGraph();
}

function updateAttribute() {
  syncGraph();
}

// 关系特征编辑逻辑
function toggleCharacteristic(char) {
  if (!selectedEdge.value) return;
  if (!selectedEdge.value.characteristics) {
    selectedEdge.value.characteristics = [];
  }
  const idx = selectedEdge.value.characteristics.indexOf(char);
  if (idx > -1) {
    selectedEdge.value.characteristics.splice(idx, 1);
  } else {
    selectedEdge.value.characteristics.push(char);
  }
  syncGraph();
}

// 递归查找被折叠节点的所有子孙节点
const hiddenNodeIds = computed(() => {
  const hidden = new Set();
  const hideChildren = (parentId) => {
    nodes.value.forEach(n => {
      if (n.parent_id === parentId) {
        hidden.add(n.id);
        hideChildren(n.id);
      }
    });
  };
  collapsedNodeIds.value.forEach(id => hideChildren(id));
  return hidden;
});

// 过滤掉被隐藏的节点和连线
const visibleNodes = computed(() => 
  nodes.value.filter(n => !hiddenNodeIds.value.has(n.id))
);

const visibleEdges = computed(() => 
  edges.value.filter(e => !hiddenNodeIds.value.has(e.source) && !hiddenNodeIds.value.has(e.target))
);

const nodeMap = computed(() => {
  const map = new Map();
  visibleNodes.value.forEach((node) => map.set(node.id, node));
  return map;
});

// 计算从矩形中心指向外部点的射线与矩形边界的交点
// 用于让连线端点落在节点矩形边框上，而非被卡片遮挡
function lineRectIntersection(outX, outY, rectX, rectY, rectW, rectH) {
  const cx = rectX + rectW / 2;
  const cy = rectY + rectH / 2;
  const dx = outX - cx;
  const dy = outY - cy;

  if (Math.abs(dx) < 0.001 && Math.abs(dy) < 0.001) return { x: cx, y: cy };

  let tMin = Infinity;

  // 右边: x = rectX + rectW
  if (dx > 0) {
    const t = (rectX + rectW - cx) / dx;
    const hitY = cy + t * dy;
    if (hitY >= rectY && hitY <= rectY + rectH && t < tMin) tMin = t;
  }
  // 左边: x = rectX
  if (dx < 0) {
    const t = (rectX - cx) / dx;
    const hitY = cy + t * dy;
    if (hitY >= rectY && hitY <= rectY + rectH && t < tMin) tMin = t;
  }
  // 下边: y = rectY + rectH
  if (dy > 0) {
    const t = (rectY + rectH - cy) / dy;
    const hitX = cx + t * dx;
    if (hitX >= rectX && hitX <= rectX + rectW && t < tMin) tMin = t;
  }
  // 上边: y = rectY
  if (dy < 0) {
    const t = (rectY - cy) / dy;
    const hitX = cx + t * dx;
    if (hitX >= rectX && hitX <= rectX + rectW && t < tMin) tMin = t;
  }

  return { x: cx + tMin * dx, y: cy + tMin * dy };
}

const edgeViews = computed(() => {
  // 读取 dragTick 强制在拖拽时重新计算
  dragTick.value;
  return visibleEdges.value
    .map((edge) => {
      const source = nodeMap.value.get(edge.source);
      const target = nodeMap.value.get(edge.target);
      if (!source || !target) {
        return null;
      }

      // 节点中心和尺寸
      const srcCX = source.x + 100;
      const srcCY = source.y + 35;
      const tgtCX = target.x + 100;
      const tgtCY = target.y + 35;

      // 起点 = 以 target 中心为外部点，射线与 source 矩形边界的交点
      const srcPt = lineRectIntersection(tgtCX, tgtCY, source.x, source.y, 200, 70);
      // 终点 = 以 source 中心为外部点，射线与 target 矩形边界的交点
      const tgtPt = lineRectIntersection(srcCX, srcCY, target.x, target.y, 200, 70);

      const x1 = srcPt.x;
      const y1 = srcPt.y;
      const x2 = tgtPt.x;
      const y2 = tgtPt.y;

      let path = "";
      if (edge.kind === "parent-child") {
        // 树状正交折线 (Orthogonal Line)
        const midY = y1 + (y2 - y1) / 2;
        path = `M ${x1} ${y1} L ${x1} ${midY} L ${x2} ${midY} L ${x2} ${y2}`;

        const labelX = (x1 + x2) / 2;
        const labelY = (y1 + y2) / 2;
        const effWeight = edge.weight != null ? edge.weight : 0.5;
        const weightPct = (effWeight * 100).toFixed(0);
        const displayRelation = edge.relation + ' · ' + weightPct + '%';
        return { ...edge, x1, y1, x2, y2, labelX, labelY, path, displayRelation };
      } else {
        // 普通关系线使用二次贝塞尔曲线
        const dx = x2 - x1;
        const dy = y2 - y1;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const cx = (x1 + x2) / 2;
        const cy = (y1 + y2) / 2 + dist * 0.15;
        path = `M ${x1} ${y1} Q ${cx} ${cy} ${x2} ${y2}`;
        const labelX = 0.25 * x1 + 0.5 * cx + 0.25 * x2;
        const labelY = 0.25 * y1 + 0.5 * cy + 0.25 * y2;
        const effWeight = edge.weight != null ? edge.weight : 0.5;
        const weightPct = (effWeight * 100).toFixed(0);
        const displayRelation = edge.relation + ' · ' + weightPct + '%';
        return { ...edge, x1, y1, x2, y2, cx, cy, labelX, labelY, path, displayRelation };
      }
    })
    .filter(Boolean);
});

// 辅助方法：检查节点是否有子节点
function hasChildren(nodeId) {
  return nodes.value.some(n => n.parent_id === nodeId);
}

// 展开/折叠切换
function toggleCollapse(nodeId) {
  const newSet = new Set(collapsedNodeIds.value);
  if (newSet.has(nodeId)) {
    newSet.delete(nodeId);
  } else {
    newSet.add(nodeId);
  }
  collapsedNodeIds.value = newSet;
  hideContextMenu();
}

// ========================
// 右键菜单逻辑
// ========================
function showContextMenu(event, type, nodeId = null) {
  if (!canvasRef.value) return;
  const rect = canvasRef.value.getBoundingClientRect();
  contextMenu.value = {
    visible: true,
    x: event.clientX - rect.left,
    y: event.clientY - rect.top,
    type,
    nodeId
  };
}

function hideContextMenu() {
  contextMenu.value.visible = false;
}

// 从菜单开始连线
function startConnectionFromMenu(nodeId) {
  hideContextMenu();
  selectedNodeId.value = nodeId;
  enableConnectMode();
}

// ========================
// 项目管理方法
// ========================
async function loadProjects() {
  try {
    const data = await request("/api/projects");
    projects.value = data;
    if (!currentProjectId.value && data.length) {
      currentProjectId.value = data[0].id;
      await loadGraph(currentProjectId.value);
    }
  } catch (error) {
    statusMessage.value = `加载项目列表失败：${error.message}`;
  }
}

async function switchProject(id) {
  currentProjectId.value = id;
  selectedNodeId.value = null;
  selectedEdgeId.value = null;
  // 重置贝叶斯分析状态
  upstreamResult.value = null;
  downstreamResult.value = null;
  overviewResult.value = null;
  upstreamTargetId.value = '';
  downstreamSourceId.value = '';
  clearHighlight();
  await loadGraph(id);
  statusMessage.value = "已切换项目";
}

async function createProject() {
  const name = await customPrompt("新建项目", "", "输入项目名称");
  if (!name) return;
  const proj = await request("/api/projects", { method: "POST", body: JSON.stringify({ name }) });
  projects.value.push(proj);
  await switchProject(proj.id);
}

async function deleteProject(id) {
  const proj = projects.value.find(p => p.id === id);
  if (!proj) return;
  const confirmed = await customConfirm("删除项目", `确定删除项目"${proj.name}"吗？`);
  if (!confirmed) return;
  await request(`/api/projects/${id}`, { method: "DELETE" });
  projects.value = projects.value.filter(p => p.id !== id);
  if (currentProjectId.value === id) {
    currentProjectId.value = projects.value[0]?.id || null;
    if (currentProjectId.value) await loadGraph(currentProjectId.value);
    else { nodes.value = []; edges.value = []; }
  }
  statusMessage.value = "项目已删除";
}

function startRename(id) {
  renamingProjectId.value = id;
  renameValue.value = projects.value.find(p => p.id === id)?.name || '';
}

async function finishRename(id) {
  if (renamingProjectId.value !== id) return;
  const name = renameValue.value.trim();
  if (name) {
    await request(`/api/projects/${id}`, { method: "PUT", body: JSON.stringify({ name }) });
    const p = projects.value.find(p => p.id === id);
    if (p) p.name = name;
  }
  renamingProjectId.value = null;
}

async function request(path, options = {}) {
  const isFormData = options.body instanceof FormData;
  const headers = isFormData
    ? { ...(options.headers || {}) }
    : { "Content-Type": "application/json", ...(options.headers || {}) };
  const response = await fetch(`${API_BASE}${path}`, {
    headers,
    ...options
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}

async function loadGraph(projectId) {
  // 若从模板事件调用（接收到 Event 对象）或未传参，回退到当前项目
  const pid = (typeof projectId === 'string' || typeof projectId === 'number') ? projectId : currentProjectId.value;
  if (!pid) {
    nodes.value = [];
    edges.value = [];
    inferenceRules.value = [];
    mutexRules.value = [];
    statusMessage.value = "无项目选中";
    return;
  }
  try {
    const graph = await request(`/api/graph?project_id=${pid}`);
    nodes.value = graph.nodes || [];
    edges.value = graph.edges || [];
    inferenceRules.value = graph.inference_rules || [];
    mutexRules.value = graph.mutex_rules || [];
    statusMessage.value = "已加载后端数据";
    // 加载权重配置
    await loadWeightConfig();
  } catch (error) {
    statusMessage.value = `加载失败：${error.message}`;
  }
}

async function syncGraph(projectId) {
  // 若从模板事件调用（接收到 Event 对象）或未传参，回退到当前项目
  const pid = (typeof projectId === 'string' || typeof projectId === 'number') ? projectId : currentProjectId.value;
  if (!pid) {
    statusMessage.value = "无项目选中，无法保存";
    return;
  }
  try {
    await request(`/api/graph?project_id=${pid}`, {
      method: "PUT",
      body: JSON.stringify({
        nodes: nodes.value,
        edges: edges.value,
        inference_rules: inferenceRules.value,
        mutex_rules: mutexRules.value
      })
    });
  } catch (error) {
    statusMessage.value = `同步失败：${error.message}`;
  }
}

function canUseLlmOcr() {
  if (!ocrFile.value) return false;
  const type = ocrFile.value.type || "";
  const name = (ocrFile.value.name || "").toLowerCase();
  return type.startsWith("image/") || [".png", ".jpg", ".jpeg", ".bmp", ".webp"].some((ext) => name.endsWith(ext));
}

async function runOcrExtract(engine = "local") {
  if (!ocrFile.value) {
    statusMessage.value = "请先选择文件";
    return;
  }
  if (engine === "llm" && !canUseLlmOcr()) {
    statusMessage.value = "大模型 OCR 目前仅支持图片文件";
    return;
  }
  try {
    ocrLoading.value = true;
    const formData = new FormData();
    formData.append("file", ocrFile.value);
    const result = await request(`/api/ocr/extract?engine=${engine}`, {
      method: "POST",
      body: formData
    });
    ocrResult.value = result;
    ocrCandidates.value = (result.entities || []).map((text) => ({
      text,
      selected: true
    }));
    ocrDialogVisible.value = true;
    statusMessage.value = `${engine === "llm" ? "大模型 OCR" : "本地 OCR"} 识别完成：${ocrCandidates.value.length} 项`;
  } catch (error) {
    statusMessage.value = `${engine === "llm" ? "大模型 OCR" : "本地 OCR"} 识别失败：${error.message}`;
  } finally {
    ocrLoading.value = false;
  }
}

async function importOcrToCanvas() {
  const entities = selectedOcrEntities.value;
  if (!entities.length) {
    statusMessage.value = "请至少勾选一项再导入";
    return;
  }
  try {
    const payload = {
      entities,
      start_x: 120 - viewOffset.value.x,
      start_y: 120 - viewOffset.value.y,
      spacing_x: 180,
      spacing_y: 120
    };
    const result = await request("/api/ocr/import", {
      method: "POST",
      body: JSON.stringify(payload)
    });
    await loadGraph();
    ocrDialogVisible.value = false;
    statusMessage.value = `已导入 ${result.created_count} 项，跳过 ${result.skipped_entities.length} 项`;
  } catch (error) {
    statusMessage.value = `导入失败：${error.message}`;
  }
}

async function createNode(payload) {
  const node = await request("/api/nodes", {
    method: "POST",
    body: JSON.stringify(payload)
  });
  // 必须重新加载图，因为后端会同步创建父子关系连线
  await loadGraph();
  return node;
}

async function createEdge(payload) {
  const edge = await request("/api/edges", {
    method: "POST",
    body: JSON.stringify(payload)
  });
  // 同样重新加载以保持同步
  await loadGraph();
  return edge;
}

async function reparentNode(nodeId, newParentId) {
  return request(`/api/nodes/${nodeId}/reparent`, {
    method: "POST",
    body: JSON.stringify({ new_parent_id: newParentId })
  });
}

async function clearGraph() {
  const confirmed = await customConfirm("清空画布", "确定要清空当前画布上的所有本体和关系吗？此操作不可撤销。");
  if (!confirmed) return;
  try {
    nodes.value = [];
    edges.value = [];
    await syncGraph();
    statusMessage.value = "画布已清空";
    selectedNodeId.value = null;
    collapsedNodeIds.value = new Set();
  } catch (error) {
    statusMessage.value = `清空失败：${error.message}`;
  }
}

async function addOntology(x = null, y = null) {
  const name = await customPrompt("请输入本体名称", "", "如：Person");
  if (!name) return;

  try {
    const node = await createNode({
      name,
      x: x !== null ? x : (120 + Math.random() * 220 - viewOffset.value.x) / zoom.value,
      y: y !== null ? y : (120 + Math.random() * 220 - viewOffset.value.y) / zoom.value
    });
    selectedNodeId.value = node.id;
    statusMessage.value = "已新增本体";
  } catch (error) {
    statusMessage.value = `新增失败：${error.message}`;
  }
}

async function addRootOntologyMenu() {
  const { x, y } = contextMenu.value;
  hideContextMenu();
  // 修正侧边栏宽度带来的偏移，并考虑画布平移与缩放
  await addOntology((x - viewOffset.value.x) / zoom.value, (y - viewOffset.value.y) / zoom.value);
}

async function addChildOntology(parentId = null) {
  const targetParentId = parentId || selectedNodeId.value;
  if (!targetParentId) {
    statusMessage.value = "请先选中一个父本体";
    return;
  }
  hideContextMenu();

  const parentNode = nodes.value.find(n => n.id === targetParentId);
  if (!parentNode) return;

  const name = await customPrompt("请输入子本体名称", "", "如：Student");
  if (!name) return;

  // 树状布局计算 (水平铺开)
  const siblings = nodes.value.filter(n => n.parent_id === targetParentId);
  const xOffset = siblings.length * 180 - (siblings.length > 0 ? 90 : 0);

  try {
    await createNode({
      name,
      x: parentNode.x + xOffset,
      y: parentNode.y + 130, // 自动放置在父节点正下方
      parent_id: targetParentId
    });
    
    // 如果父节点被折叠，自动展开
    if (collapsedNodeIds.value.has(targetParentId)) {
      toggleCollapse(targetParentId);
    }
    statusMessage.value = "已新增子本体";
  } catch (error) {
    statusMessage.value = `新增失败：${error.message}`;
  }
}

function enableConnectMode() {
  if (!selectedNodeId.value) {
    statusMessage.value = "请先选中一个起始本体";
    return;
  }
  connectMode.value = true;
  connectSourceId.value = selectedNodeId.value;
  reparentMode.value = false;
  reparentSourceId.value = null;
  statusMessage.value = "连线模式：请点击目标本体";
}

function cancelConnectMode() {
  connectMode.value = false;
  connectSourceId.value = null;
}

function enableReparentMode(nodeId = null) {
  const sourceId = nodeId || selectedNodeId.value;
  if (!sourceId) {
    statusMessage.value = "请先选择要移动的本体";
    return;
  }
  reparentMode.value = true;
  reparentSourceId.value = sourceId;
  connectMode.value = false;
  connectSourceId.value = null;
  statusMessage.value = "子本体模式：请点击目标父本体";
}

function cancelReparentMode() {
  reparentMode.value = false;
  reparentSourceId.value = null;
}

function startReparentFromMenu(nodeId) {
  hideContextMenu();
  selectedNodeId.value = nodeId;
  enableReparentMode(nodeId);
}

async function onClickNode(nodeId) {
  selectedNodeId.value = nodeId;
  selectedEdgeId.value = null;
  if (reparentMode.value) {
    if (!reparentSourceId.value) {
      reparentSourceId.value = nodeId;
      statusMessage.value = "已设置待移动本体，请选择目标父本体";
      return;
    }
    if (reparentSourceId.value === nodeId) {
      statusMessage.value = "目标父本体不能与当前本体相同";
      return;
    }
    try {
      await reparentNode(reparentSourceId.value, nodeId);
      await loadGraph();
      statusMessage.value = "已更新父子关系";
    } catch (error) {
      statusMessage.value = `更新父子关系失败：${error.message}`;
    } finally {
      cancelReparentMode();
    }
    return;
  }

  if (!connectMode.value) return;

  if (!connectSourceId.value) {
    connectSourceId.value = nodeId;
    statusMessage.value = "已设置起始本体，请选择目标本体";
    return;
  }

  if (connectSourceId.value === nodeId) {
    statusMessage.value = "起始和目标不能相同";
    return;
  }

  const relation = await customPrompt("请输入关系名称", "关联", "例如：关联、依赖、包含");
  if (!relation) return;

  try {
    await createEdge({
      source: connectSourceId.value,
      target: nodeId,
      relation,
      kind: "relation"
    });
    await loadGraph(); // 重新加载以获取可能通过规则自动推导出的新边
    statusMessage.value = "已创建本体关系。请继续选择下一个起始本体，或取消连线模式。";
  } catch (error) {
    statusMessage.value = `创建关系失败：${error.message}`;
  } finally {
    // 保持连线模式开启，只清空起始节点，以便连续连线
    connectSourceId.value = null;
  }
}

function startDrag(event, node) {
  draggingNodeId.value = node.id;
  dragOffset.value = {
    x: (event.clientX - viewOffset.value.x) / zoom.value - node.x,
    y: (event.clientY - viewOffset.value.y) / zoom.value - node.y
  };
}

function startPanning(event) {
  if (event.button !== 0) return; // 仅左键平移
  // 弹窗或右键菜单打开时，不启动平移
  if (promptState.value.visible || confirmState.value.visible || ocrDialogVisible.value || contextMenu.value.visible || rulesDialogVisible.value || bayesianDialogVisible.value || weightDialogVisible.value || projectMenuOpen.value) return;
  isPanning.value = true;
  panStart.value = {
    x: event.clientX - viewOffset.value.x,
    y: event.clientY - viewOffset.value.y
  };
}

async function onPointerMove(event) {
  if (draggingNodeId.value) {
    const node = nodes.value.find((item) => item.id === draggingNodeId.value);
    if (!node) return;
    node.x = (event.clientX - viewOffset.value.x) / zoom.value - dragOffset.value.x;
    node.y = (event.clientY - viewOffset.value.y) / zoom.value - dragOffset.value.y;
    dragTick.value++; // 强制边线实时跟随
  } else if (isPanning.value) {
    viewOffset.value = {
      x: event.clientX - panStart.value.x,
      y: event.clientY - panStart.value.y
    };
  }
}

async function onPointerUp() {
  if (draggingNodeId.value) {
    draggingNodeId.value = null;
    try {
      await syncGraph();
      statusMessage.value = "位置已保存";
    } catch (error) {
      statusMessage.value = `保存位置失败：${error.message}`;
    }
  }
  isPanning.value = false;
}

// ========================
// 符号格式化逻辑
// ========================
function formatSymbol(text) {
  if (!text) return "";

  // 仅对高置信度的物理量符号做格式化，避免把普通英文词错误渲染为上下标
  // 1) 下划线模式：Q_p, TDS_in, p_var
  const underscoreMatch = text.match(/^([A-Za-z]{1,5})_([A-Za-z0-9]{1,8})$/);
  if (underscoreMatch) {
    return `<i>${underscoreMatch[1]}</i><sub>${underscoreMatch[2]}</sub>`;
  }

  // 2) 数字下标模式：CO2, O3
  const numericSubMatch = text.match(/^([A-Za-z]{1,5})(\d{1,3})$/);
  if (numericSubMatch) {
    return `${numericSubMatch[1]}<sub>${numericSubMatch[2]}</sub>`;
  }

  // 3) 常见工程符号后缀：Qp/Qpp, vp, pvar/pfix/pperf, TDSin/TDSout
  const suffixMatch = text.match(/^([A-Za-z]{1,5})(in|out|pp|var|fix|perf)$/);
  if (suffixMatch) {
    return `<i>${suffixMatch[1]}</i><sub>${suffixMatch[2]}</sub>`;
  }

  return text;
}

function openHelp() {
  window.open('/help.html', '_blank');
}

function handleGlobalKeyDown(e) {
  if (e.key === "Escape") {
    if (connectMode.value) {
      cancelConnectMode();
      statusMessage.value = "已取消连线模式";
    }
    if (reparentMode.value) {
      cancelReparentMode();
      statusMessage.value = "已取消子本体模式";
    }
  }
}

// 贝叶斯分析方法

// 加载项目的权重配置
async function loadWeightConfig() {
  try {
    const data = await request(`/api/bayesian/weights/${currentProjectId.value}`);
    if (data && data.relation_weights) {
      weightConfig.value = data.relation_weights;
    }
  } catch (e) {
    // 无配置时使用默认空对象
  }
}

async function saveWeightConfig() {
  try {
    await request(`/api/bayesian/weights/${currentProjectId.value}`, {
      method: 'PUT',
      body: JSON.stringify({ relation_weights: weightConfig.value })
    });
    statusMessage.value = "权重配置已保存";
  } catch (e) {
    statusMessage.value = `保存失败：${e.message}`;
  }
}

function addWeightMapping() {
  if (!newWeightRelation.value.trim()) return;
  weightConfig.value[newWeightRelation.value.trim()] = newWeightValue.value;
  newWeightRelation.value = '';
}

function removeWeightMapping(key) {
  delete weightConfig.value[key];
}

async function runUpstreamAnalysis() {
  if (!upstreamTargetId.value) { statusMessage.value = "请选择目标节点"; return; }
  bayesianLoading.value = true;
  try {
    upstreamResult.value = await request(
      `/api/bayesian/trace-upstream/${currentProjectId.value}?target=${upstreamTargetId.value}`
    );
    highlightPath(upstreamResult.value);
  } catch (e) { statusMessage.value = `分析失败：${e.message}`; }
  finally { bayesianLoading.value = false; }
}

async function runDownstreamAnalysis() {
  if (!downstreamSourceId.value) { statusMessage.value = "请选择因子节点"; return; }
  bayesianLoading.value = true;
  try {
    downstreamResult.value = await request(
      `/api/bayesian/propagate-downstream/${currentProjectId.value}?source=${downstreamSourceId.value}`
    );
    highlightPath(downstreamResult.value);
  } catch (e) { statusMessage.value = `分析失败：${e.message}`; }
  finally { bayesianLoading.value = false; }
}

function getProbLevel(prob) {
  if (prob >= 0.7) return 'high';
  if (prob >= 0.4) return 'mid';
  if (prob >= 0.15) return 'low';
  return 'none';
}

async function runOverviewAnalysis() {
  bayesianLoading.value = true;
  try {
    overviewResult.value = await request(`/api/bayesian/overview/${currentProjectId.value}`);
    // 高亮最强路径中的节点
    if (overviewResult.value && overviewResult.value.strongest_paths) {
      const nodeIds = new Set();
      overviewResult.value.strongest_paths.forEach(p => {
        const parts = p.path.split(' → ');
        parts.forEach(name => {
          const node = nodes.value.find(n => n.name === name);
          if (node) nodeIds.add(node.id);
        });
      });
      highlightedNodeIds.value = nodeIds;
      highlightEnabled.value = true;
    }
  } catch (e) { statusMessage.value = `分析失败：${e.message}`; }
  finally { bayesianLoading.value = false; }
}

// 画布联动：高亮影响路径中的节点和边
function highlightPath(result) {
  highlightedNodeIds.value = new Set();
  highlightedEdgeIds.value = new Set();
  if (!result) return;

  // 从 result 中提取所有涉及的节点名称
  const nodeNamesToHighlight = new Set();

  // 上游追溯结果
  if (result.factors) {
    result.factors.forEach(f => {
      if (f.paths) {
        f.paths.forEach(p => {
          const parts = p.path.split(' → ');
          parts.forEach(n => nodeNamesToHighlight.add(n.trim()));
        });
      }
    });
  }
  // 下游传播结果
  if (result.effects) {
    result.effects.forEach(e => {
      if (e.paths) {
        e.paths.forEach(p => {
          const parts = p.path.split(' → ');
          parts.forEach(n => nodeNamesToHighlight.add(n.trim()));
        });
      }
    });
  }

  // 将名称映射到节点ID
  const nameToId = {};
  nodes.value.forEach(n => { nameToId[n.name] = n.id; });

  nodeNamesToHighlight.forEach(name => {
    if (nameToId[name]) highlightedNodeIds.value.add(nameToId[name]);
  });

  highlightEnabled.value = true;
}

function clearHighlight() {
  highlightedNodeIds.value = new Set();
  highlightedEdgeIds.value = new Set();
  highlightEnabled.value = false;
}

// ========================
// 多视角切换逻辑
// ========================
function onPerspectiveChange(key) {
  currentPerspective.value = key;
}

function onGraphLoaded(data) {
  perspectiveGraphData.value = data;
}

function onStats(stats) {
  perspectiveStats.value = stats;
}

function onImportNodes(importedNodes) {
  if (importedNodes && importedNodes.length > 0) {
    nodes.value = [...nodes.value, ...importedNodes];
    syncGraph(currentProjectId.value);
  }
}

onMounted(() => {
  loadProjects();
  window.addEventListener("pointermove", onPointerMove);
  window.addEventListener("pointerup", onPointerUp);
  window.addEventListener("keydown", handleGlobalKeyDown);
});

onUnmounted(() => {
  window.removeEventListener("pointermove", onPointerMove);
  window.removeEventListener("pointerup", onPointerUp);
  window.removeEventListener("keydown", handleGlobalKeyDown);
});
</script>

<template>
  <div class="app-container" @click="hideContextMenu">
    <!-- 全局关系数据列表，供所有的 input list="rel-list" 使用 -->
    <datalist id="rel-list">
      <option v-for="r in uniqueRelations" :key="r" :value="r"></option>
    </datalist>

    <aside class="sidebar" @click.stop>
      <div class="sidebar-header">
        <div class="logo">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="5" r="3"></circle><circle cx="6" cy="12" r="3"></circle><circle cx="18" cy="19" r="3"></circle><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line></svg>
        </div>
        <h2>本体建模系统</h2>
        <div class="project-selector" @click.stop>
          <button class="ps-trigger" @click="projectMenuOpen = !projectMenuOpen">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
            <span class="ps-current-name">{{ projects.find(p => p.id === currentProjectId)?.name || '选择项目' }}</span>
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="6 9 12 15 18 9"/></svg>
          </button>
          <div class="ps-dropdown" v-if="projectMenuOpen">
            <div class="ps-list">
              <div v-for="proj in projects" :key="proj.id" class="ps-item" :class="{ active: currentProjectId === proj.id }" @click="switchProject(proj.id); projectMenuOpen = false">
                <svg class="ps-item-dot" v-if="currentProjectId === proj.id" width="6" height="6" viewBox="0 0 6 6"><circle cx="3" cy="3" r="3" fill="#1E40AF"/></svg>
                <span v-else class="ps-item-dot" style="width:6px;flex-shrink:0"></span>
                <span class="ps-item-name" v-if="renamingProjectId !== proj.id">{{ proj.name }}</span>
                <input v-else class="ps-rename-input" v-model="renameValue" @keyup.enter="finishRename(proj.id)" @keyup.esc="renamingProjectId = null" @blur="finishRename(proj.id)" @click.stop />
                <div class="ps-item-actions" v-if="renamingProjectId !== proj.id">
                  <button @click.stop="startRename(proj.id)" title="重命名"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 3a2.85 2.85 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/></svg></button>
                  <button @click.stop="deleteProject(proj.id)" title="删除"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/></svg></button>
                </div>
              </div>
            </div>
            <div class="ps-footer">
              <button class="ps-new-btn" @click="createProject(); projectMenuOpen = false">+ 新建项目</button>
            </div>
          </div>
        </div>
      </div>
      
      <div class="sidebar-content">
        <div class="action-group">
          <h3 class="group-title">画布操作</h3>
          <button class="btn btn-primary" @click="addOntology(null, null)">
            <span class="icon">＋</span> 新增独立本体
          </button>
          <button class="btn btn-secondary" @click="syncGraph">
            <span class="icon">💾</span> 保存当前画布
          </button>
          <button class="btn btn-danger" @click="clearGraph">
            <span class="icon">🗑️</span> 一键清空画布
          </button>
        </div>

        <div class="action-group">
          <h3 class="group-title">关系连接</h3>
          <button 
            class="btn btn-outline" 
            :class="{ active: connectMode }" 
            :disabled="!selectedNodeId && !connectMode"
            @click="connectMode ? cancelConnectMode() : enableConnectMode()"
          >
            <span class="icon">🔗</span> {{ connectMode ? '取消连线 (Esc)' : '开启连线模式' }}
          </button>
          <button
            class="btn btn-outline"
            :class="{ active: reparentMode }"
            :disabled="!selectedNodeId && !reparentMode"
            @click="reparentMode ? cancelReparentMode() : enableReparentMode()"
          >
            <span class="icon">🌳</span> {{ reparentMode ? '取消子本体模式' : '转为子本体模式' }}
          </button>
          <button class="btn btn-secondary" @click="rulesDialogVisible = true">
            <span class="icon">⚙️</span> 关系逻辑规则设置
          </button>
          <p class="tip-text" v-if="connectMode">请在画布点击目标本体</p>
          <p class="tip-text" v-if="reparentMode">先选待移动本体，再点目标父本体</p>
        </div>

        <div class="action-group">
          <h3 class="group-title">因果分析</h3>
          <button class="btn btn-bayesian" @click="bayesianDialogVisible = true">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="10"/>
              <path d="M12 6v6l4 2"/>
            </svg>
            贝叶斯网络分析
          </button>
          <button class="btn btn-weight-config" @click="weightDialogVisible = true">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/><line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/><line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/><line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" x2="15" y2="8"/><line x1="17" y1="16" x2="23" y2="16"/>
            </svg>
            关系权重配置
          </button>
        </div>

        <div class="action-group">
          <h3 class="group-title">数据导入</h3>
          <DataSourcePanel @import-nodes="onImportNodes" />
        </div>

        <div class="action-group">
          <h3 class="group-title">OCR 导入</h3>
          <button class="btn btn-ghost" :disabled="ocrLoading" @click="useSampleOcrFile">
            <span class="icon">🧪</span> 使用示例文件 test.png
          </button>
          <input
            class="file-input"
            type="file"
            accept=".png,.jpg,.jpeg,.bmp,.webp,.txt,.csv"
            @change="onOcrFileChange"
          />
          <button class="btn btn-secondary" :disabled="!ocrFile || ocrLoading" @click="runOcrExtract('local')">
            <span class="icon">🔍</span> {{ ocrLoading ? "识别中..." : "本地识别" }}
          </button>
          <!-- 大模型识别：部署至内网，暂停使用 -->
          <button class="btn btn-primary" disabled title="部署至内网，暂停使用">
            <span class="icon">🤖</span> 大模型识别
          </button>
          <div class="llm-paused-badge">
            <span class="pause-icon">⏸</span> 大模型识别暂不可用（内网环境）
          </div>
          <button class="btn btn-outline" v-if="ocrResult" @click="ocrDialogVisible = true">
            <span class="icon">📋</span> 查看识别结果
          </button>
        </div>
      </div>

      <div class="sidebar-footer">
        <div class="status-panel" :class="{ error: statusMessage.includes('失败'), success: statusMessage.includes('已') }">
          <div class="status-indicator"></div>
          <span class="status-text">{{ statusMessage }}</span>
        </div>

        <!-- 视角统计信息 -->
        <div
          v-if="currentPerspective === 'process' && perspectiveStats.nodes > 0"
          class="stats-panel"
        >
          <div class="stats-row">
            <span class="stats-item">
              <span class="stats-value">{{ perspectiveStats.nodes }}</span>
              <span class="stats-label">本体</span>
            </span>
            <span class="stats-sep">·</span>
            <span class="stats-item">
              <span class="stats-value">{{ perspectiveStats.edges }}</span>
              <span class="stats-label">关系</span>
            </span>
            <span v-if="perspectiveStats.domains > 0" class="stats-sep">·</span>
            <span v-if="perspectiveStats.domains > 0" class="stats-item">
              <span class="stats-value">{{ perspectiveStats.domains }}</span>
              <span class="stats-label">业务域</span>
            </span>
          </div>
        </div>

        <button class="btn btn-ghost" @click="loadGraph">↻ 刷新画布</button>
	        <button class="btn btn-help" @click="openHelp">
	          <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
	          帮助文档
	        </button>
      </div>
    </aside>

    <!-- 主内容区：视角Tab栏 + 视角视图 + 画布 -->
    <div class="main-content-wrapper">
      <!-- 多视角切换 Tab -->
      <PerspectiveTabs :projectId="currentProjectId" @change="onPerspectiveChange" />

      <!-- 视角内容区（领导/工程师视角，替换画布区域），带 fade 过渡 -->
      <Transition name="perspective-fade" mode="out-in">
        <div class="perspective-content" v-if="currentPerspective !== 'process'" :key="currentPerspective">
          <LeaderView v-if="currentPerspective === 'leader'" :projectId="currentProjectId" />
          <EngineerView v-if="currentPerspective === 'engineer'" :projectId="currentProjectId" />
        </div>
      </Transition>

      <!-- 工艺人员视角：保留现有画布 -->
      <div v-show="currentPerspective === 'process'" class="canvas-wrapper">
    <main
      ref="canvasRef"
      class="canvas"
      :class="{ panning: isPanning }"
      :style="{ backgroundPosition: `${viewOffset.x}px ${viewOffset.y}px`, backgroundSize: `${24 * zoom}px ${24 * zoom}px` }"
      @pointerdown="startPanning"
      @wheel.prevent="onWheel"
      @click.self="selectedNodeId = null; selectedEdgeId = null; hideContextMenu()" 
      @contextmenu.prevent="showContextMenu($event, 'canvas')"
    >
      <div class="canvas-hint" v-if="nodes.length === 0">
        画布为空，右键点击空白处「新增独立本体」
      </div>

      <!-- 右键菜单 -->
      <div class="context-menu" v-if="contextMenu.visible" :style="{ top: contextMenu.y + 'px', left: contextMenu.x + 'px' }" @click.stop>
        <template v-if="contextMenu.type === 'node'">
          <div class="menu-item" @click="addChildOntology(contextMenu.nodeId)">
            <span class="menu-icon">➕</span> 新增子本体
          </div>
          <div class="menu-item" @click="startConnectionFromMenu(contextMenu.nodeId)">
            <span class="menu-icon">🔗</span> 从此节点连线
          </div>
          <div class="menu-item" @click="startReparentFromMenu(contextMenu.nodeId)">
            <span class="menu-icon">🌳</span> 将此节点转为子本体
          </div>
          <div class="menu-divider" v-if="hasChildren(contextMenu.nodeId)"></div>
          <div class="menu-item" v-if="hasChildren(contextMenu.nodeId)" @click="toggleCollapse(contextMenu.nodeId)">
            <span class="menu-icon">↕️</span> {{ collapsedNodeIds.has(contextMenu.nodeId) ? '展开子节点' : '折叠子节点' }}
          </div>
        </template>
        <template v-else>
          <div class="menu-item" @click="addRootOntologyMenu">
            <span class="menu-icon">➕</span> 在此新增独立本体
          </div>
        </template>
      </div>

      <!-- 自定义 Prompt 弹窗 -->
      <div class="prompt-overlay" v-if="promptState.visible" @click.self="cancelPrompt">
        <div class="prompt-dialog">
          <h3>{{ promptState.title }}</h3>
          <input
            ref="promptInputRef"
            type="text"
            v-model="promptState.value"
            :placeholder="promptState.placeholder"
            @keyup.enter="submitPrompt"
            @keyup.esc="cancelPrompt"
          />
          <div class="prompt-actions">
            <button class="btn btn-secondary" @click="cancelPrompt">取消</button>
            <button class="btn btn-primary" @click="submitPrompt">确定</button>
          </div>
        </div>
      </div>

      <!-- 自定义 Confirm 弹窗 -->
      <div class="prompt-overlay" v-if="confirmState.visible" @click.self="handleConfirm(false)">
        <div class="prompt-dialog">
          <h3>{{ confirmState.title }}</h3>
          <p class="confirm-message">{{ confirmState.message }}</p>
          <div class="prompt-actions">
            <button class="btn btn-secondary" @click="handleConfirm(false)">取消</button>
            <button class="btn btn-danger" @click="handleConfirm(true)">确定清空</button>
          </div>
        </div>
      </div>

      <!-- 关系规则管理 - 右侧全高面板 -->
      <div class="rules-overlay" v-if="rulesDialogVisible" @click.self="rulesDialogVisible = false" @wheel.stop>
        <div class="rules-panel" @click.stop>
          <!-- 头部 -->
          <div class="rs-header">
            <div class="rs-header-left">
              <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
              </svg>
              <h2>关系逻辑规则</h2>
            </div>
            <button class="rs-close" @click="rulesDialogVisible = false">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
          </div>

          <!-- Tab 切换 -->
          <div class="rs-tabs">
            <button
              class="rs-tab"
              :class="{ active: activeTab === 'mutex' }"
              @click="activeTab = 'mutex'"
            >
              <svg viewBox="0 0 8 8" width="8" height="8"><circle cx="4" cy="4" r="4" fill="currentColor"/></svg>
              互斥约束
              <span class="rs-badge" v-if="mutexRules.length">{{ mutexRules.length }}</span>
            </button>
            <button
              class="rs-tab"
              :class="{ active: activeTab === 'inference' }"
              @click="activeTab = 'inference'"
            >
              <svg viewBox="0 0 8 8" width="8" height="8"><circle cx="4" cy="4" r="4" fill="currentColor"/></svg>
              顺承推理
              <span class="rs-badge" v-if="inferenceRules.length">{{ inferenceRules.length }}</span>
            </button>
          </div>

          <!-- 内容区 -->
          <div class="rs-body">
            <!-- ====== 互斥约束 ====== -->
            <div v-if="activeTab === 'mutex'" class="rs-section">
              <p class="rs-desc">定义不可共存的有向关系对。A→B 上已存在的关系将阻止在同一方向添加冲突关系。</p>

              <div class="rs-form-card">
                <div class="rs-form-row">
                  <label class="rs-label">关系 A</label>
                  <input type="text" list="rel-list" class="rs-input" v-model="newMutex.rel1" placeholder="例如：管理" @keyup.enter="addMutexRule" />
                </div>
                <div class="rs-form-sep mutex-sep">互斥于</div>
                <div class="rs-form-row">
                  <label class="rs-label">关系 B</label>
                  <input type="text" list="rel-list" class="rs-input" v-model="newMutex.rel2" placeholder="例如：控制" @keyup.enter="addMutexRule" />
                </div>
                <button class="rs-btn-add mutex" @click="addMutexRule">
                  <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                  添加规则
                </button>
              </div>

              <div class="rs-list" v-if="mutexRules.length">
                <div class="rs-card" v-for="rule in mutexRules" :key="rule.id">
                  <div class="rs-card-body">
                    <span class="rs-tag mutex">{{ rule.rel1 }}</span>
                    <svg class="rs-card-sep" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                    <span class="rs-tag mutex">{{ rule.rel2 }}</span>
                  </div>
                  <button class="rs-card-del" @click="removeMutexRule(rule.id)" title="删除">
                    <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>
                  </button>
                </div>
              </div>
              <div class="rs-empty" v-else>
                <div class="rs-empty-icon">
                  <svg viewBox="0 0 24 24" width="36" height="36" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="9" y1="9" x2="15" y2="15"/><line x1="15" y1="9" x2="9" y2="15"/></svg>
                </div>
                <span class="rs-empty-text">暂无互斥约束规则</span>
                <span class="rs-empty-hint">在上方表单中添加第一条规则</span>
              </div>
            </div>

            <!-- ====== 顺承推理 ====== -->
            <div v-if="activeTab === 'inference'" class="rs-section">
              <p class="rs-desc">定义有向关系传递规则。当 A→B 存在关系 1，且 B→C 存在关系 2 时，自动推导出 A→C 的新关系。</p>

              <div class="rs-form-card">
                <div class="rs-form-row">
                  <label class="rs-label">关系 1</label>
                  <input type="text" list="rel-list" class="rs-input" v-model="newInference.rel1" placeholder="例如：控制" @keyup.enter="addInferenceRule" />
                </div>
                <div class="rs-form-sep inference-sep">
                  <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                </div>
                <div class="rs-form-row">
                  <label class="rs-label">关系 2</label>
                  <input type="text" list="rel-list" class="rs-input" v-model="newInference.rel2" placeholder="例如：依赖" @keyup.enter="addInferenceRule" />
                </div>
                <div class="rs-form-sep inference-arrow">
                  <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
                </div>
                <div class="rs-form-row">
                  <label class="rs-label">推导结果</label>
                  <input type="text" list="rel-list" class="rs-input rs-input-result" v-model="newInference.inferred_rel" placeholder="例如：支配" @keyup.enter="addInferenceRule" />
                </div>
                <button class="rs-btn-add inference" @click="addInferenceRule">
                  <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                  添加规则
                </button>
              </div>

              <div class="rs-list" v-if="inferenceRules.length">
                <div class="rs-card" v-for="rule in inferenceRules" :key="rule.id">
                  <div class="rs-card-body inference-body">
                    <span class="rs-tag inference">{{ rule.rel1 }}</span>
                    <svg class="rs-card-op" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                    <span class="rs-tag inference">{{ rule.rel2 }}</span>
                    <svg class="rs-card-arrow" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
                    <span class="rs-tag inference is-result">{{ rule.inferred_rel }}</span>
                  </div>
                  <button class="rs-card-del" @click="removeInferenceRule(rule.id)" title="删除">
                    <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>
                  </button>
                </div>
              </div>
              <div class="rs-empty" v-else>
                <div class="rs-empty-icon">
                  <svg viewBox="0 0 24 24" width="36" height="36" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><polyline points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
                </div>
                <span class="rs-empty-text">暂无顺承推理规则</span>
                <span class="rs-empty-hint">在上方表单中添加第一条规则</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 贝叶斯因果分析面板 -->
      <div class="rules-overlay" v-if="bayesianDialogVisible" @click.self="bayesianDialogVisible = false; clearHighlight()" @wheel.stop>
        <div class="rules-panel bayesian-panel" @click.stop>
          <!-- 头部 -->
          <div class="rs-header">
            <div class="rs-header-left">
              <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>
              </svg>
              <h2>贝叶斯因果分析</h2>
            </div>
            <button class="rs-close" @click="bayesianDialogVisible = false; clearHighlight()">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
          </div>

          <!-- 3个Tab -->
          <div class="rs-tabs">
            <button class="rs-tab" :class="{ active: bayesianTab === 'upstream' }" @click="bayesianTab = 'upstream'">向上追溯</button>
            <button class="rs-tab" :class="{ active: bayesianTab === 'downstream' }" @click="bayesianTab = 'downstream'">向下传播</button>
            <button class="rs-tab" :class="{ active: bayesianTab === 'overview' }" @click="bayesianTab = 'overview'">全局概览</button>
          </div>

          <div class="rs-body">
            <!-- Tab1: 向上追溯 -->
            <div v-if="bayesianTab === 'upstream'" class="by-section">
              <div class="by-select-row">
                <label>选择目标节点：</label>
                <select v-model="upstreamTargetId" class="by-select">
                  <option value="">-- 请选择 --</option>
                  <option v-for="n in nodes" :key="n.id" :value="n.id">{{ n.name }}</option>
                </select>
                <button class="by-run-btn" @click="runUpstreamAnalysis" :disabled="!upstreamTargetId || bayesianLoading">开始追溯</button>
              </div>
              <div v-if="bayesianLoading" class="by-loading">分析中...</div>
              <!-- 结果 -->
              <div v-if="upstreamResult" class="by-result">
                <h3 class="by-result-title">追溯目标：「{{ upstreamResult.target }}」的上游影响因素</h3>
                <div v-for="f in upstreamResult.factors" :key="f.factor_id" class="by-factor-card">
                  <div class="by-factor-top">
                    <span class="by-factor-name">{{ f.factor }}</span>
                    <span class="by-level-tag" :class="f.level">{{ f.level }}</span>
                    <span class="by-prob">{{ (f.combined_probability * 100).toFixed(0) }}%</span>
                  </div>
                  <div class="by-prob-bar">
                    <div class="by-prob-fill" :style="{ width: (f.combined_probability * 100) + '%' }"></div>
                  </div>
                  <div class="by-paths">
                    <div v-for="p in f.paths" :key="p.path" class="by-path-item">
                      <span class="by-path-str">{{ p.path }}</span>
                      <span class="by-path-prob">{{ (p.probability * 100).toFixed(1) }}%</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- Tab2: 向下传播 -->
            <div v-if="bayesianTab === 'downstream'" class="by-section">
              <div class="by-select-row">
                <label>选择因子节点：</label>
                <select v-model="downstreamSourceId" class="by-select">
                  <option value="">-- 请选择 --</option>
                  <option v-for="n in nodes" :key="n.id" :value="n.id">{{ n.name }}</option>
                </select>
                <button class="by-run-btn" @click="runDownstreamAnalysis" :disabled="!downstreamSourceId || bayesianLoading">开始传播</button>
              </div>
              <div v-if="bayesianLoading" class="by-loading">分析中...</div>
              <div v-if="downstreamResult" class="by-result">
                <h3 class="by-result-title">传播源头：「{{ downstreamResult.source }}」的下游影响</h3>
                <div v-for="e in downstreamResult.effects" :key="e.target_id" class="by-factor-card">
                  <div class="by-factor-top">
                    <span class="by-factor-name">{{ e.target }}</span>
                    <span class="by-level-tag" :class="e.level">{{ e.level }}</span>
                    <span class="by-prob">{{ (e.combined_probability * 100).toFixed(0) }}%</span>
                  </div>
                  <div class="by-prob-bar">
                    <div class="by-prob-fill" :style="{ width: (e.combined_probability * 100) + '%' }"></div>
                  </div>
                  <div class="by-paths">
                    <div v-for="p in e.paths" :key="p.path" class="by-path-item">
                      <span class="by-path-str">{{ p.path }}</span>
                      <span class="by-path-prob">{{ (p.probability * 100).toFixed(1) }}%</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- Tab3: 全局概览 -->
            <div v-if="bayesianTab === 'overview'" class="by-section ov-wrapper">
              <button class="by-run-btn by-run-full" @click="runOverviewAnalysis" :disabled="bayesianLoading">执行全局分析</button>
              <div v-if="bayesianLoading" class="by-loading">分析中...</div>
              <div v-if="overviewResult" class="by-result">
                <!-- 总结卡片 -->
                <div class="ov-summary">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;margin-top:2px;color:#1E40AF"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg>
                  <span>{{ overviewResult.summary }}</span>
                </div>

                <!-- 影响力排名 -->
                <div class="ov-section">
                  <h3 class="ov-section-title">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9H4.5a2.5 2.5 0 0 1 0-5C7 4 6 9 6 9z"/><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5C17 4 18 9 18 9z"/><path d="M4 22h16"/><path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22"/><path d="M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22"/><path d="M18 2H6v7a6 6 0 0 0 12 0V2Z"/></svg>
                    影响力排名
                  </h3>
                  <div class="ov-rank-list">
                    <div class="ov-rank-card" v-for="(item, idx) in overviewResult.influence_ranking.slice(0, 8)" :key="item.node_id">
                      <div class="ov-rank-num" :class="'rank-' + (idx + 1)">{{ idx + 1 }}</div>
                      <div class="ov-rank-body">
                        <div class="ov-rank-name">{{ item.node }}</div>
                        <div class="ov-rank-bar-wrap">
                          <div class="ov-rank-bar" :style="{ width: Math.max((item.score || 0) * 100, 2) + '%' }"></div>
                        </div>
                      </div>
                      <div class="ov-rank-stat">
                        <span class="ov-rank-count">{{ item.reachable_nodes }}</span>
                        <span class="ov-rank-unit">节点</span>
                      </div>
                    </div>
                  </div>
                </div>

                <!-- 最脆弱节点 -->
                <div class="ov-section">
                  <h3 class="ov-section-title">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
                    最脆弱节点
                  </h3>
                  <p class="ov-section-desc">被最多上游链路依赖的节点，一旦出问题波及范围最广</p>
                  <div class="ov-vuln-grid">
                    <div class="ov-vuln-card" v-for="item in overviewResult.vulnerability_ranking.slice(0, 6)" :key="item.node_id">
                      <span class="ov-vuln-num" :style="{ color: item.incoming_links >= 6 ? '#EF4444' : item.incoming_links >= 3 ? '#F59E0B' : '#94A3B8' }">{{ item.incoming_links }}<span class="ov-vuln-num-unit">条链路</span></span>
                      <span class="ov-vuln-label">{{ item.node }}</span>
                    </div>
                  </div>
                </div>

                <!-- 最强因果链 -->
                <div class="ov-section">
                  <h3 class="ov-section-title">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>
                    最强因果链
                  </h3>
                  <div class="ov-chain-list">
                    <div class="ov-chain-card" v-for="(p, idx) in overviewResult.strongest_paths.slice(0, 5)" :key="idx">
                      <span class="ov-chain-badge" :style="{ background: p.probability >= 0.8 ? '#10B981' : p.probability >= 0.6 ? '#3B82F6' : p.probability >= 0.4 ? '#F59E0B' : '#94A3B8' }">{{ (p.probability * 100).toFixed(0) }}%</span>
                      <span class="ov-chain-path">{{ p.path }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 关系权重配置弹窗 -->
      <div class="prompt-overlay" v-if="weightDialogVisible" @click.self="weightDialogVisible = false" @wheel.stop>
        <div class="prompt-dialog weight-dialog" @click.stop>
          <div class="rd-header">
            <div class="rd-header-left">
              <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/><line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/><line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/><line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" x2="15" y2="8"/><line x1="17" y1="16" x2="23" y2="16"/>
              </svg>
              <h3>关系权重配置</h3>
            </div>
            <button class="rd-close" @click="weightDialogVisible = false">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
          </div>
          <div class="rd-body">
            <p class="rd-desc">设定不同关系类型在贝叶斯因果分析中的默认权重。权重越高，该关系的影响力越大。也可选中单条边在详情面板中单独覆盖权重。</p>
            <div class="by-weights-card">
              <div v-for="(weight, relName) in weightConfig" :key="relName" class="by-weight-row">
                <span class="by-weight-name">{{ relName }}</span>
                <input type="range" min="0" max="1" step="0.05" v-model.number="weightConfig[relName]" class="by-slider" />
                <span class="by-weight-val">{{ (weightConfig[relName] * 100).toFixed(0) }}%</span>
                <button class="by-weight-del" @click="removeWeightMapping(relName)">
                  <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/></svg>
                </button>
              </div>
              <div v-if="Object.keys(weightConfig).length === 0" class="rd-empty">
                <span>暂未配置权重映射，所有关系使用系统默认值（50%）</span>
              </div>
              <div class="by-weight-add">
                <input v-model="newWeightRelation" placeholder="关系名" class="by-input-sm" @keyup.enter="addWeightMapping" />
                <input type="range" min="0" max="1" step="0.05" v-model.number="newWeightValue" class="by-slider-sm" />
                <span class="by-weight-val-add">{{ (newWeightValue * 100).toFixed(0) }}%</span>
                <button class="by-weight-add-btn" @click="addWeightMapping">添加</button>
              </div>
            </div>
            <button class="by-run-btn" @click="saveWeightConfig(); weightDialogVisible = false" style="margin-top: 16px; width: 100%;">保存并关闭</button>
          </div>
        </div>
      </div>

      <!-- OCR 结果弹窗 -->
      <div class="prompt-overlay" v-if="ocrDialogVisible" @click.self="ocrDialogVisible = false" @wheel.stop>
        <div class="prompt-dialog ocr-dialog" @click.stop>
          <div class="ocr-dialog-header">
            <h3>OCR 识别结果</h3>
            <button class="btn btn-ghost ocr-close-btn" @click="ocrDialogVisible = false">关闭</button>
          </div>
          
          <!-- 并排布局容器 -->
          <div class="ocr-split-layout">
            <!-- 左侧：原始文本预览 -->
            <div class="ocr-preview-panel">
              <div class="ocr-meta">用户上传文件预览</div>
              <div class="ocr-preview-content">
                <img v-if="ocrPreviewType === 'image'" :src="ocrPreviewUrl" alt="预览图" class="ocr-preview-img" />
                <pre v-else-if="ocrPreviewType === 'text'">{{ ocrPreviewText }}</pre>
                <div v-else class="ocr-preview-empty">暂无预览</div>
              </div>
            </div>

            <!-- 右侧：识别实体选择 -->
            <div class="ocr-panel" v-if="ocrResult">
              <div class="ocr-meta">提取实体 (模式：{{ ocrResult.mode }}，共 {{ ocrCandidates.length }} 项)</div>
              <div class="ocr-actions">
                <button class="btn btn-ghost" @click="toggleAllOcrCandidates(true)">全选</button>
                <button class="btn btn-ghost" @click="toggleAllOcrCandidates(false)">全不选</button>
              </div>
              <div class="ocr-list">
                <label class="ocr-item" v-for="(item, idx) in ocrCandidates" :key="`${item.text}-${idx}`">
                  <input type="checkbox" v-model="item.selected" />
                    <span :title="item.text">{{ item.text }}</span>
                </label>
              </div>
              <button class="btn btn-primary" :disabled="selectedOcrEntities.length === 0" @click="importOcrToCanvas">
                一键导入勾选项
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- 画布内容容器，支持平移和缩放 -->
      <div 
        class="canvas-content" 
        :style="{ transform: `translate(${viewOffset.x}px, ${viewOffset.y}px) scale(${zoom})`, transformOrigin: '0 0' }"
        @click.self="selectedNodeId = null; selectedEdgeId = null; hideContextMenu()"
      >

        <svg class="edges-layer" :class="{ 'is-dragging': draggingNodeId }">
          <defs>
            <marker id="arrow" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto">
              <path d="M0,0 L0,8 L10,4 z" fill="#6366f1" />
            </marker>
            <marker id="arrow-selected" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto">
              <path d="M0,0 L0,8 L10,4 z" fill="#3b82f6" />
            </marker>
            <marker id="arrow-parent" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto">
              <path d="M0,0 L0,8 L10,4 z" fill="#10b981" />
            </marker>
            <marker id="arrow-symmetric" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto">
              <path d="M0,0 L0,8 L10,4 z" fill="#8b5cf6" />
            </marker>
            <marker id="arrow-reverse-symmetric" markerWidth="10" markerHeight="8" refX="1" refY="4" orient="auto">
              <path d="M10,0 L10,8 L0,4 z" fill="#8b5cf6" />
            </marker>
          </defs>
          <g 
            v-for="edge in edgeViews" 
            :key="edge.id" 
            class="edge-group"
            :class="{ selected: selectedEdgeId === edge.id, highlighted: highlightEnabled && highlightedEdgeIds.has(edge.id), dimmed: highlightEnabled && !highlightedEdgeIds.has(edge.id) }"
            @click.stop="selectedEdgeId = edge.id; selectedNodeId = null; hideContextMenu()"
          >
            <!-- 增加一个宽的透明路径方便点击 -->
            <path
              :d="edge.path"
              class="edge-click-area"
              fill="none"
              stroke="transparent"
              stroke-width="20"
            />
            <path
              :d="edge.path"
              :class="['edge-line', edge.kind, { 
                symmetric: edge.characteristics?.includes('symmetric'),
                transitive: edge.characteristics?.includes('transitive')
              }]"
              :marker-end="edge.characteristics?.includes('symmetric') ? 'url(#arrow-symmetric)' : `url(#arrow${edge.kind === 'parent-child' ? '-parent' : (selectedEdgeId === edge.id ? '-selected' : '')})`"
              :marker-start="edge.characteristics?.includes('symmetric') ? 'url(#arrow-reverse-symmetric)' : ''"
              fill="none"
            />
            <rect
              :x="edge.labelX - 42"
              :y="edge.labelY - 13"
              width="84"
              height="26"
              rx="13"
              class="edge-label-bg"
            />
            <text
              :x="edge.labelX"
              :y="edge.labelY + 4.5"
              class="edge-label"
            >
              {{ edge.displayRelation }}
            </text>
          </g>
        </svg>

        <div
          v-for="node in visibleNodes"
          :key="node.id"
          :class="['node-card', { selected: selectedNodeId === node.id, connecting: connectMode && connectSourceId === node.id, dragging: draggingNodeId === node.id, highlighted: highlightEnabled && highlightedNodeIds.has(node.id), dimmed: highlightEnabled && !highlightedNodeIds.has(node.id) }]"
          :style="{ '--node-x': node.x + 'px', '--node-y': node.y + 'px' }"
          @click.stop="onClickNode(node.id); hideContextMenu()"
          @pointerdown.stop="startDrag($event, node); hideContextMenu()"
          @contextmenu.prevent.stop="showContextMenu($event, 'node', node.id)"
        >
          <div class="node-topbar" :class="{ 'has-children': hasChildren(node.id) }"></div>
          <div class="node-header">
            <div class="node-icon">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <path d="M12 2L2 7l10 5 10-5-10-5z"/>
                <path d="M2 17l10 5 10-5"/>
                <path d="M2 12l10 5 10-5"/>
              </svg>
            </div>
            <span class="node-title" :title="node.name" v-html="formatSymbol(node.name)"></span>
          </div>
          <div class="node-body">
            <div class="node-id">ID: {{ node.id.slice(0, 6) }}</div>
          </div>

          <!-- 展开/折叠按钮 -->
          <div 
            v-if="hasChildren(node.id)" 
            class="collapse-btn" 
            @click.stop="toggleCollapse(node.id)"
          >
            {{ collapsedNodeIds.has(node.id) ? '+' : '-' }}
          </div>
        </div>
      </div>

      <!-- 缩放控件 -->
      <div class="zoom-controls" @click.stop>
        <button class="zoom-btn" @click="zoomIn" title="放大 (或使用滚轮)">＋</button>
        <button class="zoom-btn" @click="zoomReset" title="重置缩放">⌂</button>
        <button class="zoom-btn" @click="zoomOut" title="缩小 (或使用滚轮)">－</button>
      </div>
    </main>
      </div> <!-- end canvas-wrapper -->

      <!-- ProcessView 用于加载数据（不可见，仅触发事件） -->
      <ProcessView
        v-if="currentPerspective === 'process'"
        :projectId="currentProjectId"
        @graph-loaded="onGraphLoaded"
        @stats="onStats"
        ref="processViewRef"
      />
    </div> <!-- end main-content-wrapper -->

    <!-- 右侧详情面板 (Protégé 风格) -->
    <aside class="detail-panel" v-if="selectedNode || selectedEdge" @click.stop>
      <div class="panel-header">
        <h3>{{ selectedNode ? '本体详情' : '关系详情' }}</h3>
        <button class="close-btn" @click="selectedNodeId = null; selectedEdgeId = null">×</button>
      </div>

      <div class="panel-content">
        <!-- 节点编辑 -->
        <template v-if="selectedNode">
          <div class="detail-group">
            <label>名称</label>
            <input type="text" v-model="selectedNode.name" @change="syncGraph" class="input-field" />
          </div>

          <div class="detail-group">
            <div class="group-header">
              <label>属性 (Data Properties)</label>
              <button class="add-btn" @click="addAttribute">＋</button>
            </div>
            <div class="attr-list">
              <div v-for="(attr, idx) in selectedNode.attributes" :key="idx" class="attr-item">
                <input type="text" v-model="attr.key" @change="updateAttribute" placeholder="键" />
                <input type="text" v-model="attr.value" @change="updateAttribute" placeholder="值" />
                <button class="remove-btn" @click="removeAttribute(idx)">×</button>
              </div>
              <div v-if="!selectedNode.attributes?.length" class="empty-tip">暂无属性</div>
            </div>
          </div>
        </template>

        <!-- 边编辑 -->
        <template v-else-if="selectedEdge">
          <div class="detail-group">
            <label>关系名称</label>
            <input type="text" list="rel-list" v-model="selectedEdge.relation" @change="syncGraph" class="input-field" />
          </div>

          <div class="detail-group">
            <label>因果权重</label>
            <div class="weight-edit-row">
              <input type="range" min="0" max="1" step="0.05"
                :value="selectedEdge.weight != null ? selectedEdge.weight : 0.5"
                @input="selectedEdge.weight = parseFloat($event.target.value); syncGraph()"
                class="weight-slider" />
              <span class="weight-val">{{ ((selectedEdge.weight != null ? selectedEdge.weight : 0.5) * 100).toFixed(0) }}%</span>
            </div>
            <div class="weight-hint">
              当前使用{{ selectedEdge.weight != null ? '显式权重' : '系统默认值(0.5)，拖动滑块设置显式权重' }}
            </div>
            <button v-if="selectedEdge.weight != null" class="btn btn-ghost btn-xs"
              @click="selectedEdge.weight = null; syncGraph()">重置为默认</button>
          </div>

          <div class="detail-group" v-if="selectedEdge.kind === 'relation'">
            <label>特征 (Characteristics)</label>
            <div class="chara-options">
              <label class="chara-item">
                <input type="checkbox" :checked="selectedEdge.characteristics?.includes('symmetric')" @change="toggleCharacteristic('symmetric')" />
                Symmetric (对称)
              </label>
              <label class="chara-item">
                <input type="checkbox" :checked="selectedEdge.characteristics?.includes('transitive')" @change="toggleCharacteristic('transitive')" />
                Transitive (传递)
              </label>
              <label class="chara-item">
                <input type="checkbox" :checked="selectedEdge.characteristics?.includes('functional')" @change="toggleCharacteristic('functional')" />
                Functional (函数)
              </label>
            </div>
          </div>
        </template>
      </div>

      <div class="panel-footer">
        <button class="btn btn-danger" @click="selectedNode ? deleteSelectedNode() : deleteSelectedEdge()">
          <span class="icon">🗑️</span> 删除此{{ selectedNode ? '本体' : '关系' }}
        </button>
      </div>
    </aside>
  </div>
</template>

<style scoped>
/* ======================== CSS 变量 ======================== */
.app-container {
  --color-primary: #2563eb;
  --color-primary-light: #3b82f6;
  --color-primary-dark: #1d4ed8;
  --color-primary-bg: #eff6ff;
  --color-success: #10b981;
  --color-success-bg: #d1fae5;
  --color-relation: #6366f1;
  --color-symmetric: #8b5cf6;
  --color-warning: #d97706;
  --color-danger: #dc2626;
  --color-text: #0f172a;
  --color-text-secondary: #475569;
  --color-text-muted: #64748b;
  --color-border: #e2e8f0;
  --color-border-light: #f1f5f9;
  --color-bg: #f8fafc;
  --color-bg-canvas: #fafbfc;
  --color-surface: #ffffff;

  --shadow-xs: 0 1px 2px rgba(0,0,0,0.04);
  --shadow-sm: 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
  --shadow-md: 0 4px 6px -1px rgba(0,0,0,0.06), 0 2px 4px -2px rgba(0,0,0,0.04);
  --shadow-lg: 0 10px 15px -3px rgba(0,0,0,0.08), 0 4px 6px -4px rgba(0,0,0,0.06);
  --shadow-xl: 0 20px 40px -8px rgba(0,0,0,0.12), 0 10px 15px -3px rgba(0,0,0,0.08);
  --shadow-glow: 0 0 0 3px rgba(37,99,235,0.2), 0 0 20px rgba(37,99,235,0.06);

  --radius-sm: 6px;
  --radius-md: 8px;
  --radius-lg: 12px;
  --radius-xl: 16px;

  --ease-out: cubic-bezier(0.4, 0, 0.2, 1);
  --ease-in-out: cubic-bezier(0.4, 0, 0.2, 1);
  --ease-spring: cubic-bezier(0.16, 1, 0.3, 1);

  --transition-fast: 0.15s var(--ease-out);
  --transition-normal: 0.25s var(--ease-out);
  --transition-slow: 0.35s var(--ease-out);
}

.app-container {
  display: flex;
  height: 100vh;
  width: 100vw;
  background-color: #f8fafc;
  overflow: hidden;
  font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  color: #0f172a;
}

/* ======================== 主内容区（视角 Tab + 画布 + 详情） ======================== */
.main-content-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  position: relative;
  overflow: hidden;
}

.perspective-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* 视角内容区 fade 过渡 */
.perspective-fade-enter-active,
.perspective-fade-leave-active {
  transition: opacity 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.perspective-fade-enter-from,
.perspective-fade-leave-to {
  opacity: 0;
}

.canvas-wrapper {
  flex: 1;
  display: flex;
  overflow: hidden;
}

/* ======================== 项目管理栏 (Project Bar) ======================== */
.project-bar {
  width: 260px;
  background: #ffffff;
  border-right: 1px solid #E8ECF1;
  display: flex;
  flex-direction: column;
  box-shadow: 2px 0 16px rgba(15, 23, 42, 0.03);
  z-index: 11;
  transition: width 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
  flex-shrink: 0;
}

.project-bar.collapsed {
  width: 48px;
}

/* ---- 头部 ---- */
.pb-header {
  padding: 20px 18px 14px 18px;
  flex-shrink: 0;
}

.pb-new-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  padding: 11px 16px;
  border: 1px solid #DBEAFE;
  border-radius: 8px;
  background: #EFF6FF;
  color: #1E40AF;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  letter-spacing: 0.01em;
  white-space: nowrap;
}

.pb-new-btn:hover {
  background: #DBEAFE;
  border-color: #BFDBFE;
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(30, 64, 175, 0.1);
}

.pb-new-btn:active {
  transform: translateY(0);
}

/* ---- 项目列表 ---- */
.pb-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 10px;
}

.pb-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 16px;
  color: #94A3B8;
  text-align: center;
  gap: 8px;
  user-select: none;
}

.pb-empty p {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  color: #64748B;
}

.pb-empty span {
  font-size: 11.5px;
  color: #94A3B8;
}

.pb-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  position: relative;
  transition: all 0.18s ease;
  margin-bottom: 2px;
}

.pb-item:hover {
  background: #F1F5F9;
}

.pb-item.active {
  background: #EFF6FF;
}

.pb-item.active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 8px;
  bottom: 8px;
  width: 3px;
  border-radius: 0 3px 3px 0;
  background: #1E40AF;
}

.pb-item-icon {
  flex-shrink: 0;
  color: #94A3B8;
  transition: color 0.18s ease;
}

.pb-item.active .pb-item-icon {
  color: #1E40AF;
}

.pb-item-content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.pb-item-name {
  font-size: 13.5px;
  font-weight: 600;
  color: #0F172A;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 1.3;
}

.pb-item.active .pb-item-name {
  color: #1E40AF;
}

.pb-item-meta {
  font-size: 11px;
  color: #94A3B8;
  font-weight: 500;
  white-space: nowrap;
}

.pb-item.active .pb-item-meta {
  color: #64748B;
}

/* ---- 重命名输入框 ---- */
.pb-rename-input {
  width: 100%;
  padding: 4px 8px;
  border: 1.5px solid #BFDBFE;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
  color: #0F172A;
  background: #FFFFFF;
  outline: none;
  box-sizing: border-box;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.pb-rename-input:focus {
  border-color: #1E40AF;
  box-shadow: 0 0 0 3px rgba(30, 64, 175, 0.1);
}

/* ---- 操作按钮 ---- */
.pb-item-actions {
  display: flex;
  align-items: center;
  gap: 2px;
  opacity: 0;
  transition: opacity 0.15s ease;
  flex-shrink: 0;
}

.pb-item:hover .pb-item-actions,
.pb-item.active .pb-item-actions {
  opacity: 1;
}

.pb-action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border: 1px solid transparent;
  border-radius: 6px;
  background: none;
  color: #94A3B8;
  cursor: pointer;
  transition: all 0.15s ease;
}

.pb-action-btn:hover {
  background: #F1F5F9;
  color: #475569;
  border-color: #E2E8F0;
}

.pb-action-btn:last-child:hover {
  background: #FEF2F2;
  color: #DC2626;
  border-color: #FECACA;
}

/* ---- 底部折叠按钮 ---- */
.pb-footer {
  padding: 12px 18px;
  border-top: 1px solid #F1F5F9;
  flex-shrink: 0;
}

.pb-toggle-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  padding: 8px;
  border: 1px solid transparent;
  border-radius: 6px;
  background: none;
  color: #94A3B8;
  cursor: pointer;
  transition: all 0.18s ease;
}

.pb-toggle-btn:hover {
  background: #F1F5F9;
  color: #475569;
  border-color: #E2E8F0;
}

/* ---- 折叠状态 ---- */
.pb-collapsed-inner {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 12px;
  padding: 8px 0;
}

.pb-collapsed-icon {
  flex-shrink: 0;
  color: #94A3B8;
  transition: color 0.18s ease;
}

.pb-expand-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: none;
  color: #94A3B8;
  cursor: pointer;
  transition: all 0.18s ease;
  flex-shrink: 0;
}

.pb-expand-btn:hover {
  background: #F1F5F9;
  color: #475569;
  border-color: #E2E8F0;
}

/* ---- 滚动条美化 ---- */
.pb-list {
  scrollbar-width: thin;
  scrollbar-color: #E2E8F0 transparent;
}

.pb-list::-webkit-scrollbar {
  width: 4px;
}

.pb-list::-webkit-scrollbar-track {
  background: transparent;
}

.pb-list::-webkit-scrollbar-thumb {
  background: #E2E8F0;
  border-radius: 2px;
}

.pb-list::-webkit-scrollbar-thumb:hover {
  background: #CBD5E1;
}

/* Sidebar */
.sidebar {
  width: 300px;
  background: #ffffff;
  border-right: 1px solid #e2e8f0;
  display: flex;
  flex-direction: column;
  box-shadow: 4px 0 24px rgba(15, 23, 42, 0.04);
  z-index: 10;
}

.sidebar-header {
  padding: 16px 20px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  border-bottom: 1px solid #f1f5f9;
}

.logo {
  width: 32px;
  height: 32px;
  background: #eff6ff;
  color: #2563eb;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.logo svg {
  width: 20px;
  height: 20px;
}

.sidebar-header h2 {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: #0f172a;
  flex-shrink: 0;
}

/* ---------- 项目选择器 ---------- */
.project-selector {
  position: relative;
  width: 100%;
  margin-top: 2px;
}

.ps-trigger {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 12px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
  color: #334155;
  transition: all 0.2s ease;
}

.ps-trigger:hover {
  background: #f1f5f9;
  border-color: #cbd5e1;
}

.ps-trigger svg:first-child { color: #94a3b8; flex-shrink: 0; }
.ps-trigger svg:last-child { color: #94a3b8; flex-shrink: 0; margin-left: auto; }

.ps-current-name {
  flex: 1;
  text-align: left;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 600;
  color: #0f172a;
}

.ps-dropdown {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  margin-top: 4px;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  box-shadow: 0 12px 32px rgba(15,23,42,0.12);
  z-index: 200;
  overflow: hidden;
}

.ps-list { max-height: 240px; overflow-y: auto; }

.ps-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  cursor: pointer;
  transition: background 0.12s ease;
  font-size: 13px;
  color: #334155;
}

.ps-item:hover { background: #f8fafc; }
.ps-item.active { background: #eff6ff; }

.ps-item-name { flex: 1; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.ps-item-actions { display: flex; gap: 4px; opacity: 0; transition: opacity 0.12s ease; }
.ps-item:hover .ps-item-actions { opacity: 1; }
.ps-item.active .ps-item-actions { opacity: 1; }

.ps-item-actions button {
  width: 26px; height: 26px;
  display: flex; align-items: center; justify-content: center;
  background: none; border: 1px solid transparent; border-radius: 5px;
  color: #94a3b8; cursor: pointer; transition: all 0.15s ease;
}
.ps-item-actions button:hover { background: #f1f5f9; border-color: #e2e8f0; color: #475569; }

.ps-rename-input {
  flex: 1;
  height: 28px;
  padding: 0 8px;
  border: 1.5px solid #bfdbfe;
  border-radius: 5px;
  font-size: 13px;
  outline: none;
  background: #ffffff;
}

.ps-footer {
  padding: 8px;
  border-top: 1px solid #f1f5f9;
}

.ps-new-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  width: 100%;
  padding: 8px;
  background: #eff6ff;
  color: #1e40af;
  border: 1px dashed #bfdbfe;
  border-radius: 7px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
}

.ps-new-btn:hover { background: #dbeafe; border-color: #93c5fd; }

.sidebar-content {
  flex: 1;
  padding: 24px;
  overflow-y: auto;
}

.action-group {
  margin-bottom: 32px;
}

.group-title {
  font-size: 13px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #475569;
  margin: 0 0 16px 4px;
  font-weight: 700;
}

/* Buttons */
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  gap: 8px;
  padding: 10px 16px;
  margin-bottom: 12px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  border: 1px solid transparent;
  outline: none;
}

.btn:focus-visible {
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.5);
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-primary {
  background: #2563eb;
  color: #ffffff;
  box-shadow: 0 4px 6px -1px rgba(37, 99, 235, 0.2);
}

.btn-primary:hover:not(:disabled) {
  background: #1d4ed8;
  box-shadow: 0 6px 8px -1px rgba(37, 99, 235, 0.3);
  transform: translateY(-1px);
}

.btn-secondary {
  background: #f1f5f9;
  color: #1e293b;
  border-color: #cbd5e1;
}

.btn-secondary:hover:not(:disabled) {
  background: #e2e8f0;
  color: #0f172a;
}

.btn-danger {
  background: #fef2f2;
  color: #dc2626;
  border-color: #fecaca;
}

.btn-danger:hover:not(:disabled) {
  background: #fee2e2;
  color: #b91c1c;
  border-color: #fca5a5;
}

.tip-text {
  font-size: 13px;
  color: #d97706;
  margin: 4px 0 0 0;
  text-align: center;
  font-weight: 500;
}

.file-input {
  display: block;
  width: 100%;
  margin-bottom: 12px;
  font-size: 13px;
  color: #334155;
  padding: 8px;
  border: 1px dashed #cbd5e1;
  border-radius: 8px;
  background: #fafafa;
}

.file-input:focus-visible {
  outline: none;
  border-color: #2563eb;
}

/* LLM 暂停使用提示 */
.llm-paused-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: var(--radius-md);
  font-size: 12px;
  font-weight: 600;
  color: #92400e;
  margin-bottom: 12px;
  line-height: 1.5;
}

.pause-icon {
  font-size: 13px;
  flex-shrink: 0;
}

.ocr-dialog {
  width: 90vw !important;
  max-width: 1400px !important;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
}

.ocr-dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
  padding: 0 4px;
}

.ocr-dialog-header h3 {
  margin: 0;
  font-size: 22px;
  font-weight: 800;
  color: #0f172a;
}

.ocr-close-btn {
  width: auto;
  margin: 0;
  padding: 8px 16px;
  font-size: 14px;
}

.ocr-split-layout {
  display: flex;
  gap: 24px;
  flex: 1;
  overflow: hidden;
  padding-top: 8px;
}

.ocr-preview-panel {
  flex: 1.1;
  min-width: 0;
  border: 1px solid #cbd5e1;
  border-radius: 12px;
  background: #f8fafc;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.ocr-preview-panel .ocr-meta {
  padding: 16px 16px 0;
}

.ocr-preview-content {
  flex: 1;
  overflow: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  background: #ffffff;
  margin: 12px;
  border-radius: 8px;
  border: 1px solid #f1f5f9;
}

.ocr-preview-img {
  max-width: 100%;
  height: auto;
  border-radius: 6px;
  object-fit: contain;
  margin: auto;
}

.ocr-preview-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #94a3b8;
  font-size: 14px;
}

.ocr-preview-content pre {
  margin: 0;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 13px;
  color: #334155;
  white-space: pre-wrap;
  word-wrap: break-word;
  line-height: 1.6;
}

.ocr-panel {
  flex: 1.3;
  border: 1px solid #cbd5e1;
  border-radius: 12px;
  padding: 20px;
  background: #f8fafc;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.ocr-meta {
  font-size: 15px;
  font-weight: 600;
  color: #334155;
  margin-bottom: 16px;
}

.ocr-actions {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.ocr-actions .btn {
  margin-bottom: 0;
  padding: 8px 16px;
  font-size: 13px;
  width: auto;
}

.ocr-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
  flex: 1;
  max-height: none;
  min-height: 300px;
  overflow-y: auto;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  background: #ffffff;
  padding: 16px;
  margin-bottom: 16px;
}

.ocr-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px;
  border-radius: 8px;
  background: #f8fafc;
  border: 1px solid transparent;
  transition: all 0.2s ease;
  cursor: pointer;
}

.ocr-item:hover {
  background: #f1f5f9;
  border-color: #cbd5e1;
}

/* Fallback for browsers that don't support :has */
.ocr-item.selected {
  background: #eff6ff;
  border-color: #bfdbfe;
}
.ocr-item:has(input:checked) {
  background: #eff6ff;
  border-color: #bfdbfe;
}

.ocr-item input[type="checkbox"] {
  margin-top: 2px;
  width: 18px;
  height: 18px;
  accent-color: #2563eb;
  cursor: pointer;
  flex-shrink: 0;
}

.ocr-item span {
  font-size: 14px;
  color: #1e293b;
  line-height: 1.5;
  word-break: break-word;
  font-weight: 500;
}

.btn-outline {
  background: transparent;
  color: #2563eb;
  border-color: #bfdbfe;
}

.btn-outline:hover:not(:disabled) {
  background: #eff6ff;
}

.btn-outline.active {
  background: #fef2f2;
  color: #dc2626;
  border-color: #fecaca;
}

.btn-ghost {
  background: transparent;
  color: #475569;
  border: 1px solid transparent;
}

.btn-ghost:hover {
  color: #0f172a;
  background: #f1f5f9;
  border-color: #e2e8f0;
}

.btn-xs {
  width: auto;
  padding: 6px 12px;
  font-size: 11px;
  margin-top: 6px;
}

.weight-edit-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 4px;
}

.weight-slider {
  flex: 1;
  height: 6px;
  accent-color: #1E40AF;
  cursor: pointer;
}

.weight-val {
  font-size: 14px;
  font-weight: 700;
  color: #1E40AF;
  min-width: 40px;
  text-align: right;
  font-family: ui-monospace, monospace;
}

.weight-hint {
  font-size: 11px;
  color: #94A3B8;
  margin-top: 4px;
  line-height: 1.4;
}

.btn-help {
  background: #eff6ff;
  color: #1e40af;
  border-color: #bfdbfe;
}
.btn-help:hover {
  background: #dbeafe;
  border-color: #93c5fd;
  color: #1e3a8a;
}

/* Sidebar Footer */
.sidebar-footer {
  padding: 24px;
  border-top: 1px solid #f1f5f9;
  background: #f8fafc;
}

/* ---- 视角统计面板 ---- */
.stats-panel {
  margin-bottom: 14px;
  padding: 12px 14px;
  background: #f1f5f9;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
}

.stats-row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  flex-wrap: wrap;
}

.stats-item {
  display: inline-flex;
  align-items: baseline;
  gap: 3px;
}

.stats-value {
  font-size: 14px;
  font-weight: 700;
  color: #1e3a5f;
  font-variant-numeric: tabular-nums;
}

.stats-label {
  font-size: 11px;
  font-weight: 500;
  color: #64748b;
}

.stats-sep {
  font-size: 13px;
  font-weight: 400;
  color: #94a3b8;
  margin: 0 1px;
}

/* ======================== 关系规则面板 - 右侧滑出 ======================== */
.rules-overlay {
  position: absolute;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  backdrop-filter: blur(3px);
  z-index: 110;
  display: flex;
  justify-content: flex-end;
  animation: rules-overlay-in 0.15s ease-out;
}

@keyframes rules-overlay-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

.rules-panel {
  width: 520px;
  max-width: 95vw;
  height: 100%;
  background: #F8FAFC;
  display: flex;
  flex-direction: column;
  box-shadow: -8px 0 32px rgba(15, 23, 42, 0.12);
  animation: rules-panel-in 0.2s cubic-bezier(0.22, 0.61, 0.36, 1);
  overflow: hidden;
}

@keyframes rules-panel-in {
  from { transform: translateX(100%); }
  to { transform: translateX(0); }
}

/* ---------- 头部 ---------- */
.rs-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 22px 26px 18px 26px;
  flex-shrink: 0;
  background: #FFFFFF;
  border-bottom: 1px solid #E8ECF1;
}

.rs-header-left {
  display: flex;
  align-items: center;
  gap: 12px;
  color: #1E40AF;
}

.rs-header-left h2 {
  margin: 0;
  font-size: 17px;
  font-weight: 700;
  color: #0F172A;
  letter-spacing: -0.01em;
}

.rs-close {
  width: 34px; height: 34px;
  display: flex; align-items: center; justify-content: center;
  background: none; border: 1px solid transparent; border-radius: 8px;
  color: #94A3B8; cursor: pointer;
  transition: all 0.2s ease;
  flex-shrink: 0;
}

.rs-close:hover {
  background: #F1F5F9;
  border-color: #E2E8F0;
  color: #475569;
}

/* ---------- Tab 切换 ---------- */
.rs-tabs {
  display: flex;
  gap: 0;
  padding: 0 26px;
  flex-shrink: 0;
  background: #FFFFFF;
  border-bottom: 1px solid #E8ECF1;
}

.rs-tab {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 13px 22px 13px 22px;
  font-size: 13.5px;
  font-weight: 600;
  color: #64748B;
  background: none;
  border: none;
  border-bottom: 2.5px solid transparent;
  cursor: pointer;
  transition: all 0.2s ease;
  margin-bottom: -1px;
  letter-spacing: 0.01em;
  white-space: nowrap;
}

.rs-tab svg { flex-shrink: 0; }

.rs-tab:nth-child(1) svg { color: #F59E0B; }
.rs-tab:nth-child(2) svg { color: #6366F1; }

.rs-tab:hover {
  color: #334155;
  background: rgba(241, 245, 249, 0.5);
}

.rs-tab.active {
  color: #0F172A;
  font-weight: 700;
  border-bottom-color: #1E40AF;
}

.rs-badge {
  font-size: 11px;
  font-weight: 700;
  color: #64748B;
  background: #F1F5F9;
  padding: 2px 8px;
  border-radius: 10px;
  min-width: 20px;
  text-align: center;
  letter-spacing: 0.02em;
  line-height: 1.4;
}

.rs-tab.active .rs-badge {
  background: #E0E7FF;
  color: #3730A3;
}

/* ---------- 内容区 ---------- */
.rs-body {
  flex: 1;
  overflow-y: auto;
  padding: 24px 26px 32px 26px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.rs-section {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.rs-desc {
  margin: 0;
  font-size: 13px;
  color: #64748B;
  line-height: 1.7;
  padding: 13px 16px;
  background: #F1F5F9;
  border-radius: 8px;
  border-left: 3px solid #CBD5E1;
}

/* ---------- 表单卡片 ---------- */
.rs-form-card {
  background: #FFFFFF;
  border: 1px solid #E8ECF1;
  border-radius: 12px;
  padding: 22px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.rs-form-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.rs-label {
  font-size: 11.5px;
  font-weight: 700;
  color: #64748B;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  padding-left: 2px;
}

.rs-input {
  width: 100%;
  height: 42px;
  padding: 0 14px;
  margin: 0;
  border: 1.5px solid #E2E8F0;
  border-radius: 8px;
  font-size: 13.5px;
  font-weight: 500;
  color: #0F172A;
  background: #FAFBFC;
  outline: none;
  box-sizing: border-box;
  font-family: "SF Mono", "Cascadia Code", "Fira Code", ui-monospace, Consolas, monospace;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, background 0.2s ease;
}

.rs-input:focus {
  border-color: #1E40AF;
  box-shadow: 0 0 0 3px rgba(30, 64, 175, 0.08);
  background: #FFFFFF;
}

.rs-input-result:focus {
  border-color: #4338CA;
  box-shadow: 0 0 0 3px rgba(67, 56, 202, 0.08);
  background: #FFFFFF;
}

/* ---------- 表单内分隔符 ---------- */
.rs-form-sep {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  height: 34px;
  border-radius: 7px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.03em;
  flex-shrink: 0;
}

.rs-form-sep.mutex-sep {
  background: #FFFBEB;
  color: #92400E;
  border: 1.5px solid #FDE68A;
}

.rs-form-sep.inference-sep,
.rs-form-sep.inference-arrow {
  background: #EEF2FF;
  color: #4338CA;
  border: 1.5px solid #C7D2FE;
}

/* ---------- 添加按钮 ---------- */
.rs-btn-add {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  height: 42px;
  padding: 0 22px;
  border: 1.5px solid transparent;
  border-radius: 8px;
  font-size: 13.5px;
  font-weight: 700;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.2s ease;
  flex-shrink: 0;
  letter-spacing: 0.01em;
}

.rs-btn-add.mutex {
  background: #FEF3C7;
  color: #92400E;
  border-color: #FCD34D;
}

.rs-btn-add.mutex:hover {
  background: #FDE68A;
  border-color: #FBBF24;
  transform: translateY(-1px);
  box-shadow: 0 3px 10px rgba(245, 158, 11, 0.2);
}

.rs-btn-add.inference {
  background: #E0E7FF;
  color: #3730A3;
  border-color: #A5B4FC;
}

.rs-btn-add.inference:hover {
  background: #C7D2FE;
  border-color: #818CF8;
  transform: translateY(-1px);
  box-shadow: 0 3px 10px rgba(99, 102, 241, 0.2);
}

/* ---------- 规则列表 ---------- */
.rs-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* 规则卡片 */
.rs-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #FFFFFF;
  border: 1px solid #E8ECF1;
  border-radius: 10px;
  padding: 14px 16px;
  transition: all 0.18s ease;
  gap: 10px;
}

.rs-card:hover {
  border-color: #CBD5E1;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.rs-card-body {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  min-width: 0;
  flex-wrap: wrap;
}

.inference-body {
  gap: 8px;
}

/* 标签 */
.rs-tag {
  display: inline-block;
  padding: 5px 11px;
  border-radius: 6px;
  font-size: 12.5px;
  font-weight: 650;
  letter-spacing: 0.01em;
  font-family: "SF Mono", "Cascadia Code", "Fira Code", ui-monospace, Consolas, monospace;
  white-space: nowrap;
  line-height: 1.3;
}

.rs-tag.mutex {
  background: #FFFBEB;
  color: #92400E;
  border: 1px solid #FDE68A;
}

.rs-tag.inference {
  background: #EEF2FF;
  color: #3730A3;
  border: 1px solid #C7D2FE;
}

.rs-tag.inference.is-result {
  background: #DBEAFE;
  color: #1E40AF;
  font-weight: 750;
  border: 1px solid #BFDBFE;
}

/* 卡片内分隔图标 */
.rs-card-sep {
  color: #D97706;
  flex-shrink: 0;
}

.rs-card-op {
  color: #818CF8;
  flex-shrink: 0;
}

.rs-card-arrow {
  color: #6366F1;
  flex-shrink: 0;
}

/* 删除按钮 */
.rs-card-del {
  width: 30px; height: 30px;
  display: flex; align-items: center; justify-content: center;
  background: none; border: 1px solid transparent; border-radius: 7px;
  color: #CBD5E1; cursor: pointer;
  transition: all 0.2s ease;
  flex-shrink: 0;
}

.rs-card:hover .rs-card-del {
  color: #94A3B8;
  border-color: #E2E8F0;
}

.rs-card-del:hover {
  background: #FEF2F2;
  border-color: #FECACA;
  color: #EF4444;
}

/* ---------- 空状态 ---------- */
.rs-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 52px 24px;
  text-align: center;
  background: #FFFFFF;
  border: 1.5px dashed #E2E8F0;
  border-radius: 12px;
}

.rs-empty-icon {
  color: #CBD5E1;
  margin-bottom: 2px;
}

.rs-empty-text {
  font-size: 14px;
  font-weight: 600;
  color: #94A3B8;
}

.rs-empty-hint {
  font-size: 12px;
  color: #CBD5E1;
  font-weight: 500;
  margin-top: -2px;
}

.status-panel {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px;
  background: #ffffff;
  border-radius: 8px;
  border: 1px solid #cbd5e1;
  margin-bottom: 16px;
  font-size: 14px;
  font-weight: 500;
  color: #334155;
  box-shadow: 0 1px 2px rgba(0,0,0,0.05);
}

.status-indicator {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #94a3b8;
  box-shadow: 0 0 0 3px #f1f5f9;
}

.status-panel.success .status-indicator {
  background: #10b981;
  box-shadow: 0 0 0 3px #d1fae5;
}

.status-panel.error .status-indicator {
  background: #ef4444;
  box-shadow: 0 0 0 3px #fee2e2;
}

.status-text {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Canvas */
.canvas {
  position: relative;
  flex: 1;
  overflow: hidden;
  background-color: var(--color-bg-canvas);
  cursor: default;
  background-image:
    radial-gradient(circle, rgba(148,163,184,0.22) 1px, transparent 1px);
  background-size: 24px 24px;
}

.canvas-content {
  width: 100%;
  height: 100%;
  position: absolute;
  inset: 0;
  will-change: transform;
}

.canvas.panning,
.canvas:active {
  cursor: grabbing;
}

.canvas-hint {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  color: #64748b;
  font-size: 15px;
  font-weight: 500;
  pointer-events: none;
  user-select: none;
  background: rgba(255, 255, 255, 0.88);
  padding: 14px 28px;
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-md);
  border: 1px solid var(--color-border-light);
  backdrop-filter: blur(4px);
}

/* Edges */
.edges-layer {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  overflow: visible;
}

.edge-line {
  stroke: #94a3b8;
  stroke-width: 2.5px;
  transition: stroke 0.25s var(--ease-out), stroke-width 0.25s var(--ease-out);
  fill: none;
}

/* 拖拽时禁用所有连线过渡，确保实时跟随 */
.edges-layer.is-dragging .edge-line,
.edges-layer.is-dragging .edge-label-bg,
.edges-layer.is-dragging .edge-label {
  transition: none !important;
}

.edge-line.relation {
  stroke: var(--color-relation);
  stroke-dasharray: 8 4;
  animation: dash-flow 2s linear infinite;
}

@keyframes dash-flow {
  to { stroke-dashoffset: -24; }
}

.edge-line.relation.transitive {
  stroke-width: 4px;
  stroke-dasharray: 3 5;
  stroke: var(--color-symmetric);
}

.edge-line.relation.symmetric {
  stroke: #a78bfa;
  stroke-dasharray: none;
}

.edge-line.parent-child {
  stroke: var(--color-success);
  stroke-width: 2.5px;
}

.edge-group.selected .edge-line {
  stroke: var(--color-primary);
  stroke-width: 4px;
}

.edge-group {
  pointer-events: all;
  cursor: pointer;
  transition: filter 0.2s var(--ease-out);
}

.edge-group:hover .edge-line {
  stroke-width: 4px;
  filter: brightness(1.1) saturate(1.2);
}

.edge-group:hover .edge-line.relation {
  stroke: #4f46e5;
}

.edge-group:hover .edge-line.parent-child {
  stroke: #059669;
}

.edge-click-area {
  cursor: pointer;
  pointer-events: stroke;
}

.edge-label, .edge-label-bg {
  pointer-events: all;
  cursor: pointer;
}

.edge-line.parent-child {
  stroke: #10b981;
}

.edge-label-bg {
  fill: rgba(255, 255, 255, 0.9);
  stroke: var(--color-border);
  stroke-width: 1px;
  filter: drop-shadow(0 1px 2px rgba(0,0,0,0.06));
  transition: all var(--transition-normal);
}

.edge-group:hover .edge-label-bg {
  fill: #ffffff;
  stroke: #cbd5e1;
  filter: drop-shadow(0 2px 4px rgba(0,0,0,0.1));
}

.edge-label {
  font-size: 11px;
  font-weight: 700;
  fill: #475569;
  text-anchor: middle;
  dominant-baseline: middle;
  transition: fill 0.2s var(--ease-out);
  letter-spacing: 0.02em;
}

.edge-group:hover .edge-label {
  fill: #1e293b;
}

/* Detail Panel (Protégé Style) */
.detail-panel {
  width: 320px;
  background: #ffffff;
  border-left: 1px solid #e2e8f0;
  display: flex;
  flex-direction: column;
  box-shadow: -4px 0 24px rgba(15, 23, 42, 0.04);
  z-index: 10;
  animation: panel-slide 0.3s ease-out;
}

@keyframes panel-slide {
  from { transform: translateX(100%); }
  to { transform: translateX(0); }
}

.panel-header {
  padding: 20px 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #f1f5f9;
}

.panel-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: #0f172a;
}

.close-btn {
  background: none;
  border: none;
  font-size: 24px;
  color: #94a3b8;
  cursor: pointer;
  line-height: 1;
}

.close-btn:hover {
  color: #64748b;
}

.panel-content {
  padding: 24px;
  overflow-y: auto;
  flex: 1;
}

.panel-footer {
  padding: 24px;
  border-top: 1px solid #f1f5f9;
  background: #fafafa;
}

.detail-group {
  margin-bottom: 24px;
}

.group-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.detail-group label {
  display: block;
  font-size: 13px;
  font-weight: 700;
  color: #475569;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 8px;
}

.input-field {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  font-size: 14px;
  outline: none;
}

.input-field:focus {
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}

.attr-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.attr-item {
  display: flex;
  gap: 8px;
  align-items: center;
}

.attr-item input {
  flex: 1;
  min-width: 0;
  padding: 8px 10px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  font-size: 13px;
}

.add-btn, .remove-btn {
  background: #f1f5f9;
  border: none;
  border-radius: 4px;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: #64748b;
  transition: all 0.2s;
}

.add-btn:hover {
  background: #e0f2fe;
  color: #0369a1;
}

.remove-btn:hover {
  background: #fef2f2;
  color: #dc2626;
}

.empty-tip {
  font-size: 13px;
  color: #94a3b8;
  text-align: center;
  padding: 12px;
  background: #f8fafc;
  border-radius: 8px;
  border: 1px dashed #cbd5e1;
}

.chara-options {
  display: flex;
  flex-direction: column;
  gap: 12px;
  background: #f8fafc;
  padding: 16px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
}

.chara-item {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  color: #334155;
  cursor: pointer;
  text-transform: none !important;
  font-weight: 500 !important;
}

.chara-item input {
  width: 16px;
  height: 16px;
  accent-color: #2563eb;
}

/* ======================== Node Card ======================== */
.node-card {
  position: absolute;
  top: 0;
  left: 0;
  width: 200px;
  transform: translate(var(--node-x, 0px), var(--node-y, 0px));
  background: linear-gradient(135deg, #ffffff 0%, #fafbfc 100%);
  border-radius: 14px;
  border: 1px solid rgba(203, 213, 225, 0.6);
  box-shadow:
    0 1px 2px rgba(0, 0, 0, 0.04),
    0 2px 8px rgba(0, 0, 0, 0.04),
    0 6px 16px rgba(0, 0, 0, 0.03);
  cursor: grab;
  user-select: none;
  transition:
    border-color 0.25s var(--ease-out),
    box-shadow 0.25s var(--ease-out),
    background 0.25s var(--ease-out);
  will-change: transform, box-shadow;
  z-index: 1;
  overflow: hidden;
}

/* 卡片顶部光晕条 */
.node-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(148, 163, 184, 0.2), transparent);
  z-index: 2;
  pointer-events: none;
}

.node-card:hover {
  transform: translate(var(--node-x, 0px), var(--node-y, 0px)) translateY(-2px);
  box-shadow:
    0 2px 4px rgba(0, 0, 0, 0.05),
    0 4px 14px rgba(0, 0, 0, 0.06),
    0 8px 28px rgba(0, 0, 0, 0.05);
  border-color: rgba(148, 163, 184, 0.8);
  z-index: 10;
}

.node-card:active {
  cursor: grabbing;
}

/* 拖拽中的节点 */
.node-card.dragging {
  cursor: grabbing;
  transform: translate(var(--node-x, 0px), var(--node-y, 0px)) scale(1.03);
  box-shadow:
    0 4px 8px rgba(0, 0, 0, 0.08),
    0 8px 24px rgba(0, 0, 0, 0.08),
    0 16px 48px rgba(0, 0, 0, 0.1),
    0 0 0 1px rgba(37, 99, 235, 0.15);
  border-color: rgba(37, 99, 235, 0.35);
  background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
  z-index: 100;
  opacity: 0.94;
  filter: saturate(1.05);
}

/* 选中态 */
.node-card.selected {
  border-color: var(--color-primary);
  box-shadow:
    0 0 0 3px rgba(37, 99, 235, 0.1),
    0 0 20px rgba(37, 99, 235, 0.06),
    0 4px 14px rgba(0, 0, 0, 0.06),
    0 8px 28px rgba(0, 0, 0, 0.04);
  z-index: 5;
  animation: node-pulse 0.6s var(--ease-spring);
  background: linear-gradient(135deg, #ffffff 0%, #eff6ff 100%);
}

@keyframes node-pulse {
  0% {
    box-shadow: 0 0 0 0 rgba(37, 99, 235, 0.25);
    border-color: #93c5fd;
  }
  100% {
    box-shadow:
      0 0 0 3px rgba(37, 99, 235, 0.1),
      0 0 20px rgba(37, 99, 235, 0.06),
      0 4px 14px rgba(0, 0, 0, 0.06),
      0 8px 28px rgba(0, 0, 0, 0.04);
    border-color: var(--color-primary);
  }
}

/* 连线模式中的源节点 */
.node-card.connecting {
  border-color: var(--color-warning);
  box-shadow:
    0 0 0 3px rgba(217, 119, 6, 0.12),
    0 0 24px rgba(217, 119, 6, 0.05),
    0 4px 14px rgba(0, 0, 0, 0.05);
  animation: pulse-connecting 2.2s var(--ease-in-out) infinite;
  background: linear-gradient(135deg, #ffffff 0%, #fffbeb 100%);
}

@keyframes pulse-connecting {
  0%, 100% {
    box-shadow:
      0 0 0 3px rgba(217, 119, 6, 0.12),
      0 0 24px rgba(217, 119, 6, 0.05),
      0 4px 14px rgba(0, 0, 0, 0.05);
  }
  50% {
    box-shadow:
      0 0 0 5px rgba(217, 119, 6, 0.06),
      0 0 32px rgba(217, 119, 6, 0.02),
      0 4px 14px rgba(0, 0, 0, 0.05);
  }
}

/* ======================== 顶部色条 ======================== */
.node-topbar {
  height: 4px;
  background: linear-gradient(90deg, #cbd5e1, #e2e8f0);
  border-radius: 0;
  transition: background 0.3s var(--ease-out);
  position: relative;
  z-index: 1;
}

.node-topbar::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 1px;
  background: rgba(255, 255, 255, 0.6);
}

.node-topbar.has-children {
  background: linear-gradient(90deg, var(--color-success), #34d399);
}

.node-card.selected .node-topbar {
  background: linear-gradient(90deg, var(--color-primary), #6366f1);
}

.node-card.selected .node-topbar.has-children {
  background: linear-gradient(90deg, var(--color-primary), var(--color-success));
}

/* ======================== 节点头部 ======================== */
.node-header {
  padding: 14px 16px 12px 16px;
  display: flex;
  align-items: center;
  gap: 10px;
  border-bottom: 1px solid rgba(241, 245, 249, 0.8);
  background: transparent;
  border-radius: 0;
  transition: background 0.25s var(--ease-out), border-color 0.25s var(--ease-out);
}

.node-card.selected .node-header {
  background: rgba(239, 246, 255, 0.55);
  border-bottom-color: rgba(191, 219, 254, 0.8);
}

/* ======================== 节点图标 ======================== */
.node-icon {
  color: #64748b;
  display: flex;
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  background: linear-gradient(135deg, #f1f5f9, #e2e8f0);
  border-radius: 8px;
  align-items: center;
  justify-content: center;
  transition: all 0.25s var(--ease-out);
}

.node-card.selected .node-icon {
  color: var(--color-primary);
  background: linear-gradient(135deg, #dbeafe, #bfdbfe);
}

.node-icon svg {
  width: 16px;
  height: 16px;
}

/* ======================== 节点标题 ======================== */
.node-title {
  font-size: 14px;
  font-weight: 650;
  color: #0f172a;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  letter-spacing: -0.01em;
  line-height: 1.3;
}

.node-title i, .ocr-item i {
  font-family: "Times New Roman", Times, serif;
  font-style: italic;
  margin-right: 1px;
}

.node-title sub, .ocr-item sub {
  font-size: 0.75em;
  bottom: -0.2em;
  margin-left: 1px;
  color: #475569;
}

/* ======================== 节点内容区 ======================== */
.node-body {
  padding: 10px 16px 14px 16px;
}

.node-id {
  font-size: 11px;
  color: #94a3b8;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-weight: 500;
  background: rgba(241, 245, 249, 0.7);
  display: inline-block;
  padding: 2px 8px;
  border-radius: 5px;
  letter-spacing: 0.02em;
}

.node-card.selected .node-id {
  background: rgba(219, 234, 254, 0.6);
  color: #3b82f6;
}

/* ======================== 折叠按钮 ======================== */
.collapse-btn {
  position: absolute;
  bottom: -11px;
  left: 50%;
  transform: translateX(-50%);
  width: 22px;
  height: 22px;
  background: #ffffff;
  border: 1.5px solid #e2e8f0;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  color: #64748b;
  cursor: pointer;
  z-index: 10;
  box-shadow:
    0 1px 3px rgba(0, 0, 0, 0.06),
    0 2px 8px rgba(0, 0, 0, 0.04);
  transition: all 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);
  line-height: 1;
}

.collapse-btn:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
  background: #eff6ff;
  box-shadow:
    0 2px 6px rgba(37, 99, 235, 0.12),
    0 4px 14px rgba(37, 99, 235, 0.08);
  transform: translateX(-50%) scale(1.18);
}

.collapse-btn:active {
  transform: translateX(-50%) scale(0.92);
}

/* 缩放控件 */
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
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: all var(--transition-normal);
  backdrop-filter: blur(8px);
  box-shadow: var(--shadow-xs);
  line-height: 1;
}

.zoom-btn:hover {
  background: #ffffff;
  border-color: var(--color-primary);
  color: var(--color-primary);
  box-shadow: var(--shadow-md);
  transform: scale(1.08);
}

.zoom-btn:active {
  transform: scale(0.94);
}

/* 右键菜单 */
.context-menu {
  position: absolute;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 10px;
  box-shadow: 0 12px 32px -6px rgba(0, 0, 0, 0.1), 0 8px 12px -6px rgba(0, 0, 0, 0.08);
  padding: 6px;
  min-width: 200px;
  z-index: 1000;
  animation: context-enter 0.2s var(--ease-spring);
  transform-origin: top left;
}

@keyframes context-enter {
  from { opacity: 0; transform: scale(0.92) translateY(-4px); }
  to { opacity: 1; transform: scale(1) translateY(0); }
}

.menu-item {
  padding: 10px 12px;
  font-size: 13px;
  font-weight: 500;
  color: #374151;
  cursor: pointer;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  gap: 10px;
  transition: all var(--transition-fast);
}

.menu-item:hover {
  background: var(--color-border-light);
  color: var(--color-text);
}

.menu-icon {
  font-size: 13px;
  width: 18px;
  text-align: center;
  flex-shrink: 0;
  opacity: 0.8;
}

.menu-divider {
  height: 1px;
  background: var(--color-border);
  margin: 4px 8px;
}

/* Prompt Modal */
.prompt-overlay {
  position: absolute;
  inset: 0;
  background: rgba(15, 23, 42, 0.5);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}

.prompt-dialog {
  background: #ffffff;
  padding: 32px;
  border-radius: 16px;
  width: 800px;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
  animation: modal-enter 0.2s ease-out;
}

@keyframes modal-enter {
  from { opacity: 0; transform: scale(0.95) translateY(10px); }
  to { opacity: 1; transform: scale(1) translateY(0); }
}

.prompt-dialog h3 {
  margin: 0 0 20px 0;
  font-size: 18px;
  font-weight: 700;
  color: #0f172a;
}

.confirm-message {
  font-size: 15px;
  color: #475569;
  line-height: 1.6;
  margin-bottom: 24px;
}

.prompt-dialog input {
  width: 100%;
  padding: 12px 14px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  font-size: 15px;
  color: #0f172a;
  outline: none;
  transition: border-color 0.2s, box-shadow 0.2s;
  margin-bottom: 24px;
  background: #f8fafc;
}

.prompt-dialog input:focus {
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.15);
  background: #ffffff;
}

.prompt-actions {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
}

.prompt-actions .btn {
  width: auto;
  margin: 0;
  padding: 10px 20px;
}

/* ======================== 贝叶斯因果分析面板 ======================== */

/* 面板宽度加宽 */
.rules-panel.bayesian-panel {
  width: 600px;
}

/* ---------- Tab栏 ---------- */
.rs-tabs {
  display: flex;
  border-bottom: 1.5px solid #E2E8F0;
  padding: 0 20px;
  gap: 4px;
  flex-shrink: 0;
}

.rs-tab {
  padding: 11px 18px;
  border: none;
  border-bottom: 2.5px solid transparent;
  background: transparent;
  color: #64748B;
  font-size: 13.5px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
  margin-bottom: -1.5px;
}

.rs-tab:hover {
  color: #334155;
  background: #F8FAFC;
}

.rs-tab.active {
  color: #1E40AF;
  border-bottom-color: #1E40AF;
  background: #EEF2FF;
}

/* ---------- 内容区容器 ---------- */
.by-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 20px;
}

/* ---------- 下拉选择 + 按钮行 ---------- */
.by-select-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.by-select-row label {
  font-size: 13px;
  font-weight: 600;
  color: #334155;
  white-space: nowrap;
}

.by-select {
  flex: 1;
  min-width: 140px;
  padding: 9px 12px;
  border: 1.5px solid #1E40AF;
  border-radius: 8px;
  background: #FFFFFF;
  color: #0F172A;
  font-size: 13.5px;
  font-weight: 500;
  outline: none;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.by-select:focus {
  border-color: #1D4ED8;
  box-shadow: 0 0 0 3px rgba(30, 64, 175, 0.1);
}

/* ---------- 运行按钮 ---------- */
.by-run-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 10px 24px;
  border: none;
  border-radius: 8px;
  background: #1E40AF;
  color: #FFFFFF;
  font-size: 13.5px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.25s ease;
  box-shadow: 0 2px 8px rgba(30, 64, 175, 0.25);
  white-space: nowrap;
  letter-spacing: 0.02em;
}

.by-run-btn:hover:not(:disabled) {
  background: #1D4ED8;
  transform: translateY(-1px);
  box-shadow: 0 4px 14px rgba(30, 64, 175, 0.35);
}

.by-run-btn:active:not(:disabled) {
  transform: translateY(0);
  box-shadow: 0 1px 4px rgba(30, 64, 175, 0.2);
}

.by-run-btn:disabled {
  background: #94A3B8;
  cursor: not-allowed;
  box-shadow: none;
}

.by-run-full {
  width: 100%;
  padding: 14px 24px;
  font-size: 15px;
}

/* ---------- 加载状态 ---------- */
.by-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 24px;
  font-size: 14px;
  font-weight: 600;
  color: #1E40AF;
  background: #F8FAFC;
  border: 1px dashed #E2E8F0;
  border-radius: 10px;
}

/* ---------- 结果区域 ---------- */
.by-result {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.by-result-title {
  margin: 0;
  font-size: 14px;
  font-weight: 700;
  color: #0F172A;
  padding-bottom: 6px;
  border-bottom: 1px solid #F1F5F9;
}

/* ---------- 因子卡片 ---------- */
.by-factor-card {
  background: #FFFFFF;
  border: 1px solid #E2E8F0;
  border-radius: 10px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.by-factor-card:hover {
  border-color: #CBD5E1;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

/* 因子顶部：名称 + 等级标签 + 概率 */
.by-factor-top {
  display: flex;
  align-items: center;
  gap: 10px;
}

.by-factor-top .by-factor-name {
  font-size: 14px;
  font-weight: 650;
  color: #0F172A;
  flex: 1;
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 等级标签 */
.by-level-tag {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 6px;
  font-size: 11.5px;
  font-weight: 700;
  letter-spacing: 0.03em;
  white-space: nowrap;
  flex-shrink: 0;
}

.by-level-tag.很高 {
  background: #D1FAE5;
  color: #065F46;
  border: 1px solid #A7F3D0;
}

.by-level-tag.高 {
  background: #DBEAFE;
  color: #1E40AF;
  border: 1px solid #BFDBFE;
}

.by-level-tag.中等 {
  background: #FEF3C7;
  color: #92400E;
  border: 1px solid #FCD34D;
}

.by-level-tag.较低 {
  background: #F1F5F9;
  color: #475569;
  border: 1px solid #E2E8F0;
}

.by-level-tag.低 {
  background: #F1F5F9;
  color: #475569;
  border: 1px solid #E2E8F0;
}

/* 概率数值 */
.by-prob {
  font-size: 18px;
  font-weight: 800;
  color: #1E40AF;
  font-variant-numeric: tabular-nums;
  flex-shrink: 0;
  min-width: 42px;
  text-align: right;
}

/* 概率进度条 */
.by-prob-bar {
  height: 6px;
  background: #E8ECF1;
  border-radius: 3px;
  overflow: hidden;
}

.by-prob-fill {
  height: 100%;
  border-radius: 3px;
  background: linear-gradient(90deg, #3B82F6, #1E40AF);
  transition: width 0.45s cubic-bezier(0.22, 0.61, 0.36, 1);
}

/* 路径列表 */
.by-paths {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.by-path-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 10px;
  background: #F8FAFC;
  border-radius: 6px;
  border: 1px solid #F1F5F9;
  gap: 10px;
}

.by-path-str {
  font-size: 12px;
  font-family: "SF Mono", "Cascadia Code", "Fira Code", ui-monospace, Consolas, monospace;
  color: #334155;
  line-height: 1.5;
  word-break: break-all;
  flex: 1;
}

.by-path-prob {
  font-size: 12.5px;
  font-weight: 700;
  color: #1E40AF;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}

/* ---------- 权重配置弹窗 ---------- */
.weight-dialog {
  width: 560px !important;
  max-width: 94vw;
  max-height: 80vh;
  overflow-y: auto;
}

/* ---------- 权重配置卡片 ---------- */
.by-weights-card {
  background: #FFFFFF;
  border: 1px solid #E2E8F0;
  border-radius: 12px;
  padding: 20px 22px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.by-weights-card h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 700;
  color: #0F172A;
}

.by-weights-desc {
  margin: 0;
  font-size: 12.5px;
  color: #64748B;
  line-height: 1.65;
}

/* 权重行 */
.by-weight-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  background: #F8FAFC;
  border: 1px solid #F1F5F9;
  border-radius: 8px;
}

.by-weight-name {
  font-size: 13.5px;
  font-weight: 600;
  color: #0F172A;
  min-width: 60px;
}

.by-slider {
  flex: 1;
  height: 6px;
  -webkit-appearance: none;
  appearance: none;
  background: #E2E8F0;
  border-radius: 3px;
  outline: none;
}

.by-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #1E40AF;
  cursor: pointer;
  box-shadow: 0 1px 4px rgba(30, 64, 175, 0.3);
  transition: transform 0.15s ease;
}

.by-slider::-webkit-slider-thumb:hover {
  transform: scale(1.15);
}

.by-weight-val {
  font-size: 13px;
  font-weight: 700;
  color: #1E40AF;
  font-variant-numeric: tabular-nums;
  min-width: 36px;
  text-align: right;
}

.by-weight-del {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border: 1px solid #E2E8F0;
  border-radius: 6px;
  background: #FFFFFF;
  color: #94A3B8;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.2s ease;
  flex-shrink: 0;
}

.by-weight-del:hover {
  background: #FEF2F2;
  border-color: #FCA5A5;
  color: #EF4444;
}

/* 添加权重行 */
.by-weight-add {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border: 1.5px dashed #E2E8F0;
  border-radius: 8px;
  background: #FAFBFC;
}

.by-input-sm {
  width: 100px;
  padding: 7px 10px;
  border: 1px solid #E2E8F0;
  border-radius: 6px;
  font-size: 13px;
  color: #0F172A;
  outline: none;
  transition: border-color 0.2s ease;
}

.by-input-sm:focus {
  border-color: #1E40AF;
  box-shadow: 0 0 0 2px rgba(30, 64, 175, 0.08);
}

.by-slider-sm {
  flex: 1;
  height: 6px;
  -webkit-appearance: none;
  appearance: none;
  background: #E2E8F0;
  border-radius: 3px;
  outline: none;
}

.by-slider-sm::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: #1E40AF;
  cursor: pointer;
}

.by-weight-val-add {
  font-size: 13px;
  font-weight: 600;
  color: #64748B;
  font-variant-numeric: tabular-nums;
  min-width: 32px;
  text-align: right;
}

.by-weight-add-btn {
  display: inline-flex;
  align-items: center;
  padding: 6px 14px;
  border: 1.5px solid #1E40AF;
  border-radius: 6px;
  background: #FFFFFF;
  color: #1E40AF;
  font-size: 12.5px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
}

.by-weight-add-btn:hover {
  background: #1E40AF;
  color: #FFFFFF;
}

/* ---------- 排名项 ---------- */
.by-rank-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  background: #F8FAFC;
  border: 1px solid #F1F5F9;
  border-radius: 8px;
  gap: 12px;
}

.by-rank-name {
  font-size: 13.5px;
  font-weight: 600;
  color: #0F172A;
  flex: 1;
}

.by-rank-score {
  font-size: 12.5px;
  color: #64748B;
  white-space: nowrap;
}

/* ---------- 总结文本 ---------- */
.by-summary {
  background: #FFFFFF;
  border: 1px solid #E2E8F0;
  border-radius: 10px;
  padding: 16px 18px;
  font-size: 13.5px;
  color: #334155;
  line-height: 1.75;
  border-left: 4px solid #1E40AF;
}

/* ---------- 画布高亮联动 ---------- */
.node-card.highlighted {
  box-shadow: 0 0 0 3px rgba(30, 64, 175, 0.5), 0 0 16px rgba(30, 64, 175, 0.25), var(--card-shadow);
}

.node-card.dimmed {
  opacity: 0.3;
  transition: opacity 0.35s ease;
}

.edge-group.dimmed .edge-line {
  opacity: 0.15;
  transition: opacity 0.35s ease;
}

.edge-group.highlighted .edge-line {
  opacity: 1;
  stroke-width: 3.5;
  filter: drop-shadow(0 0 4px rgba(30, 64, 175, 0.4));
}

.edge-group.highlighted .edge-label-bg {
  fill: #1E40AF;
}

.edge-group.highlighted .edge-label {
  fill: #FFFFFF;
  font-weight: 700;
}

/* ---------- 侧边栏入口按钮 ---------- */
.btn-bayesian {
  background: #1E40AF;
  color: #FFFFFF;
  border: none;
  box-shadow: 0 2px 4px rgba(30, 64, 175, 0.15);
  gap: 8px;
}

.btn-bayesian:hover:not(:disabled) {
  background: #1E3A8A;
  box-shadow: 0 4px 8px rgba(30, 64, 175, 0.25);
  transform: translateY(-1px);
  color: #FFFFFF;
}

.btn-bayesian svg { flex-shrink: 0; }

.btn-weight-config {
  background: #f8fafc;
  color: #1E40AF;
  border: 1.5px solid #BFDBFE;
  gap: 8px;
}
.btn-weight-config:hover:not(:disabled) {
  background: #eff6ff;
  border-color: #93C5FD;
  color: #1E3A8A;
  transform: translateY(-1px);
}

/* ========== 贝叶斯全局概览 (Overview) ========== */

/* -- 区块容器 -- */
.ov-section {
  margin-bottom: 28px;
}

.ov-section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: #0F172A;
  margin: 0 0 14px 0;
}

.ov-section-title svg {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
}

.ov-section-desc {
  font-size: 13px;
  color: #64748B;
  margin: -6px 0 12px 0;
  line-height: 1.5;
}

/* -- 总结卡片 -- */
.ov-summary {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  background: #EFF6FF;
  border-left: 3px solid #1E40AF;
  border-radius: 8px;
  padding: 14px 16px;
  font-size: 13.5px;
  color: #334155;
  line-height: 1.7;
  margin-bottom: 20px;
}

/* -- 影响力排名 -- */
.ov-rank-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.ov-rank-card {
  display: flex;
  align-items: center;
  gap: 12px;
  background: #FFFFFF;
  border: 1px solid #E8ECF1;
  border-radius: 10px;
  padding: 12px 14px;
  transition: box-shadow 0.2s ease;
}

.ov-rank-card:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.ov-rank-num {
  width: 36px;
  height: 36px;
  min-width: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 700;
  color: #FFFFFF;
  background: #E2E8F0;
  flex-shrink: 0;
}

.ov-rank-num.rank-1 {
  background: linear-gradient(135deg, #FCD34D, #F59E0B);
  box-shadow: 0 2px 6px rgba(245, 158, 11, 0.35);
}

.ov-rank-num.rank-2 {
  background: linear-gradient(135deg, #CBD5E1, #94A3B8);
  box-shadow: 0 2px 6px rgba(148, 163, 184, 0.35);
}

.ov-rank-num.rank-3 {
  background: linear-gradient(135deg, #F59E0B, #D97706);
  box-shadow: 0 2px 6px rgba(217, 119, 6, 0.35);
}

.ov-rank-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.ov-rank-name {
  font-size: 14px;
  font-weight: 600;
  color: #0F172A;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.ov-rank-bar-wrap {
  flex: 1;
  height: 8px;
  border-radius: 4px;
  background: #F1F5F9;
  overflow: hidden;
}

.ov-rank-bar {
  height: 100%;
  border-radius: 4px;
  background: linear-gradient(90deg, #3B82F6, #1E40AF);
  transition: width 0.6s ease;
}

.ov-rank-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-width: 40px;
  flex-shrink: 0;
}

.ov-rank-count {
  font-size: 24px;
  font-weight: 700;
  color: #1E40AF;
  line-height: 1.1;
}

.ov-rank-unit {
  font-size: 11px;
  color: #94A3B8;
}

/* -- 最脆弱节点 -- */
.ov-vuln-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.ov-vuln-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: #FFFFFF;
  border: 1px solid #E8ECF1;
  border-radius: 10px;
  padding: 20px 16px;
  transition: box-shadow 0.2s ease;
}

.ov-vuln-card:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.ov-vuln-num {
  font-size: 48px;
  font-weight: 700;
  line-height: 1.1;
  white-space: nowrap;
}

.ov-vuln-num-unit {
  font-size: 14px;
  font-weight: 400;
  color: #94A3B8;
  margin-left: 2px;
}

.ov-vuln-label {
  font-size: 13px;
  color: #64748B;
  margin-top: 6px;
  text-align: center;
  line-height: 1.3;
}

/* -- 最强因果链 -- */
.ov-chain-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.ov-chain-card {
  display: flex;
  align-items: center;
  gap: 12px;
  background: #FFFFFF;
  border: 1px solid #E8ECF1;
  border-radius: 10px;
  padding: 12px 14px;
  transition: box-shadow 0.2s ease;
}

.ov-chain-card:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.ov-chain-badge {
  min-width: 44px;
  text-align: center;
  font-weight: 700;
  font-size: 12.5px;
  border-radius: 6px;
  padding: 4px 8px;
  color: #FFFFFF;
  flex-shrink: 0;
  line-height: 1.4;
}

.ov-chain-path {
  font-size: 13px;
  color: #334155;
  font-family: 'Courier New', 'Consolas', 'Menlo', monospace;
  word-break: break-all;
  line-height: 1.5;
}

/* -- 响应式 -- */
@media (max-width: 600px) {
  .ov-vuln-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .ov-rank-card {
    padding: 10px 10px;
    gap: 8px;
  }

  .ov-rank-num {
    width: 30px;
    height: 30px;
    min-width: 30px;
    font-size: 12px;
  }

  .ov-rank-count {
    font-size: 20px;
  }

  .ov-vuln-num {
    font-size: 36px;
  }
}

</style>
