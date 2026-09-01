# 视频平台

这是一个面向视频内容处理的全栈项目，包含用户与权限、视频上传/转码、字幕处理、AI 内容分析和管理端能力。后端使用 Django/DRF，异步任务使用 Celery，Redis 同时承担消息代理、缓存和 WebSocket channel layer；前端使用 Vue/Vite，并保留 Electron 启动模式。

## 先看这里

| 目的 | 文档 |
| --- | --- |
| 第一次配置和启动 | [开发指南](docs/DEVELOPMENT.md) |
| 理解服务和任务流 | [架构说明](docs/ARCHITECTURE.md) |
| 调接口和看鉴权方式 | [API 说明](docs/API.md) |
| 团队提交、分支和检查规范 | [贡献规范](CONTRIBUTING.md) |
| 启动报错排查 | [排错手册](docs/TROUBLESHOOTING.md) |
| 配置 DeepSeek、阿里云 AI 和 OSS | [云端 AI 配置手册](docs/AI_CLOUD_CONFIGURATION.md) |
| 密钥和敏感配置要求 | [安全规范](SECURITY.md) |

`markdown/` 目录是已有的 Django/Redis 学习笔记，不是本项目的唯一操作手册。新成员应先阅读本文和 `docs/DEVELOPMENT.md`。

## 目录结构

```text
.
├── backend/video/              # Django 项目
│   ├── video/                  # 项目配置、ASGI、Celery
│   ├── authentication/         # 注册、登录、验证码
│   ├── users/                  # 用户、权限、后台管理
│   ├── videos/                 # 视频、上传、字幕、审核、任务
│   └── ai_service/             # OCR、语音、审核、摘要和字幕 AI
├── frontend/video-ui/          # Vue + Vite + Electron 前端
├── docs/                       # 团队开发文档
├── markdown/                   # 个人学习笔记
├── start_dev.py                # 启动 Redis/Worker/Beat/后端/前端
└── stop_dev.py                 # 停止开发服务
```

## 快速开始

以下命令从仓库根目录执行。完整的 Windows/CPU 依赖说明见 [开发指南](docs/DEVELOPMENT.md)。

```powershell
# 1. 创建 Python 3.12 虚拟环境
py -3.12 -m venv backend\venv

# 2. 安装后端依赖（依赖兼容环境）
backend\venv\Scripts\python.exe -m pip install -r backend\video\requirements.txt

# 3. 创建本地配置文件，并填写自己的数据库、Redis 和第三方服务配置
Copy-Item .env.example .env

# 4. 安装前端依赖
Push-Location frontend\video-ui
npm ci
Pop-Location

# 5. 检查 Django 配置
Push-Location backend\video
..\venv\Scripts\python.exe manage.py check
Pop-Location

# 6. 数据库权限准备好后执行迁移
Push-Location backend\video
..\venv\Scripts\python.exe manage.py migrate
Pop-Location

# 7. 启动全部开发服务
py -3.12 start_dev.py
```

如果你在 Windows、AMD 或纯 CPU 环境开发，不要直接执行第 2 步；原始依赖包含 GPU 版 Paddle。先阅读 [开发指南中的 CPU 说明](docs/DEVELOPMENT.md#windows-无-nvidia-gpu-的注意事项)。

默认地址：

- 后端：`http://127.0.0.1:8000`
- 前端 Vite：`http://127.0.0.1:5173`
- Swagger：`http://127.0.0.1:8000/swagger/`
- ReDoc：`http://127.0.0.1:8000/redoc/`
- WebSocket：`ws://127.0.0.1:8000/ws/notifications/`

停止服务：

```powershell
py -3.12 stop_dev.py
```

## 当前已知状态

以下是截至 2026-09-01 已记录并验证过的状态，不代表所有业务流程已经验收：

- Python 3.12 虚拟环境已创建，Django `manage.py check` 通过。
- Redis 远程认证连接曾验证通过；在新的团队目标环境中仍需重新执行认证连接和 `PING`。
- 业务数据库连接检查和迁移计划检查已通过；全量 Django 测试仍因当前账号不能创建 `test_video_dev` 测试库而受到 MySQL 1044 权限错误阻塞。
- `npm ci`、前端 API 错误测试和 `npm run build` 已通过；构建仅保留大 chunk 性能提示。
- AI 运行主路径已切换为 DeepSeek/阿里云 Provider；原始 requirements 和旧本地模型代码暂作迁移回退保留，待真实云端验收后再删除重依赖。
- 云端 AI 已完成真实小样本验收：DeepSeek、OSS 临时交换和百炼 Fun-ASR 可用，异步链路已生成并写回 43 条字幕；阿里云 OCR 尚未开通，内容安全尚缺服务开通或 RAM 权限。OSS 当前不保存业务原视频，只保存 AI 任务的临时对象。
- 登录、上传、转码、审核、发布和播放的完整主链路尚未完成端到端验收，不能用单项检查通过代替整体可交付结论。

## 贡献前必读

不要提交 `.env`、数据库/Redis 密码、API Key、支付私钥、`backend/venv`、`node_modules`、日志、媒体文件或构建产物。详见 [安全规范](SECURITY.md) 和 [贡献规范](CONTRIBUTING.md)。
