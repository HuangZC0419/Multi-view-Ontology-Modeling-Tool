# Git 协作流程规范

## 原则

**提 PR 之前，先把最新的 main 拉到自己的分支里合并，有冲突让 AI 解决，再推上去。**

---

## 每次改代码的标准流程（6 步）

```bash
# 1. 切到自己的功能分支（首次创建分支用 -b，之后不用）
git checkout -b feature/你的功能名

# 2. 写代码...

# 3. 把自己的改动暂存
git add .

# 4. 提交到本地仓库
git commit -m "描述你改了什么"

# 5. 拉取最新的 main 并合并到自己的分支
git checkout main
git pull origin main
git checkout feature/你的功能名
git merge main

# 6. 推送到 GitHub，去网页上提 PR
#     如果 merge 时出现冲突，把冲突文件交给 AI 工具（如 Claude Code、Cursor、Copilot 等）处理：
#         "帮我解决当前分支和 main 的合并冲突"
#     AI 处理完后，确认无误，再 push
git push origin feature/你的功能名
```

> ⚠️ **第 3 步必须在第 5 步之前做**，否则 Git 会报错不让切分支。

---

## 冲突怎么处理（交给 AI）

`git merge main` 如果报冲突，你会看到类似提示：

```
Auto-merging 某个文件
CONFLICT (content): Merge conflict in xxx.py
Automatic merge failed; fix conflicts and then commit the result.
```

**不用慌，丢给 AI 就行：**

1. 打开 AI 编程工具（Claude Code / Cursor / GitHub Copilot 等）
2. 对 AI 说：**"帮我解决当前分支和 main 的合并冲突"**
3. AI 会读取冲突标记 `<<<<<<<` `=======` `>>>>>>>`，自动判断两边各自的意图，合并出合理的代码
4. 你检查一下结果，没问题就：

```bash
git add .
git commit -m "AI 协助解决与 main 的合并冲突"
```

---

## 一张图记住

```
  git checkout -b 新分支        ← 第1步：开草稿
         ↓
  写代码 → add → commit          ← 第2~4步：保存
         ↓
  git merge main（先拉最新）    ← 第5步：同步
         ↓
  有冲突？→ 丢给 AI → commit     ← AI 处理
         ↓
  git push → 提 PR               ← 第6步：提交审核
```

---

## 千万不要做的事

| 不要 | 原因 |
|------|------|
| 直接在 main 分支上改代码 | 所有人的代码会搅在一起，回不了头 |
| 没 commit 就切分支或 merge | Git 会报错 |
| 冲突没解决就 push | PR 上会一团乱，同事看了想打人 |
| `git push --force` | 会覆盖别人的代码，除非你确定知道在干什么 |

---

## 口号

**存自己 → 拉最新 → 合进来 → 有冲突丢给 AI → 推上去 → 提 PR**
