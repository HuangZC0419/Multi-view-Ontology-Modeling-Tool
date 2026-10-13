<script setup>
import { ref } from "vue";

const props = defineProps({
  apiBase: { type: String, default: "" },
  projectId: { type: [String, Number], default: null },
});

// 结果定位交由父组件处理，本组件不接触画布
const emit = defineEmits(["locate-concept", "locate-relation"]);

const SCOPES = [
  { key: "concept", label: "概念名称" },
  { key: "attribute", label: "概念属性" },
  { key: "relation", label: "关系" },
  { key: "source", label: "数据来源" },
];

const FIELD_LABELS = {
  name: "概念名称",
  attribute: "概念属性",
  relation: "关系",
  source: "数据来源",
};

const query = ref("");
const selectedScopes = ref(SCOPES.map((s) => s.key));
const results = ref(null);
const loading = ref(false);
const error = ref("");

function fieldLabel(key) {
  return FIELD_LABELS[key] || key;
}

function toggleScope(key) {
  const idx = selectedScopes.value.indexOf(key);
  if (idx >= 0) selectedScopes.value.splice(idx, 1);
  else selectedScopes.value.push(key);
}

async function runSearch() {
  const kw = query.value.trim();
  error.value = "";

  if (!kw) {
    error.value = "请输入检索关键词";
    return;
  }
  if (!props.projectId) {
    error.value = "请先选择一个项目";
    return;
  }
  if (!selectedScopes.value.length) {
    error.value = "请至少选择一个检索范围";
    return;
  }

  loading.value = true;
  try {
    const params = new URLSearchParams({
      project_id: String(props.projectId),
      q: kw,
      scope: selectedScopes.value.join(","),
    });
    const res = await fetch(`${props.apiBase}/api/knowledge/search?${params}`);
    if (!res.ok) {
      throw new Error((await res.text()) || `HTTP ${res.status}`);
    }
    results.value = await res.json();
  } catch (e) {
    error.value = `检索失败：${e.message}`;
    results.value = null;
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="ksp">
    <div class="ksp-search-row">
      <input
        v-model="query"
        class="ksp-input"
        type="text"
        placeholder="输入概念名称、属性或关系关键词"
        @keyup.enter="runSearch"
      />
      <button class="ksp-btn" :disabled="loading" @click="runSearch">
        {{ loading ? "检索中..." : "开始检索" }}
      </button>
    </div>

    <div class="ksp-scopes">
      <label
        v-for="s in SCOPES"
        :key="s.key"
        class="ksp-scope"
        :class="{ active: selectedScopes.includes(s.key) }"
      >
        <input
          type="checkbox"
          :checked="selectedScopes.includes(s.key)"
          @change="toggleScope(s.key)"
        />
        <span>{{ s.label }}</span>
      </label>
    </div>

    <p v-if="error" class="ksp-error">{{ error }}</p>

    <div v-if="results" class="ksp-results">
      <div class="ksp-summary">共命中 {{ results.total }} 条结果</div>

      <div v-if="results.concepts.length" class="ksp-group">
        <div class="ksp-group-title">知识概念（{{ results.concepts.length }}）</div>
        <button
          v-for="c in results.concepts"
          :key="c.id"
          class="ksp-item"
          @click="emit('locate-concept', c.id)"
        >
          <span class="ksp-item-name">{{ c.name }}</span>
          <span class="ksp-item-field">{{ fieldLabel(c.match_field) }}</span>
          <span class="ksp-item-snippet">{{ c.match_snippet }}</span>
          <span v-if="c.parent_path" class="ksp-item-path">
            路径：{{ c.parent_path }}{{ c.name }}
          </span>
        </button>
      </div>

      <div v-if="results.relations.length" class="ksp-group">
        <div class="ksp-group-title">知识关系（{{ results.relations.length }}）</div>
        <button
          v-for="r in results.relations"
          :key="r.id"
          class="ksp-item"
          @click="emit('locate-relation', r.id)"
        >
          <span class="ksp-item-name">
            {{ r.source_name }} —{{ r.relation }}→ {{ r.target_name }}
          </span>
          <span class="ksp-item-field">{{ fieldLabel(r.match_field) }}</span>
        </button>
      </div>

      <div v-if="!results.total" class="ksp-empty">
        未找到匹配的知识，请尝试其他关键词
      </div>
    </div>
  </div>
</template>

<style scoped>
.ksp {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.ksp-search-row {
  display: flex;
  gap: 6px;
}

.ksp-input {
  flex: 1;
  min-width: 0;
  height: 34px;
  padding: 0 10px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  font-size: 12.5px;
  font-family: inherit;
  color: #0f172a;
  outline: none;
  transition: border-color 0.2s;
}

.ksp-input:focus {
  border-color: #1e3a5f;
}

.ksp-btn {
  height: 34px;
  padding: 0 12px;
  border: none;
  border-radius: 8px;
  background: #1e3a5f;
  color: #ffffff;
  font-size: 12.5px;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.2s;
}

.ksp-btn:hover:not(:disabled) {
  background: #2d4f7c;
}

.ksp-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.ksp-scopes {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.ksp-scope {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  border: 1px solid #e2e8f0;
  border-radius: 999px;
  font-size: 11.5px;
  color: #64748b;
  cursor: pointer;
  user-select: none;
  transition: all 0.15s;
}

.ksp-scope.active {
  border-color: #1e3a5f;
  background: #eff4fa;
  color: #1e3a5f;
  font-weight: 600;
}

.ksp-scope input {
  display: none;
}

.ksp-error {
  margin: 0;
  font-size: 12px;
  color: #dc2626;
}

.ksp-results {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.ksp-summary {
  font-size: 12px;
  color: #64748b;
  font-weight: 600;
}

.ksp-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.ksp-group-title {
  font-size: 11.5px;
  font-weight: 600;
  color: #94a3b8;
  letter-spacing: 0.03em;
}

.ksp-item {
  display: flex;
  flex-direction: column;
  gap: 3px;
  width: 100%;
  padding: 8px 10px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #ffffff;
  text-align: left;
  font-family: inherit;
  cursor: pointer;
  transition: all 0.15s;
}

.ksp-item:hover {
  border-color: #1e3a5f;
  background: #f8fafc;
  transform: translateX(2px);
}

.ksp-item-name {
  font-size: 12.5px;
  font-weight: 600;
  color: #0f172a;
  word-break: break-all;
}

.ksp-item-field {
  align-self: flex-start;
  padding: 1px 6px;
  border-radius: 4px;
  background: #eff4fa;
  color: #1e3a5f;
  font-size: 10.5px;
}

.ksp-item-snippet,
.ksp-item-path {
  font-size: 11px;
  color: #64748b;
  word-break: break-all;
}

.ksp-empty {
  padding: 12px;
  text-align: center;
  font-size: 12px;
  color: #94a3b8;
}
</style>
