# -*- coding: utf-8 -*-
"""WorkBuddy 的 ComfyUI MCP 入口（stdio 传输）。

两个必须由本包装器解决的问题：

1. 上游 server.py 在 ComfyUI 未运行时会 sys.exit(1)，MCP 客户端会永远拿不到工具。
   → 这里先确保 ComfyUI 在 http://127.0.0.1:8188 运行，再加载上游服务端。

2. 上游在 import 阶段以及健康检查里大量 print() 到 stdout。
   而 stdio 模式下 stdout 就是 JSON-RPC 通道，这些横幅会把协议流打脏。
   → 这里把 print 重定向到 stderr（日志），只留 mcp.run() 使用真正的 stdout。

环境变量：
  COMFYUI_URL            ComfyUI API 地址，默认 http://127.0.0.1:8188
  COMFYUI_AUTOSTART      1=未运行时自动拉起 headless 后端（默认 1），0=不自动启动
  COMFYUI_BOOT_TIMEOUT   等待 ComfyUI 就绪的最长秒数，默认 150
"""

from __future__ import annotations

import builtins
import importlib
import os
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
REPO = BASE / "comfyui-mcp-server"
SERVER_PY = REPO / "server.py"

sys.path.insert(0, str(BASE))
import comfy_launcher as launcher  # noqa: E402


def _redirect_print_to_stderr() -> None:
    """让所有 print() 走 stderr，保护 stdio 上的 JSON-RPC 通道。"""
    real_print = builtins.print

    def safe_print(*args, **kwargs):
        kwargs.setdefault("file", sys.stderr)
        real_print(*args, **kwargs)

    builtins.print = safe_print


def _prepare_env() -> None:
    os.environ.setdefault("COMFYUI_URL", launcher.COMFYUI_URL)
    os.environ.setdefault("COMFY_MCP_WORKFLOW_DIR", str(REPO / "workflows"))
    os.environ.setdefault("COMFYUI_OUTPUT_ROOT", str(launcher.SHARED_DIR / "output"))
    os.environ.setdefault("COMFY_MCP_ASSET_TTL_HOURS", "24")


def main() -> int:
    if not SERVER_PY.exists():
        builtins.print(f"[comfyui-mcp] 找不到上游服务端: {SERVER_PY}", file=sys.stderr)
        return 1

    autostart = os.getenv("COMFYUI_AUTOSTART", "1").strip().lower() not in ("0", "false", "no", "off")

    if launcher.is_up():
        launcher.log(f"ComfyUI 已在运行: {launcher.COMFYUI_URL}")
    elif autostart:
        launcher.start(wait=True)
    else:
        launcher.log("ComfyUI 未运行且已禁用自动启动，交由上游服务端自行重试。")

    _prepare_env()

    # 先重定向 print，再 import —— 上游模块级横幅与健康检查的 print 都会落到 stderr
    _redirect_print_to_stderr()
    os.chdir(REPO)
    sys.path.insert(0, str(REPO))
    try:
        server = importlib.import_module("server")
    except SystemExit as e:  # 上游在 ComfyUI 不可达时会 sys.exit(1)
        launcher.log(f"上游服务端初始化失败（ComfyUI 不可达），退出码 {e.code}")
        return int(e.code or 1)

    launcher.log("MCP 服务端就绪，进入 stdio 传输 ...")
    try:
        server.mcp.run(transport="stdio")
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
