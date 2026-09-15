"""本地执行器：复用 MCP 服务端的真实渲染逻辑，把工作流直接打到本机 ComfyUI。

存在的意义 —— 它走的是 MCP 工具完全相同的代码路径
(`WorkflowManager.render_workflow` + `DefaultsManager` + `ComfyUIClient`)，
所以这里跑通 == MCP 那边跑通，不需要先「信任连接器」也能验证。

用法:
    python run_workflow.py list
    python run_workflow.py <workflow_id> [key=value ...]

示例:
    python run_workflow.py douyin_cover prompt="a lone crane over a misty lake" steps=28

参数类型按工作流里的 PARAM_ 占位符自动转换 (PARAM_INT_* -> int 等)。
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

BASE = Path(r"E:\ComfyUI-MCP")
SERVER = BASE / "comfyui-mcp-server"

# 必须在 import 服务端模块之前准备环境
os.environ.setdefault("COMFY_MCP_WORKFLOW_DIR", str(BASE / "workflows"))
os.environ.setdefault("COMFYUI_URL", "http://127.0.0.1:8188")
os.environ.setdefault("COMFY_MCP_DEFAULT_IMAGE_MODEL", "v1-5-pruned-emaonly-fp16.safetensors")

sys.path.insert(0, str(SERVER))

from comfyui_client import ComfyUIClient  # noqa: E402
from managers.defaults_manager import DefaultsManager  # noqa: E402
from managers.workflow_manager import WorkflowManager  # noqa: E402


def build():
    client = ComfyUIClient(os.environ["COMFYUI_URL"])
    defaults = DefaultsManager(client)
    wm = WorkflowManager(Path(os.environ["COMFY_MCP_WORKFLOW_DIR"]))
    return client, defaults, wm


def coerce(raw: str, annotation: type):
    if annotation is int:
        return int(float(raw))
    if annotation is float:
        return float(raw)
    if annotation is bool:
        return raw.strip().lower() in ("1", "true", "yes", "on")
    return raw


def cmd_list() -> int:
    _, _, wm = build()
    if not wm.tool_definitions:
        print("(工作流目录为空)")
        return 1
    for d in wm.tool_definitions:
        print(f"\n=== {d.workflow_id}   (工具名: {d.tool_name}) ===")
        for name, p in d.parameters.items():
            flag = "必填" if p.required else "可选"
            print(f"    {name:<18} {p.annotation.__name__:<6} [{flag}]  {p.description}")
    return 0


def cmd_run(workflow_id: str, raw_params: list[str]) -> int:
    client, defaults, wm = build()

    definition = next((d for d in wm.tool_definitions if d.workflow_id == workflow_id), None)
    if definition is None:
        ids = [d.workflow_id for d in wm.tool_definitions]
        print(f"找不到工作流 '{workflow_id}'。现有: {ids}")
        return 2

    provided: dict = {}
    for item in raw_params:
        key, sep, value = item.partition("=")
        if not sep:
            print(f"参数格式应为 key=value，忽略: {item}")
            continue
        key = key.strip()
        param = definition.parameters.get(key)
        if param is None:
            print(f"警告: 工作流没有参数 '{key}'，将被服务端丢弃")
            provided[key] = value
            continue
        provided[key] = coerce(value, param.annotation)

    print(f">>> 渲染工作流 '{workflow_id}'")
    for name, value in provided.items():
        print(f"      {name} = {value!r}")

    rendered = wm.render_workflow(definition, provided, defaults)

    leftovers = [
        (nid, k, v)
        for nid, node in rendered.items()
        for k, v in node.get("inputs", {}).items()
        if isinstance(v, str) and v.startswith("PARAM_")
    ]
    if leftovers:
        print("!! 仍有未填充的占位符（会直接 400）:")
        for nid, k, v in leftovers:
            print(f"     node {nid}.{k} = {v}")
        return 3

    started = time.time()
    result = client.run_custom_workflow(rendered, definition.output_preferences)
    elapsed = time.time() - started

    print(f"\n<<< 完成，耗时 {elapsed:.1f}s")
    print(json.dumps(result, ensure_ascii=False, indent=2)[:3000])
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    if sys.argv[1] == "list":
        return cmd_list()
    return cmd_run(sys.argv[1], sys.argv[2:])


if __name__ == "__main__":
    raise SystemExit(main())
