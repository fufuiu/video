# 云端 AI 配置与启用手册

本项目的 AI 主路径使用两个平台：DeepSeek 负责文本生成，阿里云负责临时对象存储、语音识别、OCR 和视频内容审核。基础上传、转码、人工编辑、发布和播放不依赖这些云服务；未配置时相关 AI 能力会明确失败，但 Django 仍可启动。

## 1. 能力与平台对应关系

| 项目能力 | Provider | 云产品 | 是否需要 OSS |
| --- | --- | --- | --- |
| 摘要、标签、字幕文本处理 | `deepseek` | DeepSeek API | 否 |
| 长音视频转写 | `aliyun` | 阿里云百炼 Fun-ASR | 是 |
| 硬字幕抽帧识别 | `aliyun` | 阿里云 OCR 通用文字识别 | 否 |
| 视频内容审核 | `aliyun` | 阿里云内容安全视频审核增强版 | 是 |
| 自动化测试/本地联调 | `mock` | 无外部服务 | 否 |

OSS 不是永久媒体库，而是云端 AI 的私有临时文件交换层。业务原视频当前仍由 Django
`FileSystemStorage` 保存到 `backend/video/media/videos/uploads/`；如果要把原视频永久保存到
OSS，需要另行接入 Django 的 OSS 默认存储、历史文件迁移和访问 URL 策略。

## 2. 账号与控制台准备

### 2.1 DeepSeek

1. 在 DeepSeek 开放平台创建 API Key，并设置可接受的余额告警或用量预算。
2. 只把 Key 写入部署环境变量 `DEEPSEEK_API_KEY`，不要写入 Git、日志或前端。
3. 保留默认 Base URL；模型名通过 `DEEPSEEK_MODEL` 配置，切换模型不改业务代码。

### 2.2 阿里云

1. 开通百炼、文字识别 OCR、内容安全和 OSS。
2. 创建专用 RAM 用户或运行角色，按最小权限授权；不要使用主账号长期 AccessKey。
3. 为百炼创建 API Key，并取得工作空间专属域名，分别配置 `DASHSCOPE_API_KEY` 和 `DASHSCOPE_BASE_URL`。
4. 创建私有 OSS Bucket。启用生命周期规则，自动删除前缀 `ai-temp/` 下超过 1 天的对象。
5. OSS 不需要开放公共读权限。应用生成短期签名 URL 给 ASR/视频审核拉取，成功后立即删除，异常时由生命周期规则兜底。
6. OCR 默认使用杭州公网接入点，内容安全默认使用上海接入点；如果账号开通区域不同，以控制台和官方接入点为准修改环境变量。

建议把开发、测试、生产分成不同 RAM 身份和 Bucket，并分别设置费用告警。严禁多人共享主账号密钥。

## 3. 安装云端可选依赖

基础开发环境不必安装云 SDK。只有运行真实云端任务的 Worker 需要执行：

```powershell
Push-Location backend\video
..\venv\Scripts\python.exe -m pip install -r requirements-cloud.txt
Pop-Location
```

`requirements-cloud.txt` 当前包含 OSS、OCR 和内容安全 SDK。Fun-ASR 使用现有 HTTP 客户端，DeepSeek 使用现有 OpenAI 兼容客户端。

## 4. 配置模式

### 4.1 完全离线 Mock

```dotenv
AI_TEXT_PROVIDER=mock
AI_ASR_PROVIDER=mock
AI_OCR_PROVIDER=mock
AI_MODERATION_PROVIDER=mock
AI_STORAGE_PROVIDER=local
```

Mock 只用于测试和界面联调，不能把 Mock 结果当成真实审核结论。

### 4.2 仅启用 DeepSeek

```dotenv
AI_TEXT_PROVIDER=deepseek
DEEPSEEK_API_KEY=填写部署环境中的密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
```

其他 Provider 保持 `disabled`，不影响摘要之外的基础业务。

### 4.3 启用完整阿里云能力

```dotenv
AI_ASR_PROVIDER=aliyun
AI_OCR_PROVIDER=aliyun
AI_MODERATION_PROVIDER=aliyun
AI_STORAGE_PROVIDER=aliyun

DASHSCOPE_API_KEY=填写部署环境中的百炼密钥
DASHSCOPE_BASE_URL=https://填写工作空间专属域名
DASHSCOPE_ASR_MODEL=fun-asr

ALIBABA_CLOUD_ACCESS_KEY_ID=填写RAM访问密钥ID
ALIBABA_CLOUD_ACCESS_KEY_SECRET=填写RAM访问密钥Secret
ALIYUN_OSS_ENDPOINT=oss-cn-beijing.aliyuncs.com
ALIYUN_OSS_BUCKET=填写私有Bucket名称
```

如果使用 STS，再配置 `ALIBABA_CLOUD_SECURITY_TOKEN`。生产环境更推荐实例角色或定期轮换的短期凭据。

## 5. 配置体检与启用顺序

配置体检只实例化 Provider，不发送任何外部 API 请求：

```powershell
Push-Location backend\video
..\venv\Scripts\python.exe manage.py check_ai_config
Pop-Location
```

推荐按以下顺序逐项启用，每一步都使用一条小样本真实请求验收：

1. 全 Mock 回归；
2. DeepSeek 摘要和标签；
3. OSS 上传、签名 URL、删除和 1 天生命周期；
4. Fun-ASR 短视频转写；
5. OCR 单帧与硬字幕视频；
6. 内容安全视频审核；
7. 再跑登录、上传、转码、AI、人工确认、发布、播放完整链路。

真实验收必须记录供应商 request ID、Celery task ID、video ID、耗时和账单用量，但不能记录密钥、完整签名 URL或原始连接串。

## 6. 成本与故障保护

- 文本输入默认最多 `50000` 字符；OCR 默认抽取 `8` 帧，代码上限为 `20` 帧。
- 单个云端视频输入默认最多 `2147483648` 字节，可按套餐限制调低。
- ASR 和审核都有轮询间隔与总超时，Provider 有请求超时和有限重试。
- 临时 URL 默认 6 小时，OSS 临时对象建议 24 小时生命周期兜底。
- 生产环境不会在供应商故障时自动切到 Mock，避免把假结果写入正式数据；任务会记录安全错误并允许管理员按白名单重试。
- AI 审核失败不能自动判定“安全”。应保持未完成/待人工处理状态，由管理员决定是否重试或人工审核。

相关环境变量及默认值见仓库根目录 `.env.example`。

## 7. 当前验收边界

截至 2026-09-01，当前开发环境已经完成真实小样本验收：

| 能力 | 真实验收结果 | 当前结论 |
| --- | --- | --- |
| DeepSeek 摘要/标签 | API 返回成功，摘要和标签已写入测试数据库 | 可用 |
| OSS 临时交换 | 上传、签名读取、删除均成功 | 可用 |
| 百炼 Fun-ASR | 通过 Redis/Celery 完整异步链路生成 43 条字幕并写回数据库 | 可用 |
| 阿里云 OCR | 请求已到达服务端，但账号返回 `ocrServiceNotOpen` | 需在控制台开通 OCR |
| 阿里云内容安全 | 请求已到达服务端，但账号返回 `No permissions` | 需开通服务或补 RAM 权限 |

本机队列设置为独立的 `CELERY_TASK_DEFAULT_QUEUE`，避免共享 Redis 上的其他旧 Worker 抢走任务。
仍未验证 OSS 的 24 小时生命周期规则、生产配额/余额和大样本识别质量；这些属于上线前验收项，
不影响当前已经通过的字幕生成与文本 AI 开发链路。
