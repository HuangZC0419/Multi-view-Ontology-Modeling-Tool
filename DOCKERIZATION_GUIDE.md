# Docker 打包与离线部署规范

> 适用于：Python + FastAPI 后端 + Vue/React 前端 的 Docker 容器化项目
> 最后更新：2026-06-08
> 基于项目 `Multi-view-Ontology-Modeling-Tool` 实际打包经验总结

---

## 一、项目文件结构

```
项目根目录/
├── Dockerfile                     # 镜像构建定义（必须）
├── docker-compose.yml             # 在线部署（含 build，首次构建用）
├── docker-compose.offline.yml     # 离线部署（不含 build，引用本地镜像）
├── .dockerignore                  # 排除不打包的文件（必须）
├── .gitignore                     # 排除 *.tar 等大文件（必须）
├── backend/
│   ├── requirements.txt           # Python 依赖清单（必须锁定版本号）
│   ├── app/                       # 后端代码
│   ├── projects/                  # 持久化数据目录
│   ├── uploads/                   # 上传文件目录
│   └── users.xlsx                 # 认证数据
├── frontend/
│   ├── package.json               # npm 依赖
│   ├── package-lock.json          # 锁定版本（必须）
│   └── src/                       # 前端源码
├── <镜像名>.tar                   # 离线镜像包（不提交 Git）
└── DOCKERIZATION_GUIDE.md         # 本文档
```

---

## 二、Dockerfile 编写规范

### 2.1 基础镜像选择

| 场景 | 推荐镜像 | 说明 |
|------|---------|------|
| Python 3.10+ | `python:3.10-slim-bookworm` | Debian 12，兼容性好 |
| Python 3.9 及以下 | 不建议 | 不支持 `str \| None` 等新语法 |
| Debian 最新版 | 谨慎使用 | Trixie 安全策略过严，老库可能不兼容 |

**教训**：不要用 `python:3.9-slim`（默认最新 Debian Trixie），`onnxruntime` 会因 execstack 报错。

### 2.2 多阶段构建模板

```dockerfile
# ===== 阶段 1：构建前端 =====
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci                         # 用 ci 不用 install，确保版本锁定

COPY frontend/ ./
RUN npm run build

# ===== 阶段 2：运行环境 =====
FROM python:3.10-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
```

### 2.3 国内镜像源加速（构建时必须）

```dockerfile
# APT：Debian 源换成中科大镜像
RUN sed -i 's/deb.debian.org/mirrors.ustc.edu.cn/g' /etc/apt/sources.list.d/debian.sources 2>/dev/null; \
    sed -i 's/deb.debian.org/mirrors.ustc.edu.cn/g' /etc/apt/sources.list 2>/dev/null; \
    apt-get update \
    && apt-get install -y --no-install-recommends <系统依赖包> \
    && rm -rf /var/lib/apt/lists/*

# pip：用清华源
RUN pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple \
    && pip install -r /app/backend/requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 2.4 系统依赖排查

| Python 包 | 需要的系统库 | apt 包名 |
|-----------|-------------|---------|
| `opencv-python-headless` | `libGL.so.1` | `libgl1` |
| `onnxruntime` | `libgomp.so.1` | `libgomp1` |
| `rapidocr_onnxruntime` | GLib | `libglib2.0-0` |

**排查方法**：容器启动失败时执行 `docker logs <容器名>`，若看到 `ImportError: libXXX.so: cannot open`，在 Dockerfile 中添加对应的 apt 包。

### 2.5 完整 Dockerfile 模板

```dockerfile
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.10-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 系统依赖（使用国内源）
RUN sed -i 's/deb.debian.org/mirrors.ustc.edu.cn/g' /etc/apt/sources.list.d/debian.sources 2>/dev/null; \
    sed -i 's/deb.debian.org/mirrors.ustc.edu.cn/g' /etc/apt/sources.list 2>/dev/null; \
    apt-get update \
    && apt-get install -y --no-install-recommends \
        libgomp1 libglib2.0-0 libgl1 \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖（使用国内源）
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple \
    && pip install -r /app/backend/requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 代码和静态文件
COPY backend/ /app/backend/
COPY test.png /app/test.png
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

# 运行时目录
RUN mkdir -p /app/backend/projects /app/backend/uploads

EXPOSE 8000
WORKDIR /app/backend
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 三、docker-compose 配置

### 3.1 在线版（首次构建用）

**文件**：`docker-compose.yml`

```yaml
services:
  ontology-tool:
    build:
      context: .
      dockerfile: Dockerfile
    image: <项目名>:latest
    container_name: <容器名>
    ports:
      - "8000:8000"
    volumes:
      - ./backend/projects:/app/backend/projects
      - ./backend/uploads:/app/backend/uploads
      - ./backend/users.xlsx:/app/backend/users.xlsx
    restart: unless-stopped
```

### 3.2 离线版（目标机器部署用）

**文件**：`docker-compose.offline.yml`

```yaml
services:
  ontology-tool:
    image: <项目名>:latest        # 直接用本地镜像，无 build 段
    container_name: <容器名>
    ports:
      - "8000:8000"
    volumes:
      - ./backend/projects:/app/backend/projects
      - ./backend/uploads:/app/backend/uploads
      - ./backend/users.xlsx:/app/backend/users.xlsx
    restart: unless-stopped
```

> **关键区别**：离线版去掉了 `build:` 配置，直接引用 `image:`，避免在没有网络的机器上尝试重新构建。

---

## 四、.dockerignore（必须）

```dockerignore
.git
node_modules
frontend/node_modules
frontend/dist
backend/__pycache__
backend/.venv
backend/uploads
*.pyc
*.log
Dockerfile
docker-compose.yml
docker-compose.offline.yml
```

---

## 五、构建与打包流程

### 第一步：首次构建（联网机器）

```powershell
# 在项目根目录执行
docker compose up --build -d
```

### 第二步：验证构建结果

```powershell
# 确认状态为 Up
docker ps

# 检查日志无报错
docker logs <容器名> --tail 20

# 测试 API
curl http://localhost:8000/api/projects

# 测试前端
curl -o /dev/null -w "%{http_code}" http://localhost:8000/

# 测试 OCR（如有）
docker exec <容器名> python -c "from rapidocr_onnxruntime import RapidOCR; RapidOCR(); print('OK')"
```

### 第三步：导出镜像

```powershell
docker save <项目名>:latest -o <项目名>.tar
```

### 第四步：交付清单

拷贝到离线目标机器：

| 文件 | 必须 | 说明 |
|------|:--:|------|
| `<项目名>.tar` | ✅ | Docker 镜像（约 300MB） |
| `docker-compose.offline.yml` | ✅ | 离线部署配置 |
| `backend/users.xlsx` | ✅ | 用户认证数据 |
| `backend/projects/` | ✅ | 项目数据目录 |
| `backend/uploads/` | ✅ | 上传文件目录 |
| `README.md` | 可选 | 使用说明 |

---

## 六、离线部署（目标机器）

### 前提条件

- 安装 Docker Desktop（Windows）或 Docker Engine（Linux）
- **不需要**安装 Python、Node.js、pip 等任何开发环境

### 部署步骤

```powershell
# 1. 导入镜像（只需一次）
docker load -i <项目名>.tar

# 2. 启动服务
docker compose -f docker-compose.offline.yml up -d

# 3. 验证
curl http://localhost:8000/
```

### 常用管理命令

```powershell
# 停止
docker compose -f docker-compose.offline.yml down

# 重启
docker compose -f docker-compose.offline.yml restart

# 查看日志
docker logs <容器名>

# 进入容器调试
docker exec -it <容器名> /bin/bash
```

---

## 七、常见问题速查

### Q1：`ImportError: libGL.so.1: cannot open shared object file`

**原因**：opencv-python-headless 仍需要 OpenGL 运行时

**解决**：Dockerfile 中添加 `libgl1` 到 apt install

### Q2：`ImportError: cannot enable executable stack`

**原因**：Debian Trixie 安全策略过严，onnxruntime 旧版本不兼容

**解决**：使用 `python:3.10-slim-bookworm`（Debian 12）替代默认 slim

### Q3：`TypeError: Unable to evaluate type annotation 'str | None'`

**原因**：代码用了 Python 3.10+ 的联合类型语法，但镜像用 3.9

**解决**：统一使用 `python:3.10-slim-bookworm`

### Q4：`E: Unable to locate package execstack`

**原因**：Bookworm 没有 execstack 包

**解决**：不需要 execstack，Bookworm 的 onnxruntime 直接可用

### Q5：apt-get 下载极慢

**原因**：国内访问 deb.debian.org 慢

**解决**：Dockerfile 第一行 sed 替换为中科大源（见 2.3 节）

### Q6：pip install 下载极慢

**原因**：国内访问 pypi.org 慢

**解决**：pip install 加 `-i https://pypi.tuna.tsinghua.edu.cn/simple`

### Q7：`docker compose up --build` 在离线机器上报错

**原因**：离线环境不能拉取基础镜像

**解决**：用 `docker-compose.offline.yml`（不含 build），配合 `docker load` 导入的本地镜像

---

## 八、Python 版本对齐检查清单

在打包前确认以下内容一致：

| 检查项 | 要求 |
|--------|------|
| Dockerfile 基础镜像 | `python:3.10-slim-bookworm` |
| 代码语法 | 确认无 3.10+ 语法（或统一升到 3.10） |
| requirements.txt | 所有包支持 Python 3.10 |
| 本地开发环境 | 建议与 Docker 保持一致 |

---

## 九、Git 提交检查清单

提交前确认：

- [ ] `.gitignore` 包含 `*.tar`（排除大型镜像文件）
- [ ] `.gitignore` 包含 `.superpowers/`（排除会话数据）
- [ ] `docker-compose.offline.yml` 已添加
- [ ] `Dockerfile` 已移除 `# syntax=docker/dockerfile:1`（国内无法拉取）
- [ ] `requirements.txt` 所有包已锁定版本号
- [ ] 无 `build/`、`dist/`、`OCR-Benti.spec` 等 PyInstaller 残留
- [ ] 无 `__pycache__/`、`.venv/` 等本地环境残留

---

## 十、版本记录

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-06-08 | v1.0 | 初始版本，基于 Multi-view-Ontology-Modeling-Tool 打包经验 |
