# API 使用说明

## 1. 地址和文档入口

本地开发默认地址：`http://127.0.0.1:8000`。

- Swagger UI：`/swagger/`
- ReDoc：`/redoc/`
- OpenAPI JSON/YAML：`/swagger.json`、`/swagger.yaml`
- API 前缀：`/api/`

Swagger/ReDoc 由代码自动生成，接口参数和响应发生变化时，以运行中的 Swagger 为准；本文只维护模块边界和调用约定。

## 运维探针

- 存活检查：`GET /api/health/live/`，仅确认 Django 进程可以响应。
- 就绪检查：`GET /api/health/ready/`，同时检查 MySQL 和 Redis；依赖不可用时返回 HTTP 503。

探针响应不会返回连接地址、密码或其他敏感配置，可用于启动脚本、反向代理和部署平台的健康检查。

## 2. 鉴权

登录后使用 JWT：

```http
Authorization: Bearer <access-token>
```

主要入口：

| 能力 | 路径 |
| --- | --- |
| 获取 Token | `POST /api/token/` |
| 刷新 Token | `POST /api/token/refresh/` |
| 注册 | `POST /api/auth/register/` |
| 登录 | `POST /api/auth/login/` |
| 注销 | `POST /api/auth/logout/` |
| 验证码 | `GET /api/auth/captcha/` |

`/api/captcha/` 还挂载了验证码库的资源路由，具体图片/资源路径以 Swagger 为准。

不要在日志、截图、Issue 或提交记录中记录 access token、refresh token 或密码。

## 3. 接口分组

### 用户与权限：`/api/users/`

包括个人资料、通知、评论、用户管理、角色、权限、登录设备、系统设置、统计、VIP 订单等。管理接口需要对应管理员权限，不能只依赖前端隐藏按钮。

### 视频：`/api/videos/`

包括：

- 分类、标签、视频、评论、收藏、观看记录、弹幕
- 分片上传：`upload/check/`、`upload/chunk/`、`upload/merge/`
- 视频审核、举报和回收站
- 视频转码和缩略图
- 字幕读取、更新、生成、翻译和优化

### AI：`/api/ai/`

包括：

- `moderation`：内容审核
- `recognition`：识别/OCR 等能力
- `summary`：视频摘要、标签等能力
- `subtitle`：字幕生成和处理

AI 和媒体处理通常是异步任务。提交接口返回任务相关信息后，使用对应的 `task-status`、`detection-status` 或字幕状态接口轮询；具体字段以 Swagger 和 serializer 为准。

### 管理端：`/api/admin/`

包括待审核视频、已审核视频、通过、驳回以及举报处理。管理接口的权限和状态变化应在后端校验。

## 4. WebSocket

通知连接地址：

```text
ws://127.0.0.1:8000/ws/notifications/?token=<access-token>
```

连接失败时依次检查：后端是否以 ASGI/Uvicorn 启动、Redis DB 2 是否可认证、token 是否有效、浏览器 Origin 是否在允许范围内。

## 5. 调试原则

- 先打开 Swagger 确认实际请求方法、路径、必填字段和权限。
- 上传接口使用 `multipart/form-data`；不要把文件内容放在 JSON 中。
- 分页、错误码和响应字段以对应 Serializer/分页类为准。
- 新增接口必须补权限校验、输入校验、错误路径和至少一个测试用例。
- 改动接口契约时，同时更新前端 API 封装和本文档的接口分组。
