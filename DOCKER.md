# Docker 部署说明

本项目已整理为单容器部署：Docker 构建阶段会先编译 Vue 前端，再由 FastAPI 在 `8000` 端口同时提供 API 和前端页面。

## 启动

```bash
docker compose up --build -d
```

启动后访问：

- 应用页面：http://localhost:8000
- API 文档：http://localhost:8000/docs

## 停止

```bash
docker compose down
```

## 数据持久化

`docker-compose.yml` 已挂载这些本地路径：

- `backend/projects`：项目图谱数据
- `backend/uploads`：上传的 Excel/CSV 文件
- `backend/users.xlsx`：登录用户表

如果需要重新构建镜像：

```bash
docker compose build --no-cache
```
