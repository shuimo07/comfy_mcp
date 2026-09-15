# -*- coding: utf-8 -*-
"""ComfyUI headless 启动器（供 MCP 包装器与手动脚本共用）。

职责：
  1. 探测 ComfyUI API 是否已在运行（默认 http://127.0.0.1:8188）。
  2. 未运行时，用 Comfy Desktop 自带的独立 venv 拉起一个 headless 后端。
  3. 拉起后等待端口就绪。

进程创建方式说明（本机关键坑）：
  用 subprocess.Popen 启动的子进程挂在调用方 job object 下，调用方一退出就被
  连带终止 —— 即使加了 DETACHED_PROCESS / CREATE_BREAKAWAY_FROM_JOB 也一样。
  实测可行的办法是走 Shell（ShellExecuteW）：新进程由 explorer.exe 接管，
  不受调用方 job 约束。（pywin32 的 WMI 方法在本机绑定异常，已弃用。）

停止方式：按 8188 端口的实际监听 PID 终止进程树，因此无论后端是我们拉起的
还是 Comfy Desktop 自己拉起的，都能正确收尾。
"""

from __future__ import annotations

import ctypes
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

BASE = Path(__file__).resolve().parent

# ---- Comfy Desktop 的安装布局（全部在 E 盘） ----
COMFY_ROOT = Path(r"E:\Comfy-Desktop\ComfyUI-Installs\ComfyUI")
COMFY_PY = COMFY_ROOT / "ComfyUI" / ".venv" / "Scripts" / "python.exe"
COMFY_MAIN = COMFY_ROOT / "ComfyUI" / "main.py"
SHARED_DIR = Path(r"E:\Comfy-Desktop\ComfyUI-Shared")
MODEL_YAML = BASE / "extra_model_paths.yaml"

RUNTIME_DIR = BASE / "runtime"
LOG_DIR = BASE / "logs"
HEADLESS_LOG = LOG_DIR / "comfyui-headless.log"
LAUNCH_SCRIPT = RUNTIME_DIR / "launch-comfyui.cmd"
PID_FILE = LOG_DIR / "comfyui-headless.pid"

COMFYUI_URL = os.getenv("COMFYUI_URL", "http://127.0.0.1:8188").rstrip("/")
BOOT_TIMEOUT = int(os.getenv("COMFYUI_BOOT_TIMEOUT", "180"))

SW_HIDE = 0
SW_SHOWNORMAL = 1


def log(msg: str) -> None:
    print(f"[comfyui-mcp] {msg}", file=sys.stderr, flush=True)


def _port_of(url: str) -> int:
    p = urlparse(url)
    return p.port or (443 if p.scheme == "https" else 80)


def _host_of(url: str) -> str:
    return urlparse(url).hostname or "127.0.0.1"


def is_up(timeout: float = 2.0) -> bool:
    """ComfyUI 的 /system_stats 能正常返回 200 即视为就绪。"""
    try:
        with urllib.request.urlopen(f"{COMFYUI_URL}/system_stats", timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def port_in_use() -> bool:
    """端口已被占用（无论监听方是不是 ComfyUI）。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.0)
        return s.connect_ex((_host_of(COMFYUI_URL), _port_of(COMFYUI_URL))) == 0


def preflight() -> None:
    """检查启动 ComfyUI 所需的文件是否齐全。"""
    missing = [
        f"{label}: {p}"
        for label, p in (
            ("ComfyUI 解释器", COMFY_PY),
            ("ComfyUI 入口 main.py", COMFY_MAIN),
            ("模型路径配置", MODEL_YAML),
        )
        if not p.exists()
    ]
    if missing:
        raise FileNotFoundError("缺少必要文件:\n  - " + "\n  - ".join(missing))


def _write_launch_script() -> Path:
    """生成启动用 .cmd（每次启动重写，保证与当前配置一致）。"""
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    port = _port_of(COMFYUI_URL)
    # ------------------------------------------------------------------
    # SageAttention 加速开关（默认关）
    #
    # 现状（2026-09-15 实测）：sageattention 2.2 + triton-windows 3.8 已装进 .venv，
    # ComfyUI 也能识别（启动日志出现 "Using sage attention"），但**出图会卡死**。
    # 根因：SageAttention 的 int8 量化预处理走 triton，triton 首次执行时
    # 要 JIT 编译 backends/nvidia/driver.c 生成 cuda_utils，这需要 MSVC 编译器；
    # 本机没有装 VS Build Tools（cl.exe 不存在），于是卡约 120s 后抛
    #   ImportError: DLL load failed while importing cuda_utils
    # 表现为：提交任务后一直 "running"，连 256x256/4步都跑不完，interrupt 也无效。
    #
    # 解决：装 VS Build Tools（勾选 "使用 C++ 的桌面开发"），然后设
    #   COMFY_USE_SAGE_ATTENTION=1
    # 即可开启。届时 RTX 4060 Laptop(Ada sm_89) 走 SageAttention2++ 内核，
    # 预期 30-40% 提速。
    # ------------------------------------------------------------------
    use_sage = os.getenv("COMFY_USE_SAGE_ATTENTION", "0") == "1"
    sage_arg = " --use-sage-attention" if use_sage else ""
    if use_sage:
        log("SageAttention 已启用（COMFY_USE_SAGE_ATTENTION=1）")
    args = (
        f'"{COMFY_PY}" -u -s "{COMFY_MAIN}"'
        f" --listen 127.0.0.1 --port {port}"
        f" --enable-manager"
        f"{sage_arg}"
        f' --extra-model-paths-config "{MODEL_YAML}"'
        f' --input-directory "{SHARED_DIR / "input"}"'
        f' --output-directory "{SHARED_DIR / "output"}"'
        f' >> "{HEADLESS_LOG}" 2>&1'
    )
    body = (
        "@echo off\r\n"
        f'cd /d "{COMFY_ROOT}"\r\n'
        f"{args}\r\n"
    )
    LAUNCH_SCRIPT.write_text(body, encoding="utf-8", newline="")
    return LAUNCH_SCRIPT


def _spawn_detached(script: Path, show_window: bool = False) -> int:
    """启动 ComfyUI。

    优先尝试「脱离调用方 job」（CREATE_BREAKAWAY_FROM_JOB），成功则后端可独立
    存活；若调用方 job 不允许 breakaway（实测本机多数情况如此），进程会与调用
    它的 MCP 服务端同生命周期 —— 服务端退出时自动回收，不会留孤儿进程。

    输出重定向到日志文件，且 stdin 接 DEVNULL，避免污染 MCP 的 stdio 通道。
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    if show_window:
        ctypes.windll.shell32.ShellExecuteW(None, "open", str(script), None, str(BASE), SW_SHOWNORMAL)
        return -1

    DETACHED_PROCESS = 0x00000008
    CREATE_NEW_PROCESS_GROUP = 0x00000200
    CREATE_BREAKAWAY_FROM_JOB = 0x01000000

    # 注意：日志重定向由 script 自己用 ">>" 完成。这里必须用 DEVNULL，
    # 否则同一个日志文件被两处打开会报「另一个程序正在使用此文件」，
    # 导致 cmd 的重定向失败、ComfyUI 根本起不来。
    last: Exception | None = None
    for flags, label in (
        (DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB, "已脱离 job，可独立存活"),
        (DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP, "随 MCP 服务端生命周期"),
    ):
        try:
            proc = subprocess.Popen(
                ["cmd.exe", "/c", str(script)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
                creationflags=flags,
            )
            log(f"进程模式: {label} (PID={proc.pid})")
            return int(proc.pid)
        except OSError as e:
            last = e
    raise RuntimeError(f"启动失败: {last}")


def listener_pid() -> int | None:
    """查出监听 ComfyUI 端口的 PID。"""
    try:
        raw = subprocess.run(["netstat", "-ano", "-p", "TCP"],
                             capture_output=True, timeout=20).stdout
    except Exception:
        return None
    if not raw:
        return None
    # netstat 输出在中文 Windows 上是 GBK，统一按字节取回再容错解码
    out = raw.decode("utf-8", errors="replace")
    needle = f":{_port_of(COMFYUI_URL)}"
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[0].upper() == "TCP" and parts[3].upper() == "LISTENING":
            if parts[1].endswith(needle):
                if parts[4].isdigit():
                    return int(parts[4])
    return None


def start(wait: bool = True, show_window: bool = False) -> int | None:
    """确保 ComfyUI 在运行。已在运行返回 None；否则返回监听 PID（可能为 None）。"""
    if is_up():
        log(f"ComfyUI 已在运行: {COMFYUI_URL}")
        return None

    if port_in_use():
        log(f"警告: {COMFYUI_URL} 端口被占用，但 /system_stats 无响应 —— 可能是别的程序。")
        log("不自动启动，交由 MCP 服务端自行重试。")
        return None

    preflight()
    script = _write_launch_script()

    log("正在启动 ComfyUI headless 后端 ...")
    _spawn_detached(script, show_window=show_window)
    log(f"启动脚本: {script}")
    log(f"运行日志: {HEADLESS_LOG}")

    if not wait:
        return None

    started = time.time()
    deadline = started + BOOT_TIMEOUT
    last_note = 0.0
    while time.time() < deadline:
        if is_up():
            pid = listener_pid()
            if pid:
                PID_FILE.write_text(str(pid), encoding="utf-8")
            log(f"ComfyUI 就绪（耗时 {time.time() - started:.0f}s，PID={pid}）。")
            return pid
        now = time.time()
        if now - last_note >= 10:
            log(f"等待 ComfyUI 就绪 ... 已等待 {int(now - started)}s")
            last_note = now
        time.sleep(1.0)

    log(f"超时: {BOOT_TIMEOUT}s 内未就绪，仍继续启动 MCP 服务端（其自身会再重试）。")
    return None


def stop() -> bool:
    """终止监听 ComfyUI 端口的进程树。"""
    pid = listener_pid()
    if pid is None and PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text(encoding="utf-8").strip())
        except ValueError:
            pid = None
    if pid is None:
        log(f"没有进程在监听 {_port_of(COMFYUI_URL)} 端口，无需停止。")
        PID_FILE.unlink(missing_ok=True)
        return False

    out = subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                         capture_output=True, text=True)
    ok = out.returncode == 0
    log(f"taskkill PID={pid} -> {'成功' if ok else '失败'} "
        f"{(out.stdout or '').strip()} {(out.stderr or '').strip()}")
    PID_FILE.unlink(missing_ok=True)
    return ok


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "start"
    if action == "stop":
        sys.exit(0 if stop() else 1)
    if action == "status":
        print("已运行" if is_up() else "未运行")
        sys.exit(0)
    if action == "restart":
        stop()
        time.sleep(2)
    start(wait=True, show_window=(action == "start-window"))
    sys.exit(0 if is_up() else 1)
