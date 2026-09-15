# -*- coding: utf-8 -*-
"""端到端验证：以真实 MCP 客户端身份连接 mcp_entry.py，走完整握手并调用工具。"""
import asyncio
import json
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

BASE = r"E:\ComfyUI-MCP"
ENV = {
    "COMFYUI_URL": "http://127.0.0.1:8188",
    "COMFYUI_AUTOSTART": "1",
    "COMFYUI_BOOT_TIMEOUT": "150",
    "COMFY_MCP_DEFAULT_IMAGE_MODEL": os.getenv(
        "COMFY_MCP_DEFAULT_IMAGE_MODEL", "v1-5-pruned-emaonly-fp16.safetensors"),
    "COMFY_MCP_WORKFLOW_DIR": os.path.join(BASE, "workflows"),
    "COMFYUI_OUTPUT_ROOT": r"E:\Comfy-Desktop\ComfyUI-Shared\output",
    "COMFY_MCP_ASSET_TTL_HOURS": "24",
    "PYTHONUNBUFFERED": "1",
    "PYTHONUTF8": "1",
    "SYSTEMROOT": os.environ.get("SYSTEMROOT", r"C:\Windows"),
    "PATH": os.environ.get("PATH", ""),
}


def text_of(result):
    parts = []
    for c in getattr(result, "content", []) or []:
        parts.append(getattr(c, "text", str(c)))
    return "\n".join(parts)


async def main():
    params = StdioServerParameters(
        command=os.path.join(BASE, ".venv", "Scripts", "python.exe"),
        args=[os.path.join(BASE, "mcp_entry.py")],
        env=ENV,
        cwd=BASE,
    )
    print(">>> 连接 MCP 服务端 ...", flush=True)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            info = await session.initialize()
            print(">>> 握手成功")
            print("    服务端:", info.serverInfo.name, info.serverInfo.version)
            print("    协议版本:", info.protocolVersion)

            tools = await session.list_tools()
            print(f">>> 可用工具 {len(tools.tools)} 个:")
            for t in sorted(tools.tools, key=lambda x: x.name):
                print(f"      - {t.name}")

            for name, args in (("list_workflows", {}),
                               ("list_models", {"model_type": "checkpoints"}),
                               ("get_queue_status", {})):
                try:
                    res = await session.call_tool(name, args)
                    body = text_of(res)
                    print(f">>> 调用 {name} -> {'错误' if res.isError else '成功'}")
                    print("    " + body[:600].replace("\n", "\n    "))
                except Exception as e:
                    print(f">>> 调用 {name} 异常: {type(e).__name__}: {e}")

            if os.getenv("GEN") == "1":
                prompt = os.getenv("GEN_PROMPT", "a red apple on a wooden table, soft light")
                tool = os.getenv("GEN_TOOL", "douyin_cover")
                print(f">>> 实际出图: {prompt!r} via {tool} (约 15-30s) ...")
                try:
                    res = await session.call_tool(tool, {"prompt": prompt})
                    print(f">>> {tool} -> {'错误' if res.isError else '成功'}")
                    print("    " + text_of(res)[:900].replace("\n", "\n    "))
                except Exception as e:
                    print(f">>> {tool} 异常: {type(e).__name__}: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(asyncio.wait_for(main(), timeout=300))
    except asyncio.TimeoutError:
        print("!! 整体超时")
        sys.exit(1)
