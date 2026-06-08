# Sidebar Workbench Tabs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the left sidebar accordion with a non-collapsing workbench (Project / Data Import / Modeling tabs), keep top perspectives (Leader/Engineer/Process) unchanged, and provide “Add Node” + “Add Relation” (canvas-pick + dialog) in one place.

**Architecture:** Implement workbench tabs directly in `App.vue` (existing single-page shell) to avoid cross-component rewiring. Reuse existing project actions and `DataSourcePanel`. Keep existing canvas interaction for relation-pick, add a new relation dialog overlay for search-based selection. Persist “relation create mode” in localStorage.

**Tech Stack:** Vue 3 (script setup), Vite, plain CSS in SFC.

---

## File Map

**Modify**
- `h:\Git\OCR_benti-main_win7\frontend\src\App.vue`

**Optional Modify (only if needed after wiring)**
- `h:\Git\OCR_benti-main_win7\frontend\src\components\datasource\DataSourcePanel.vue` (only if we want it to emit “import success” to trigger perspective switch)

**No new components** (keep changes localized for faster review).

---

### Task 1: Introduce Workbench Tab State + Minimal UI Skeleton

**Files:**
- Modify: `frontend/src/App.vue`

- [ ] **Step 1: Add new reactive state**

Add these in the “项目管理” / UI state region (near other refs):

```js
const activeWorkbenchTab = ref("project"); // project | import | modeling
const relationCreateMode = ref("canvas"); // canvas | dialog
```

- [ ] **Step 2: Load/persist relation mode**

Add in `onMounted()`:

```js
try {
  const saved = localStorage.getItem("benti_relation_create_mode");
  if (saved === "canvas" || saved === "dialog") relationCreateMode.value = saved;
} catch {}
```

Add a watcher:

```js
watch(relationCreateMode, (val) => {
  try { localStorage.setItem("benti_relation_create_mode", val); } catch {}
});
```

(If `watch` isn’t imported in `App.vue`, import it from Vue.)

- [ ] **Step 3: Add a sidebar tab strip (non-collapsing)**

In `<aside class="sidebar">`, replace the accordion section with:
- A `workbench-tabs` bar (3 buttons)
- A single `workbench-body` that switches content with `v-if="activeWorkbenchTab === '...'"`.

This step is UI-only: keep existing project selector markup temporarily in place until Task 2.

- [ ] **Step 4: Verify it compiles**

Run:

```bash
cd frontend
npm run build
```

Expected: build succeeds.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.vue
git commit -m "feat(ui): add workbench tab shell in sidebar"
```

---

### Task 2: Move Project Management UI Into “项目” Tab

**Files:**
- Modify: `frontend/src/App.vue`

- [ ] **Step 1: Relocate the existing project selector/dropdown**

Move the block currently in `.sidebar-header .project-selector` into the `activeWorkbenchTab === 'project'` panel.

Keep behavior:
- Switch project
- Rename project
- Delete project (manager only)
- Create project (manager only)

- [ ] **Step 2: Make new project default jump to import tab**

In `createProject()` success path, after switching to the created project:

```js
activeWorkbenchTab.value = "import";
```

Also close the project dropdown if open:

```js
projectMenuOpen.value = false;
```

- [ ] **Step 3: Verify create/delete work in all top perspectives**

Manual check:
- In Leader view, create project: should respond immediately and switch.
- In Engineer view, delete project: list updates without refresh.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/App.vue
git commit -m "feat(ui): project management in workbench tab and jump to import"
```

---

### Task 3: “数据导入” Tab (Reuse DataSourcePanel) + Post-Import Auto Switch

**Files:**
- Modify: `frontend/src/App.vue`
- Optional Modify: `frontend/src/components/datasource/DataSourcePanel.vue`

- [ ] **Step 1: Render DataSourcePanel under import tab**

In the import panel:
- If `isManager`: show `<DataSourcePanel @import-nodes="onImportNodes" />`
- Else: show a simple “仅管理者可导入数据” placeholder

- [ ] **Step 2: After import, auto-switch top perspective to process**

At the end of `onImportNodes(...)` (or after it successfully sets nodes/edges), set:

```js
currentPerspective.value = "process";
```

Do NOT change `activeWorkbenchTab` (user can keep import tab open or switch manually).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/App.vue
git commit -m "feat(ui): import tab uses DataSourcePanel and switches to process after import"
```

---

### Task 4: “建模” Tab – Add Node Button (place at viewport center)

**Files:**
- Modify: `frontend/src/App.vue`

- [ ] **Step 1: Adjust default placement in addOntology()**

When `x/y` are null, place at the visible canvas center (not random).

Implementation sketch:

```js
let px = x;
let py = y;
if (px === null || py === null) {
  if (canvasRef.value) {
    const rect = canvasRef.value.getBoundingClientRect();
    px = (rect.width / 2 - viewOffset.value.x) / zoom.value;
    py = (rect.height / 2 - viewOffset.value.y) / zoom.value;
  } else {
    px = (120 - viewOffset.value.x) / zoom.value;
    py = (120 - viewOffset.value.y) / zoom.value;
  }
}
```

Use `px/py` in `createNode()` payload.

- [ ] **Step 2: Add “新增节点” button in modeling tab**

It calls:

```js
addOntology(null, null)
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/App.vue
git commit -m "feat(ui): add node button in modeling tab and center placement"
```

---

### Task 5: “建模” Tab – Add Relation (Canvas Pick Mode)

**Files:**
- Modify: `frontend/src/App.vue`

- [ ] **Step 1: Add a new starter that does not require pre-select**

Create:

```js
function beginCanvasPickRelation() {
  connectMode.value = true;
  connectSourceId.value = null;
  statusMessage.value = "连线：请先点击源本体";
}
```

- [ ] **Step 2: Update onClickNode() status texts for 2-step flow**

Currently it already handles “if no source, set it”. Ensure messages match:
- after picking source: “已选择源本体，请点击目标本体”

Keep existing `createEdge` + reload behavior.

- [ ] **Step 3: Hook modeling tab “新增关系”**

If `relationCreateMode === 'canvas'`:
- call `beginCanvasPickRelation()`
- (optional) also switch top perspective to `process` so user can click on canvas immediately

```js
currentPerspective.value = "process";
```

- [ ] **Step 4: Add the mode toggle control**

Near the “新增关系” button: a 2-state toggle (canvas/dialog) that updates `relationCreateMode`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.vue
git commit -m "feat(ui): add relation canvas-pick mode from modeling tab"
```

---

### Task 6: “建模” Tab – Add Relation (Dialog Mode With Search)

**Files:**
- Modify: `frontend/src/App.vue`

- [ ] **Step 1: Add dialog state**

```js
const relationDialogVisible = ref(false);
const relationDraft = ref({
  sourceId: "",
  targetId: "",
  relation: "",
  weight: 0.65
});
const sourceQuery = ref("");
const targetQuery = ref("");
```

- [ ] **Step 2: Add computed search lists**

Filter `nodes.value` by `name.includes(query)` (case-insensitive), limit 20.

- [ ] **Step 3: Render dialog overlay in template**

Overlay includes:
- Source search input + clickable results list (select sets `relationDraft.sourceId`)
- Target search input + clickable results list
- Relation text input
- Weight number input (0–1)
- Cancel/Confirm buttons

Confirm:
- validate source != target and both exist
- call `createEdge({source, target, relation, kind: 'relation', weight})`
- close dialog, clear draft, switch to process (optional)

- [ ] **Step 4: Hook modeling tab “新增关系”**

If `relationCreateMode === 'dialog'`, open dialog.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.vue
git commit -m "feat(ui): add relation dialog mode with searchable node pick"
```

---

### Task 7: Remove Accordion UI + Keep Remaining Actions Accessible

**Files:**
- Modify: `frontend/src/App.vue`

- [ ] **Step 1: Delete accordion headers/bodies and their state**

Remove:
- `.accordion-group` blocks in sidebar
- `activeAccordion` and `toggleAccordion()` if no longer used

Keep these actions, moved into modeling tab:
- 保存当前画布 (`syncGraph`)
- 一键清空画布 (`clearGraph`) (manager)
- 关系逻辑规则设置 (`rulesDialogVisible = true`) (manager)
- 贝叶斯网络分析 / 关系权重配置 (if still needed, place under modeling tab as normal buttons)

- [ ] **Step 2: Update CSS**

Add styles for:
- `workbench-tabs`, `workbench-tab`, active state
- `workbench-panel` sections (simple titles, no collapses)

Remove obsolete accordion styles if they conflict (leave if used elsewhere).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/App.vue
git commit -m "refactor(ui): replace sidebar accordions with workbench tabs"
```

---

### Task 8: Verification Pass (Build + Diagnostics)

**Files:**
- Modify if needed: `frontend/src/App.vue`

- [ ] **Step 1: Run frontend build**

```bash
cd frontend
npm run build
```

- [ ] **Step 2: Manual smoke**

Using `start.bat`:
- Create project from any perspective → left tab jumps to import
- Import Excel → auto switch to process (top) and graph appears
- Modeling tab: add node creates at viewport center
- Modeling tab: add relation
  - canvas mode: click source then target
  - dialog mode: search source/target, confirm

- [ ] **Step 3: Commit any fixes**

```bash
git add frontend/src/App.vue
git commit -m "fix(ui): polish workbench tabs and relation flows"
```

---

## Spec Coverage Check

- Non-collapsing left sidebar: Task 1 + Task 7
- Project / Data Import / Modeling tabs: Task 1–3
- New project jumps to import: Task 2
- Add node + add relation together: Task 4–6
- Relation dual mode: Task 5–6
- Keep top perspective tabs: no change required

