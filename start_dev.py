import os
import sys
import time
import socket
import subprocess
import platform
import shutil
import json
from urllib.parse import urlparse
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


PID_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".dev_pids.json")

# Windows 控制台默认 GBK 编码，无法输出 ✓/⚠ 等 Unicode 字符，会导致 UnicodeEncodeError
# 统一使用 UTF-8 输出，且遇到无法编码的字符时用 ? 替代而非崩溃
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def check_dependency(name, command):
    """检查依赖是否已安装"""
    if shutil.which(command):
        return True
    print(f"✗ 未找到 {name}，请先安装 {command}")
    return False


def check_port(port, host="127.0.0.1"):
    """检查端口是否被占用"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        result = s.connect_ex((host, port))
        return result == 0  # True = 被占用


def load_env_file(root_dir):
    """加载项目根目录的本地 .env，已存在的系统环境变量优先。"""
    env_path = os.path.join(root_dir, ".env")
    if not os.path.exists(env_path):
        return

    with open(env_path, "r", encoding="utf-8") as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("\"'")
            if key:
                os.environ.setdefault(key, value)


def get_redis_endpoint():
    """读取 Redis URL，支持远程 Redis；未配置时回退到本机默认地址。"""
    redis_url = os.environ.get("REDIS_URL") or os.environ.get("CELERY_BROKER_URL")
    if not redis_url:
        return {
            "url": "redis://127.0.0.1:6379/0",
            "host": "127.0.0.1",
            "port": 6379,
            "remote": False,
        }

    parsed = urlparse(redis_url)
    if parsed.scheme not in ("redis", "rediss") or not parsed.hostname:
        raise ValueError("REDIS_URL/CELERY_BROKER_URL 必须是有效的 redis:// 或 rediss:// 地址")

    return {
        "url": redis_url,
        "host": parsed.hostname,
        "port": parsed.port or 6379,
        "remote": parsed.hostname not in ("127.0.0.1", "localhost", "::1"),
    }


def wait_for_port(port, timeout=30, check_interval=0.5):
    """等待端口可用（服务启动成功）"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        if check_port(port, "127.0.0.1") or check_port(port, "0.0.0.0"):
            return True
        time.sleep(check_interval)
    return False


def wait_for_http(url, timeout=30, check_interval=0.5):
    """等待 HTTP 探针返回 2xx，并返回最后一次失败原因。"""
    deadline = time.time() + timeout
    last_error = "未收到响应"
    while time.time() < deadline:
        try:
            request = Request(url, method="GET")
            with urlopen(request, timeout=2) as response:
                if 200 <= response.status < 300:
                    return True, None
                last_error = f"HTTP {response.status}"
        except HTTPError as exc:
            last_error = f"HTTP {exc.code}"
        except (URLError, TimeoutError, OSError) as exc:
            last_error = type(exc).__name__
        time.sleep(check_interval)
    return False, last_error


def print_header(text):
    print("\n" + "=" * 50)
    print(text)
    print("=" * 50 + "\n")


def save_pids(pids):
    """保存 PID 到文件"""
    with open(PID_FILE, "w", encoding="utf-8") as f:
        json.dump(pids, f, indent=2)


def start_process(name, command, cwd=None, shell=True, log_file=None):
    """启动进程并返回 PID"""
    system = platform.system()
    
    # 如果指定了日志文件，输出到文件；否则输出到 DEVNULL
    if log_file:
        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), log_file)
        stdout_handle = open(log_path, "w", encoding="utf-8")
        stderr_handle = subprocess.STDOUT
    else:
        stdout_handle = subprocess.DEVNULL
        stderr_handle = subprocess.DEVNULL
    
    # 设置启动参数
    kwargs = {
        "shell": shell,
        "cwd": cwd,
        "stdout": stdout_handle,
        "stderr": stderr_handle,
    }
    
    # Windows 特殊处理：创建新进程组，避免信号传递
    if system == "Windows":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    else:
        kwargs["start_new_session"] = True
    
    try:
        proc = subprocess.Popen(command, **kwargs)
        print(f"  ✓ {name} 已启动 (PID: {proc.pid})")
        if log_file:
            print(f"    日志: {log_file}")
        return proc.pid
    except Exception as e:
        print(f"  ✗ {name} 启动失败: {e}")
        return None


def main():
    print_header("启动视频平台开发环境")
    
    root_dir = os.path.dirname(os.path.abspath(__file__))
    load_env_file(root_dir)
    backend_dir = os.path.join(root_dir, "backend", "video")
    frontend_dir = os.path.join(root_dir, "frontend", "video-ui")
    
    system = platform.system()
    print(f"操作系统: {system}")
    print(f"Python: {sys.version.split()[0]}\n")
    
    # 检查依赖
    print("检查依赖...")
    deps_ok = True
    redis_endpoint = get_redis_endpoint()
    deps_ok &= check_dependency("Node.js", "npm")
    deps_ok &= check_dependency("Python", "python")
    
    if not deps_ok:
        print("\n请先安装缺失的依赖！")
        sys.exit(1)
    print("✓ 所有依赖已就绪\n")
    
    print("检查端口...")
    ports_to_check = {"Django": 8000, "Frontend": 5173}
    port_conflict = False
    
    if check_port(redis_endpoint["port"], redis_endpoint["host"]):
        print("  ✓ 端口 6379 (Redis) 已在运行")
    else:
        print("  - 端口 6379 (Redis) 未运行，稍后启动")
    
    for name, port in ports_to_check.items():
        if check_port(port):
            print(f"  ✗ 端口 {port} ({name}) 已被占用")
            port_conflict = True
        else:
            print(f"  ✓ 端口 {port} ({name}) 可用")
    
    if port_conflict:
        print("\n请先释放被占用的端口，或运行 python stop_dev.py")
        sys.exit(1)
    print()
    
    pids = {}
    startup_ok = True
    
    print("[1/4] 检查 Redis...")
    if redis_endpoint["remote"]:
        if not check_port(redis_endpoint["port"], redis_endpoint["host"]):
            print("  Redis 远程地址无法连接，请检查 REDIS_URL")
            sys.exit(1)
        print("  Redis 远程服务已连接")
        pids["redis"] = None
    elif check_port(6379):
        print("  ✓ Redis 已在运行（系统服务）")
        pids["redis"] = None  
    else:
        print("  Redis 未运行，尝试启动...")
        if not check_dependency("本机 Redis", "redis-server"):
            print("  Redis 未运行，且未配置远程 REDIS_URL")
            sys.exit(1)

        pid = start_process("Redis", "redis-server")
        if pid:
            pids["redis"] = pid
            time.sleep(1)
            if not check_port(6379):
                print("  ⚠ Redis 可能未正常启动，请检查")
    
    # 获取虚拟环境 Python 路径
    venv_python = os.path.join(root_dir, "backend", "venv", "Scripts", "python.exe")
    venv_celery = os.path.join(root_dir, "backend", "venv", "Scripts", "celery.exe")
    
    if not os.path.exists(venv_python):
        print(f"✗ 未找到虚拟环境 Python: {venv_python}")
        sys.exit(1)

    # 2. 启动 Celery Worker
    print("\n[2/5] 启动 Celery Worker...")
    # Windows 使用 gevent 池（多线程），Linux/Mac 使用 prefork 池
    # 添加 --events 参数以支持 Flower 监控
    if system == "Windows":
        celery_cmd = f"{venv_celery} -A video worker -l info --pool=gevent --concurrency=10 --events"
    else:
        celery_cmd = (
            f"{venv_celery} -A video worker -l info "
            "--pool=prefork "
            "--concurrency=2 "
            "--max-tasks-per-child=10 "
            "--max-memory-per-child=500000 "
            "--events"
        )
    pid = start_process("Celery Worker", celery_cmd, cwd=backend_dir)
    if pid:
        pids["celery"] = pid
        print("  等待 Celery 启动...")
        time.sleep(3)
        # 检查进程是否还在运行
        try:
            if system == "Windows":
                result = subprocess.run(
                    f"tasklist /FI \"PID eq {pid}\" /NH",
                    shell=True,
                    capture_output=True,
                    text=True,
                    encoding='gbk',  # Windows 使用 GBK 编码
                    errors='ignore'
                )
                if result.stdout and str(pid) not in result.stdout:
                    print(f"  ✗ Celery Worker 进程已退出")
                    pids["celery"] = None
                else:
                    print("  ✓ Celery Worker 运行正常")
            else:
                os.kill(pid, 0)  # 检查进程是否存在
                print("  ✓ Celery Worker 运行正常")
        except (subprocess.SubprocessError, OSError):
            print(f"  ✗ Celery Worker 进程已退出")
            pids["celery"] = None
    else:
        print("  ✗ Celery Worker 启动失败")
    
    # 3. 启动 Celery Beat（定时任务调度器）
    print("\n[3/6] 启动 Celery Beat...")
    beat_cmd = f"{venv_celery} -A video beat -l info"
    pid = start_process("Celery Beat", beat_cmd, cwd=backend_dir)
    if pid:
        pids["celery_beat"] = pid
        print("  等待 Celery Beat 启动...")
        time.sleep(2)
        # 检查进程是否还在运行
        try:
            if system == "Windows":
                result = subprocess.run(
                    f"tasklist /FI \"PID eq {pid}\" /NH",
                    shell=True,
                    capture_output=True,
                    text=True,
                    encoding='gbk',
                    errors='ignore'
                )
                if result.stdout and str(pid) not in result.stdout:
                    print(f"  ✗ Celery Beat 进程已退出")
                    pids["celery_beat"] = None
                else:
                    print("  ✓ Celery Beat 运行正常")
            else:
                os.kill(pid, 0)
                print("  ✓ Celery Beat 运行正常")
        except (subprocess.SubprocessError, OSError):
            print(f"  ✗ Celery Beat 进程已退出")
            pids["celery_beat"] = None
    else:
        print("  ✗ Celery Beat 启动失败")
    
    # 4. 启动 Django (Uvicorn)
    print("\n[4/5] 启动 Django (Uvicorn)...")
    django_cmd = f"{venv_python} -m uvicorn video.asgi:application --host 127.0.0.1 --port 8000 --ws websockets"
    pid = start_process("Django", django_cmd, cwd=backend_dir)
    if pid:
        pids["django"] = pid
        print("  等待 Django 启动...")
        if wait_for_port(8000, timeout=15):
            ready_url = "http://127.0.0.1:8000/api/health/ready/"
            is_ready, error = wait_for_http(ready_url, timeout=20)
            if is_ready:
                print("  ✓ Django 已就绪（端口和依赖检查通过）")
            else:
                startup_ok = False
                print(f"  ⚠ Django 端口已打开，但就绪检查超时（{error}）")
        else:
            startup_ok = False
            print("  ⚠ Django 启动超时")
    
    # 5. 启动前端 (Electron 模式)
    print("\n[5/5] 启动前端 (Electron)...")
    frontend_cmd = "npm run electron:dev"
    pid = start_process("Frontend (Electron)", frontend_cmd, cwd=frontend_dir)
    if pid:
        pids["frontend"] = pid
        if wait_for_port(5173, timeout=20):
            print("  ✓ 前端端口已就绪，浏览器将自动打开")
        else:
            startup_ok = False
            print("  ⚠ 前端端口启动超时")
    
    save_pids(pids)
    
    if startup_ok:
        print_header("所有服务已启动！")
    else:
        print_header("服务已启动，但未通过全部就绪检查")
    print("后端地址: http://localhost:8000")
    print("前端地址: http://localhost:5173")
    print(f"\nPID 已保存到: {PID_FILE}")
    print("停止服务: python stop_dev.py\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n用户中断，退出...")
        sys.exit(0)
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
