# ComfyUI × WorkBuddy MCP 接入

把本机 ComfyUI 接到 WorkBuddy，在对话里直接调用它的 API 出图 / 跑工作流。

## 组成

| 角色 | 路径 |
|---|---|
| **本仓库** | `E:\ComfyUI-MCP\` → `github.com/shuimo07/comfy_mcp` |
| MCP 服务端（上游） | `E:\ComfyUI-MCP\comfyui-mcp-server\`（joenorton/comfyui-mcp-server，Apache-2.0，**git submodule**） |
| 独立 venv | `E:\ComfyUI-MCP\.venv\` |
| 入口包装器 | `E:\ComfyUI-MCP\mcp_entry.py` |
| 启动器 | `E:\ComfyUI-MCP\comfy_launcher.py` |
| 模型路径映射 | `E:\ComfyUI-MCP\extra_model_paths.yaml` |
| 一键重建 | `E:\ComfyUI-MCP\setup.bat` |
| ComfyUI 本体 | `E:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\`（Comfy Desktop 独立版 v0.28.0） |
| 模型 / 输入 / 输出 | `E:\Comfy-Desktop\ComfyUI-Shared\` |
| 运行日志 | `E:\ComfyUI-MCP\logs\comfyui-headless.log` |

WorkBuddy 侧配置：`C:\Users\legion\.workbuddy\mcp.json`，服务名 `comfyui`，stdio 传输。

> 该文件与 PowerBI 无关。三个 PowerBI MCP 服务配在 **DSH** 的
> `E:\.dsh\profiles\web\cordis.patch.yml`，是另一套独立配置。

## 日常使用

**推荐**：先双击 `start-comfyui.bat` 把后端拉起来（约 15–20 秒），再去 WorkBuddy 用。
后端已在运行时，MCP 握手是秒级的。

也可以什么都不做 —— MCP 服务端启动时会自动把后端拉起来（`COMFYUI_AUTOSTART=1`），
只是首次握手要等它启动完。

其他脚本：

- `status-comfyui.bat` —— 看后端在不在
- `stop-comfyui.bat` —— 按 8188 端口的实际监听进程终止它

> 想让 **Comfy Desktop 图形界面**用 8188，先跑 `stop-comfyui.bat` 释放端口，
> 再打开 Comfy Desktop。两者同时开的话，Desktop 会自动换端口。

## 已暴露的工具（17 个）

生成：`generate_image` `generate_song` `regenerate`
查看：`view_image`
任务：`get_queue_status` `get_job` `list_assets` `get_asset_metadata` `cancel_job`
配置：`list_models` `get_defaults` `set_defaults`
工作流：`list_workflows` `run_workflow`
发布：`get_publish_info` `set_comfyui_output_root` `publish_asset`

`workflows/` 下的 JSON 会被自动发现成工具，用 `PARAM_*` 占位符暴露参数。

## ⚠️ 当前缺模型

`E:\Comfy-Desktop\ComfyUI-Shared\models` 里目前只有几个 `.part` **未下载完成**的文件
（wan2.2 i2v 视频模型），没有可用的 checkpoint。
`list_models` 返回空，`generate_image` 会因为没有模型而失败。

先往 `models\checkpoints\` 放一个大模型（SD1.5 / SDXL 等）再出图。

## 排错

| 现象 | 处理 |
|---|---|
| WorkBuddy 里看不到 comfyui 工具 | 连接器管理右上角「自定义连接器」里对 `comfyui` 点**信任**，然后重启应用 |
| 工具报连接失败 | 跑 `status-comfyui.bat`；不在就 `start-comfyui.bat` |
| 启动失败 | 看 `logs\comfyui-headless.log` 尾部 |
| 换端口 | 改 `mcp.json` 里的 `COMFYUI_URL` |

## 本机踩过的坑（改动前先读）

1. **`requirements.txt` 只写 `mcp>=0.9.0`**，pip 会装 mcp 2.x，而上游用的是 v1 的
   `mcp.server.fastmcp.FastMCP`，2.x 已改名 → 必须钉 `mcp<2`（现在是 1.30.0）。
2. **子进程会被连带杀掉**：`subprocess.Popen` 启动的进程挂在调用方 job 下，
   即使加 `DETACHED_PROCESS | CREATE_BREAKAWAY_FROM_JOB` 也常无效。
   本机 pywin32 的 `Win32_Process.Create` 绑定异常（`'int' object is not callable`），
   最终采用「尽力 breakaway、失败则随 MCP 服务端生命周期」的策略。
3. **日志文件不能双重打开**：Popen 传了日志句柄、`.cmd` 里又 `>>`，
   会报「另一个程序正在使用此文件」导致 ComfyUI 起不来。Popen 必须用 `DEVNULL`。
4. **上游往 stdout 打横幅**会污染 stdio 的 JSON-RPC 流 → 入口里把 `print` 重定向到 stderr。
5. 给 Windows 的 `python.exe` 传路径要用**反斜杠**，`/e/...` 这种 MSYS 路径不会被转换。
6. `netstat` 输出在中文 Windows 是 GBK，取回后要容错解码。

## 版本库 / 回滚

本仓库：<https://github.com/shuimo07/comfy_mcp>（`main` 分支）

- 上游 `comfyui-mcp-server/` 以 **git submodule** 方式引入，钉在具体 commit 上。
  本仓库**没有改动上游任何文件**，所有适配都写在包装器里。
- `.venv/` `logs/` `runtime/` `assets/` `__pycache__/` 与模型文件不入库（见 `.gitignore`）。
- 凭据存在 `E:\AI\.git-credentials`（由全局 `credential.helper=store` 读取），**不在仓库内**。

常用操作：

```bat
git -C E:\ComfyUI-MCP status
git -C E:\ComfyUI-MCP log --oneline
git -C E:\ComfyUI-MCP diff                  :: 看改动，便于回滚
git -C E:\ComfyUI-MCP checkout -- <file>    :: 单个文件回滚
git -C E:\ComfyUI-MCP reset --hard <sha>    :: 整体回滚
```

> 本机沙箱内 `curl` 到 api.github.com 不通（DNS 被劫持到 127.0.0.1），
> **git 网络命令要放在 Git Bash / 本机终端里跑**，PowerShell 里跑会 401。

## 从零重建

换机或重装后，按顺序：

1. 装好 ComfyUI（Comfy Desktop 独立版），确认 `E:\Comfy-Desktop\ComfyUI-Shared\` 存在
2. `git clone --recursive https://github.com/shuimo07/comfy_mcp.git E:\ComfyUI-MCP`
3. 双击 `setup.bat`（拉 submodule + 建 venv + 装依赖 + 钉 mcp 1.x + 自检）
4. 把 `config\workbuddy-mcp.example.json` 的 `comfyui` 段合并进 `C:\Users\legion\.workbuddy\mcp.json`
5. WorkBuddy → 连接器管理 → 右上角「自定义连接器」→ 对 `comfyui` 点**信任** → 重启应用
6. 下模型：`E:\ComfyUI-MCP\.venv\Scripts\python.exe tools\download_checkpoint.py`
7. 双击 `start-comfyui.bat` 预热后端，然后在对话里说「用 ComfyUI 画一张……」
8. 回归自检：`GEN=1 .\.venv\Scripts\python.exe tools\mcp_selftest.py`

## 实测记录（2026-09-15）

- 端到端 MCP 握手通过，17 个工具全部可见。
- `generate_image` 出图成功 → `ComfyUI_00001_.png`（512×512，386 KB）。
- **含拉起 ComfyUI 后端在内，全程 29 秒**；后端已预热时握手是秒级的。
- 冷启动 ComfyUI 约 60 秒（首次），缓存热后约 15–20 秒。
