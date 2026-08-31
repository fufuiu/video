# 开发环境与启动指南

## 1. 环境要求

| 组件 | 要求/说明 |
| --- | --- |
| Python | 推荐 3.12；项目包含 gevent、NumPy、Paddle 相关依赖，3.13 不是当前基线 |
| Node.js/npm | 需要 npm；当前前端使用 Vite 7 和 Electron 构建链 |
| MySQL | 可访问项目数据库，并给应用账号授予目标库权限 |
| Redis | 可访问并允许密码认证；DB 0/1/2 分别用于任务、缓存、Channels |
| FFmpeg/ffprobe | 必须在 PATH 中，视频处理任务会调用它们 |
| GPU | 不是启动必需；无 NVIDIA GPU 时使用 CPU Paddle/PyTorch |

项目当前没有 Docker Compose，也没有本地 Redis/MySQL 自动初始化脚本。远程服务由使用者负责准备。

## 2. Python 环境

从仓库根目录执行：

```powershell
py -3.12 -m venv backend\venv
backend\venv\Scripts\python.exe -m pip install --upgrade pip
backend\venv\Scripts\python.exe -m pip install "setuptools<81"
```

在依赖兼容的环境中可以继续直接安装历史依赖。Windows PowerShell 的命令如下；Linux 将 `Scripts\python.exe` 替换为 `bin/python`：

```powershell
backend\venv\Scripts\python.exe -m pip install -r backend\video\requirements.txt
```

Windows/CPU 环境不要直接执行上面的命令，按下面的替代方案安装。

### Windows 无 NVIDIA GPU 的注意事项

`backend/video/requirements.txt` 是历史依赖快照，其中包含 `paddlepaddle-gpu` 和多个 `nvidia-*` 包。Windows/AMD/CPU 环境直接安装可能失败。当前已验证的思路是：

1. 不安装 `nvidia-*` 包。
2. 使用 `paddlepaddle==3.2.0` 替代 `paddlepaddle-gpu==3.2.0`。
3. 避免 `opencv-python-headless==4.13.0.90` 与当前 NumPy 版本产生冲突。
4. 安装 CPU PyTorch：

   ```powershell
   backend\venv\Scripts\python.exe -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
   ```

5. 项目当前实际会导入、但未完整写入原始 requirements 的运行包还包括：

   ```powershell
   backend\venv\Scripts\python.exe -m pip install transformers timm faster-whisper openai tenacity
   backend\venv\Scripts\python.exe -m pip install django-simple-captcha django-ranged-response
   ```

这套 CPU 依赖还没有被整理成独立的 `requirements-windows-cpu.txt`；如果要给新成员批量复现，应该优先补这个文件，而不是让每个人手工改原始 requirements。

## 3. 配置文件

```powershell
Copy-Item .env.example .env
```

`.env` 必须位于仓库根目录。当前代码支持的核心配置如下：

| 变量 | 用途 |
| --- | --- |
| `MYSQL_HOST/PORT/DATABASE/USER/PASSWORD` | Django MySQL 连接 |
| `REDIS_URL` | Celery 默认 broker/result 和 Redis 基准地址 |
| `REDIS_CACHE_URL` | 可选，Django Cache 地址，默认使用 Redis DB 1 |
| `REDIS_CHANNEL_URL` | 可选，Channels 地址，默认使用 Redis DB 2 |
| `CELERY_BROKER_URL` | 可选，覆盖 Celery broker |
| `CELERY_RESULT_BACKEND` | 可选，覆盖 Celery result backend |
| `DEEPSEEK_API_KEY/BASE_URL/MODEL` | 字幕优化、翻译、摘要等 AI 能力 |
| `DJANGO_SECRET_KEY` | Django 签名和 JWT 相关安全配置 |
| `EMAIL_*` | 可选，邮件验证码和通知的 SMTP 配置 |
| `ALIPAY_*` | 可选，支付宝沙箱支付配置 |

邮件、支付宝和 Django 密钥已经支持从环境变量读取。不要把敏感值复制到文档、聊天或新分支；见 [安全规范](../SECURITY.md)。

## 4. 安装前端

```powershell
Push-Location frontend\video-ui
npm ci
Pop-Location
```

`package-lock.json` 是安装依据。正常开发不要使用 `npm install` 随意改写锁文件；确实变更依赖时，提交 `package.json` 和 `package-lock.json`。

## 5. 数据库初始化

先让数据库管理员确认应用账号能访问目标数据库，再执行：

```powershell
Push-Location backend\video
..\venv\Scripts\python.exe manage.py check
..\venv\Scripts\python.exe manage.py showmigrations
..\venv\Scripts\python.exe manage.py migrate
Pop-Location
```

日常开发只执行 `migrate`。只有模型发生变化时才运行 `makemigrations`，并把生成的迁移文件一起提交。不要直接修改历史迁移文件。

## 6. 启动方式

### 一键启动

从仓库根目录：

```powershell
py -3.12 start_dev.py
```

脚本会依次尝试启动/检查：

1. Redis（配置了远程 `REDIS_URL` 时只做连接检查）
2. Celery Worker
3. Celery Beat
4. Django Uvicorn/ASGI
5. Vite Electron 前端

停止：

```powershell
py -3.12 stop_dev.py
```

### 分别启动

后端：

```powershell
Push-Location backend\video
..\venv\Scripts\python.exe -m uvicorn video.asgi:application --host 127.0.0.1 --port 8000 --ws websockets
Pop-Location
```

Windows Celery Worker：

```powershell
Push-Location backend\video
..\venv\Scripts\celery.exe -A video worker -l info --pool=gevent --concurrency=10 --events
Pop-Location
```

Celery Beat：

```powershell
Push-Location backend\video
..\venv\Scripts\celery.exe -A video beat -l info
Pop-Location
```

浏览器模式前端：

```powershell
Push-Location frontend\video-ui
npm run dev
Pop-Location
```

Electron 模式前端：

```powershell
Push-Location frontend\video-ui
npm run electron:dev
Pop-Location
```

前端 Vite 将 `/api` 代理到 `http://localhost:8000`。默认端口为后端 `8000`、前端 `5173`；被占用时先运行 `py -3.12 stop_dev.py` 或手动释放端口。

## 7. 验证清单

```powershell
# 后端静态检查
Push-Location backend\video
..\venv\Scripts\python.exe manage.py check
Pop-Location

# 前端构建
Push-Location frontend\video-ui
npm run build
Pop-Location
```

当前前端构建会在搜索页的重复 `response` 声明处失败；修复前不要把构建标记为通过。连接验证应分别执行 MySQL `SELECT 1` 和 Redis `PING`，不要用“端口可连接”代替“账号权限正确”。

## 8. 日志位置

后端日志目录：`backend/video/logs/`。开发脚本维护的 PID 文件是仓库根目录的 `.dev_pids.json`，它属于运行时文件，不应提交。
