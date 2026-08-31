# 常见问题与排错手册

## 1. 先收集基本信息

```powershell
py -0p
node --version
npm --version
ffmpeg -version
ffprobe -version
git status -sb
```

确认命令是在仓库根目录执行，后端命令是在 `backend/video` 执行；优先使用 `backend\venv\Scripts\python.exe`，不要混用系统 Python。

## 2. Python 依赖安装失败

### `paddlepaddle-gpu` 找不到匹配版本

这是 Windows/无 NVIDIA GPU 的预期兼容性问题。参考 [开发指南](DEVELOPMENT.md) 使用 CPU Paddle，并跳过 `nvidia-*` 包。不要把个人机器的替换结果直接覆盖团队依赖文件，先单独整理 CPU requirements。

### `gevent`、NumPy 或 Cython 编译失败

优先确认使用 Python 3.12，而不是 3.13：

```powershell
backend\venv\Scripts\python.exe --version
```

如果虚拟环境创建时选错版本，重新创建：

```powershell
py -3.12 -m venv --clear backend\venv
```

### `pkg_resources is deprecated`

这是 `drf_yasg` 与新版 setuptools 的兼容性警告。当前开发环境使用 `setuptools<81`；它不是 Django 代码错误。

### `ModuleNotFoundError`

当前代码实际导入的部分包未完整出现在原始 requirements 中。根据错误补包前先确认是否应该补入正式依赖文件；当前已知启动链需要 `openai`、`tenacity`、`torch`、`torchvision`、`transformers`、`timm`、`faster-whisper` 和验证码相关包。

## 3. MySQL 报错

### `1044 Access denied ... to database`

这通常表示网络和 MySQL 握手已经通过，但应用账号没有目标数据库权限。由数据库管理员在服务器上用管理员账号执行类似授权（替换为实际占位符，不要把密码写入仓库）：

```sql
CREATE DATABASE IF NOT EXISTS `your_database` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'your_app_user'@'%' IDENTIFIED BY 'use-a-secret-outside-git';
GRANT ALL PRIVILEGES ON `your_database`.* TO 'your_app_user'@'%';
FLUSH PRIVILEGES;
```

然后重新验证：

```powershell
Push-Location backend\video
..\venv\Scripts\python.exe manage.py check
..\venv\Scripts\python.exe manage.py migrate --plan
Pop-Location
```

### 不要只检查端口

3306 可连接不代表账号、数据库名和权限正确。至少执行一次只读 `SELECT 1`；迁移前还要确认目标库允许 DDL。

## 4. Redis 报错

确认根目录 `.env` 中有正确的 `REDIS_URL`，格式示例：

```text
redis://:password@host:6379/0
```

Redis 连接验证应包含认证，而不只是 TCP 端口检查。若密码包含 URL 特殊字符，先进行 URL 编码。项目默认使用 DB 0/1/2，见 [架构说明](ARCHITECTURE.md)。

## 5. 前端构建失败

当前已知错误：

```text
src/views/search/index.vue
Identifier 'response' has already been declared
```

搜索函数中存在两次 `const response` 声明。修复时先确认究竟使用 `/videos/videos/` 还是 `/videos/search/`，不要只删除一行而改变搜索业务语义；修复后重新执行 `npm run build`。

## 6. 一键启动失败

- 端口 `8000` 或 `5173` 被占用：先执行 `py -3.12 stop_dev.py`，再检查残留进程。
- 远程 Redis 地址未配置：启动脚本会回退到本机 `127.0.0.1:6379`，本机没有 Redis 时会失败。
- Celery 启动后立即退出：先看 `backend/video/logs/`，确认虚拟环境、Redis 认证和 Django 配置。
- 后端端口起来但接口 500：优先检查 MySQL 权限和迁移状态；HTTP 进程存活不等于依赖全部正常。
- Electron 能打开但页面报错：先单独执行 `npm run dev` 或 `npm run build`，区分 Vite 编译问题和 Electron 问题。

## 7. 日志和复现信息

提交问题时附上：操作系统、Python/Node 版本、执行命令、完整首个错误堆栈、相关日志文件名和 `git status -sb`。不要附带 `.env` 内容、密码、token、API Key 或私钥。
