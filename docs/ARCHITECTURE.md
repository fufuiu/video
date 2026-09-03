# 系统架构说明

## 1. 总体结构

```text
Vue/Vite 或 Electron
        │  /api 代理、JWT、WebSocket
        ▼
Django ASGI/Uvicorn + Django REST Framework
        ├── MySQL：业务数据、用户、视频、字幕、任务状态
        ├── Redis DB 0：Celery broker/result
        ├── Redis DB 1：Django Cache
        ├── Redis DB 2：Channels/WebSocket
        ├── Celery Worker：视频、OCR、语音、审核、字幕处理
        └── Celery Beat：定时清理、预约发布、系统监控
                │
                ├── FFmpeg/ffprobe：视频媒体处理
                ├── 阿里云百炼 Fun-ASR：语音转字幕
                ├── 阿里云 OCR：可选的画面硬字幕检测
                ├── 阿里云内容安全：视频审核
                ├── 阿里云 OSS：AI 临时文件交换
                └── DeepSeek：字幕优化、翻译、摘要、标签
```

### 1.1 当前媒体存储边界

- 业务原视频、转码结果、封面和审核截图当前由 Django `FileSystemStorage` 保存在 `backend/video/media/`。
- OSS 的 `ai-temp/` 只用于 ASR 和视频审核的临时交换，任务结束立即尝试删除，并由 1 天生命周期规则兜底；它不是业务媒体库。
- 单机开发和比赛演示可以继续使用本地媒体目录，但必须把该目录纳入备份，部署时也必须使用持久磁盘，不能依赖容器临时文件系统。
- 正式多用户部署或多实例 Worker 应把业务媒体迁移到私有 OSS：数据库保存对象键，应用按权限生成短期访问地址；`media/` 永久对象与 `ai-temp/` 临时对象必须使用不同前缀和生命周期规则。
- 当前已有本地 FFmpeg 转码链路，近期接入 OSS 即可；只有需要大规模 CDN 分发、云转码、DRM 或完整媒资管理时，再评估阿里云视频点播 VOD。

## 2. 后端模块

| 模块 | 位置 | 职责 |
| --- | --- | --- |
| 项目配置 | `backend/video/video/` | Django settings、URL、ASGI、Celery |
| 认证 | `backend/video/authentication/` | 注册、登录、注销、验证码 |
| 用户与后台 | `backend/video/users/` | 用户资料、权限、角色、通知、统计、系统管理 |
| 视频 | `backend/video/videos/` | 视频 CRUD、分片上传、转码、字幕、审核、评论、举报 |
| AI | `backend/video/ai_service/` | 内容审核、OCR、语音、摘要和字幕 AI |
| 公共能力 | `backend/video/core/` | WebSocket、权限、日志、中间件、分页 |

## 3. 请求和任务流

### 同步 API

1. 前端通过 `/api` 发起请求。
2. Vite 开发代理将请求转发给 `127.0.0.1:8000`。
3. Django URL 将请求分发给各应用的 View/ViewSet。
4. Serializer 负责输入校验和输出格式化。
5. 需要持久化的数据通过 Django ORM 写入 MySQL。

### 异步视频/AI 任务

1. API 接收上传或处理请求，并创建/更新业务记录。
2. 长任务提交到 Celery；任务消息进入 Redis DB 0。
3. Worker 执行 FFmpeg，或通过 Provider 调用 Fun-ASR、可选 OCR、内容安全和 DeepSeek。
4. 任务状态和结果写回 MySQL，必要时写入媒体目录。
5. 前端通过状态接口或 WebSocket 通知获得进度。

长耗时工作不要在 Django 请求线程中直接执行；新增任务应放在对应应用的 `tasks.py`，并为失败、重试和重复提交定义清楚行为。

## 4. 认证和实时通知

- REST API 使用 JWT；入口是 `/api/token/` 和 `/api/token/refresh/`，业务登录接口位于 `/api/auth/`。
- WebSocket 路径为 `/ws/notifications/`，由 `JWTAuthMiddleware` 处理认证。
- 前端不应在组件中重复实现 token 存储和刷新逻辑，应复用现有 store/API 工具。

## 5. Redis 数据库约定

默认约定如下：

| Redis DB | 用途 | 代码入口 |
| --- | --- | --- |
| 0 | Celery broker/result | `CELERY_BROKER_URL`、`CELERY_RESULT_BACKEND` |
| 1 | Django Cache | `REDIS_CACHE_URL` |
| 2 | Channels | `REDIS_CHANNEL_URL` |

如果部署环境不能使用多个逻辑 DB，应显式配置三个 URL，避免不同组件互相清理数据。

## 6. 定时任务

定时任务在 `backend/video/video/celery.py` 注册，目前包括：

- 每日清理已删除视频
- 每分钟发布预约视频
- 每 10 秒采集系统监控数据

修改任务名称、队列或调度周期时，需要同步检查旧 Worker/Beat 是否仍在运行，避免同一任务被重复消费。

## 7. 配置和边界

- 本地敏感配置通过项目根目录 `.env` 注入，不能提交真实值。
- 媒体文件和模型文件属于运行时资源，不应进入 Git。
- 生产环境不能沿用开发用的 `DEBUG`、默认密钥、开放 CORS 或公开支付回调配置。
- AI 模型调用失败应有明确的用户可见状态和日志上下文，不能只返回“任务成功”。
