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
| 自定义工作流 | `E:\ComfyUI-MCP\workflows\`（经 `COMFY_MCP_WORKFLOW_DIR` 生效） |
| 本地执行器 | `E:\ComfyUI-MCP\tools\run_workflow.py`（复用 MCP 真实渲染逻辑） |
| 自定义节点 | `E:\ComfyUI-MCP\custom_nodes\ComfyUI-MiniMax-H3-API\` → 用 `install-minimax-node.bat` 同步进 ComfyUI |
| 本机环境守卫 | `E:\ComfyUI-MCP\local-env\` ← junction ← `E:\WBData\_tools\`，把 WorkBuddy 数据钉在 E 盘 |
| 技能归档 | `E:\ComfyUI-MCP\skills\`（`C:\Users\legion\.workbuddy\skills` 的只读副本） |
| ComfyUI 本体 | `E:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\`（Comfy Desktop 独立版 v0.28.0） |
| 模型 / 输入 / 输出 | `E:\Comfy-Desktop\ComfyUI-Shared\` |
| 运行日志 | `E:\ComfyUI-MCP\logs\comfyui-headless.log` |

WorkBuddy 侧配置：`C:\Users\legion\.workbuddy\mcp.json`，服务名 `comfyui`，stdio 传输。

> ⏸️ **2026-09-16 起该 MCP 已从 `mcp.json` 注销（现为 `{"mcpServers": {}}`），处于「关闭」状态。**
> 原因：它 env 里带 `COMFYUI_AUTOSTART=1` —— WorkBuddy 一拉起这个 MCP 就会**自动把 ComfyUI 后端
> 一起启动**（常驻约 1 GB 内存），而当前还在等 MiniMax H3 的 API key，根本用不上。
> **想重新启用**：把 `config\workbuddy-mcp.example.json` 里 `mcpServers.comfyui` 整段合并回
> `C:\Users\legion\.workbuddy\mcp.json`，再到 WorkBuddy 连接器管理右上角「自定义连接器」
> 对 `comfyui` 点「信任」，重启应用。
> **只想要 MCP、不想自动起后端**：把 `COMFYUI_AUTOSTART` 改成 `"0"`。

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

## 已暴露的工具（20 个）

生成：`generate_image` `generate_song` `douyin_cover` `minimax_h3_video` `minimax_h3_i2v` `regenerate`
查看：`view_image`
任务：`get_queue_status` `get_job` `list_assets` `get_asset_metadata` `cancel_job`
配置：`list_models` `get_defaults` `set_defaults`
工作流：`list_workflows` `run_workflow`
发布：`get_publish_info` `set_comfyui_output_root` `publish_asset`

`workflows/` 下的 JSON 会被自动发现成工具，用 `PARAM_*` 占位符暴露参数。

## 模型与出图质量

当前唯一可用 checkpoint：`v1-5-pruned-emaonly-fp16.safetensors`（**SD1.5**，2.13 GB），
在 `E:\Comfy-Desktop\ComfyUI-Shared\models\checkpoints\`。

> 早前记的「有 20 GB wan2.2 未下完」是**误读** —— 那几个 `.part` 每个只有 ~60 MB，是空壳。
> 视频生成这条路当前走不通（缺模型，且 8 GB 显存本身也不够）。

### SD1.5 的题材适配（实测：28 步 / dpmpp_2m / karras / cfg 7.5）

| 题材 | 效果 | 说明 |
|---|---|---|
| 氛围静物、逆光、剪影 | ★★★★★ | 直接能当封面。实测「雨天窗边书桌+热茶」「逆光窗边读书剪影」都很好 |
| 水墨山水、意境 | ★★★★☆ | 层次和留白很到位；偶发中心小彩斑，建议多抽几张挑 |
| 抽象科技、神经网络 | ★★☆☆☆ | 容易糊成满屏纹理，没有视觉焦点。这类别用 SD1.5 |
| 具体动物、人物正脸 | ★☆☆☆☆ | 实测「仙鹤」被画成一道红色笔触。主体越具体越容易崩 |

**结论**：SD1.5 适合**文学向氛围图**，不适合科技向信息图。
要抬上限就换 **SDXL**（约 6.5 GB，8.6 GB 显存可跑）。

## 自定义工作流

服务端会把 `COMFY_MCP_WORKFLOW_DIR` 下的 `*.json` **自动发现成一个 MCP 工具**，
参数用 `PARAM_*` 占位符暴露。该变量是**替换**语义而非追加 ——
所以工作流放在本仓库自己的 `workflows\`（上游那三个已拷进来），submodule 保持干净。

可用的占位符名（只有这些是「可选 + 有内置默认值」）：

| 占位符 | 类型 |
|---|---|
| `PARAM_PROMPT` | str，**必填** |
| `PARAM_NEGATIVE_PROMPT` | str |
| `PARAM_INT_SEED` `PARAM_INT_STEPS` `PARAM_INT_WIDTH` `PARAM_INT_HEIGHT` | int |
| `PARAM_FLOAT_CFG` `PARAM_FLOAT_DENOISE` | float |
| `PARAM_STR_SAMPLER_NAME` `PARAM_STR_SCHEDULER` `PARAM_MODEL` | str |

**任何不在这组名字里的参数都会变成必填** —— canvas 尺寸因此直接写死在节点里，
保证「只给 prompt」也能出正确比例。

### 已有：`douyin_cover`（抖音竖版封面 / 配图）

- 画布 576×768（3:4），再走 latent 1.5× + hires fix（denoise 0.5）→ **输出 864×1152**
- 实测 **14–17 秒/张**（模型已在显存时）
- 参数：`prompt`（必填）、`negative_prompt`、`steps`、`cfg`、`sampler_name`、`scheduler`、`seed`

不连 MCP 也能本地跑，走的是与 MCP 完全相同的渲染代码路径：

```bat
cd E:\ComfyUI-MCP
.venv\Scripts\python.exe tools\run_workflow.py list
.venv\Scripts\python.exe tools\run_workflow.py douyin_cover prompt="..." steps=28 seed=123
```

### 已有：`minimax_h3_video` / `minimax_h3_i2v`（MiniMax H3 视频，直连官方 API）

**为什么不用 ComfyUI 自带的 MiniMax 节点**（读 `comfy_api_nodes/nodes_minimax.py` 与
`comfy_api_nodes/apis/minimax.py` 确认）：

- 自带节点请求的是 `/proxy/minimax/...`，由 **ComfyUI 官方后端中转**，鉴权用
  `auth_token_comfy_org` / `api_key_comfy_org` —— 必须充 Comfy 官方积分，**填不了自己的 MiniMax Key**；
- 模型枚举只到 `MiniMax-Hailuo-02`，**没有 H3**。

所以本仓库自带一个自定义节点，直连 `api.minimaxi.com`，**本地不跑模型、不占显存**。

| 节点（分类 `MiniMax H3 / API`） | 用途 |
|---|---|
| `MiniMax H3 视频生成 (API)` | 文生视频 / 首帧图生视频 / 首尾帧过渡 |
| `MiniMax H3 参考生视频 (API)` | 参考图 + 视频 + 音频 → 角色、动作、镜头、音色一致（口播好用） |

用到的官方接口：

| 步骤 | 请求 |
|---|---|
| 建任务 | `POST {base}/v2/video_generation`，`model: "MiniMax-H3"`，`content[]` 多模态数组 |
| 查任务 | `GET {base}/v2/query/video_generation/{task_id}` → 成功后给 `task.content.url` |
| 下载 | 直接 GET 那个 url，落盘成 `.mp4` |

- base：国内 `https://api.minimaxi.com`（节点默认 `region=cn`）／海外 `https://api.minimax.io`
- 参数：`resolution` = `768P` / `2K`，`duration` = 4~15 秒，另有 `ratio`；H3 原生带立体声音频
- 计费参考：768P ≈ ¥0.5/秒，2K ≈ ¥0.8/秒 → 5 秒片约 ¥2.5~4
- **API Key 放 `E:\Comfy-Desktop\ComfyUI-Cache\minimax_key.txt`**（单行纯文本，节点运行时读取，
  改完不用重启；不想用文件也可直接在节点上填 `api_key`）

节点源码以**本仓库 `custom_nodes\ComfyUI-MiniMax-H3-API\` 为准**，同步进 ComfyUI：

```bat
E:\ComfyUI-MCP\install-minimax-node.bat
E:\ComfyUI-MCP\stop-comfyui.bat  &&  E:\ComfyUI-MCP\start-comfyui.bat
```

工作流参数（MCP 侧）：`minimax_h3_video(prompt, duration)`、`minimax_h3_i2v(image, prompt, duration)`。

> **节点必须置 `OUTPUT_NODE = True`** —— 否则 ComfyUI 会以
> `Prompt has no outputs` 直接拒收整个工作流（不是报错，是 HTTP 400）。

### SageAttention（已装，但**默认关闭**）

`sageattention 2.2` + `triton-windows 3.8.0` 已装进 ComfyUI 的 `.venv`（torch 未动），
ComfyUI 启动日志会出现 `Using sage attention`。**但默认不加 `--use-sage-attention`。**

根因（2026-09-15 实测）：SageAttention 的 int8 量化预处理走 triton，而 triton 只带源码
`backends/nvidia/driver.c`、**没有预编译的 `cuda_utils.pyd`**，首次调用要 JIT 编译，需要 MSVC。
本机没装 VS Build Tools（`cl.exe` 不存在）→ 卡约 120s 后抛
`ImportError: DLL load failed while importing cuda_utils`。

**表现是致命的**：提交任务后一直 `running`，连 256×256 / 4 步都跑不完，`interrupt` 也停不掉。
关掉之后同样任务 **3.0 秒**完成。

启用条件：先装 VS Build Tools（勾选「使用 C++ 的桌面开发」），再设
`COMFY_USE_SAGE_ATTENTION=1`（`comfy_launcher.py` 里读这个变量决定是否追加参数）。
届时 RTX 4060 Laptop（Ada sm_89）走 SageAttention2++ 内核，预期 30–40% 提速。

轮子留在 `E:\Comfy-Desktop\ComfyUI-Cache\sage-wheel\`，别删。

### 加新工作流

1. 在 ComfyUI 界面搭好，导出 **API 格式**的 JSON
2. 丢进 `E:\ComfyUI-MCP\workflows\`
3. 把要暴露的参数值改成 `PARAM_*` 占位符
4. 重启 WorkBuddy 即可（服务端启动时扫描，文件 mtime 变化也会热重载定义）

### 已知小瑕疵

`douyin_cover` 返回的 `width` / `height` 报的是 **576×768**，实际产物是 **864×1152**。
这是上游 `_get_asset_metadata` 从工作流的 `EmptyLatentImage` 推尺寸导致的，
不影响出图，**以文件本身为准**。

## 排错

| 现象 | 处理 |
|---|---|
| WorkBuddy 里看不到 comfyui 工具 | 连接器管理右上角「自定义连接器」里对 `comfyui` 点**信任**，然后重启应用 |
| 工具报连接失败 | 跑 `status-comfyui.bat`；不在就 `start-comfyui.bat` |
| 启动失败 | 看 `logs\comfyui-headless.log` 尾部 |
| 换端口 | 改 `mcp.json` 里的 `COMFYUI_URL` |
| 提交后一直 `running`、`interrupt` 也停不掉 | 多半是 SageAttention 被打开而本机没 MSVC → 去掉 `--use-sage-attention`、清掉 `COMFY_USE_SAGE_ATTENTION` |
| 提交工作流被拒 `Prompt has no outputs` | 自定义节点漏了 `OUTPUT_NODE = True` |
| H3 节点提示未配置 API Key | 写 `E:\Comfy-Desktop\ComfyUI-Cache\minimax_key.txt`（单行纯文本） |
| 装了 H3 节点但 ComfyUI 里看不到 | 跑 `install-minimax-node.bat` 再重启后端；确认 `object_info/MiniMaxH3Video` 有返回 |

## 本机环境：把数据钉在 E 盘（`local-env/`）

本机强制要求所有文件落 E 盘，而 WorkBuddy / CodeBuddy / pip / npm 都把数据路径**写死在 C 盘**。
`local-env/` 用 NTFS 目录联接（junction）解决：C 盘保留原路径，但它只是 0 字节重解析点，
真实写入全部落到 E 盘 —— **所以不需要改任何配置里的路径**。

- 运行时对外路径 `E:\WBData\_tools\` 本身是一个**联结**，指向本仓库的 `local-env/`。
  这样脚本只有一份（不会出现「仓库一份、运行一份」的漂移），而启动项里写死的
  `E:\WBData\_tools\guard.ps1` 照常命中。
  换机重建：`mklink /J E:\WBData\_tools E:\ComfyUI-MCP\local-env`
- `guard.ps1` 挂在登录启动项，每次登录做两件事：① 把被打回真实目录的映射重新挂成联结；
  ② 把 `settings.json` 的 `autoLaunchDesired` 改回 `false`，并删掉注册表 Run 里的自启值。
- **联结会被周期性破坏**（实测 19:03 还是联结、00:15 已变回真实目录），
  所以这个登录守卫不是冗余、是命脉；长期不注销/重启就会漏，C 盘会重新被写。
- 审计当前状态（只读，不改任何东西）：`python E:\WBData\_tools\audit_links.py`
- 完整映射表、安全约束、踩坑见 `local-env/使用说明.md`。

`skills/` 是 `C:\Users\legion\.workbuddy\skills` 的副本（那边才是 WorkBuddy 实际读取的位置），
给这几套方法论留一份版本化存档。

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
7. **本机的 HTTP 代理环境变量会把 `127.0.0.1` 一起代理掉** —— Python 探活/调本地 ComfyUI 时
   必须 `urllib.request.build_opener(urllib.request.ProxyHandler({}))` 显式绕过，
   否则报的是「连不上」，看起来像服务没起。
8. **改完自定义节点必须重启 ComfyUI 才会加载**（`custom_nodes` 下有 `__pycache__` 不影响）；
   验证方式是 `GET /object_info/<节点名>`，不是看日志。
9. 同一个会话提交的工作流，如果**历史里拿不到产物**，先看 `outputs` 里有没有带
   `filename/subfolder/type` 的列表 —— MCP 只认这个结构，节点光返回文件路径没用。

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
7. 双击 `install-minimax-node.bat`，把 MiniMax H3 自定义节点同步进 ComfyUI 的 `custom_nodes`
8. 双击 `start-comfyui.bat` 预热后端，然后在对话里说「用 ComfyUI 画一张……」
9. 回归自检：`GEN=1 .\.venv\Scripts\python.exe tools\mcp_selftest.py`

## 实测记录

**2026-09-15（接入）**

- 端到端 MCP 握手通过，17 个工具全部可见。
- `generate_image` 出图成功 → `ComfyUI_00001_.png`（512×512，386 KB）。
- **含拉起 ComfyUI 后端在内，全程 29 秒**；后端已预热时握手是秒级的。
- 冷启动 ComfyUI 约 60 秒（首次），缓存热后约 15–20 秒。

**2026-09-15（自定义工作流）**

- 新增 `douyin_cover` 后工具数 **17 → 18**，MCP 端到端再次通过。
- 单张 3:4 竖版（864×1152，含 hires fix）**14–17 秒**，
  GPU = RTX 4060 Laptop / 8.6 GB，SD1.5、28+12 步。
- 题材适配结论见上文表格（氛围/剪影/水墨好，动物/科技抽象差）。
- `COMFY_MCP_WORKFLOW_DIR` 由 `comfyui-mcp-server\workflows` 改为 `E:\ComfyUI-MCP\workflows`。

**2026-09-16（MiniMax H3 + SageAttention）**

- 新增自定义节点 `ComfyUI-MiniMax-H3-API`（直连 `api.minimaxi.com`），
  ComfyUI 0.28.0 里 `object_info` 两个节点均注册成功。
- 新增工作流 `minimax_h3_video` / `minimax_h3_i2v`，工具数 **18 → 20**。
- **端到端零成本验证通过**：直接向 `/prompt` 提交工作流 → 受理 → 节点执行到「调用 API 前一步」
  → 返回清晰提示。**链路全通，只差 API Key。**
- 补上 `OUTPUT_NODE = True` 才被 ComfyUI 接受（否则 `Prompt has no outputs`，HTTP 400）。
- SageAttention 装上但**默认关闭**：triton 缺预编译 `cuda_utils.pyd`、JIT 需要 MSVC，
  本机没有 → 出图卡死（>180s）；关闭后同任务 3.0 秒。
- 实测数据全部来自 **RTX 4060 Laptop / 8.6 GB / ComfyUI 0.28.0 / torch 2.12.1+cu130**。

**2026-09-16（休眠：把用不上的都关掉）**

- ComfyUI 后端进程（2 个 python，约 1 GB）已关闭，8188 端口释放。
- WorkBuddy 侧 `comfyui` MCP **已注销**（`mcp.json` → `{"mcpServers": {}}`）：
  它带 `COMFYUI_AUTOSTART=1`，只要 WorkBuddy 一用这个 MCP 就会**自动拉起 ComfyUI 后端**，
  在等 API key 的阶段纯属白占内存。随时可按「从零重建」第 4–5 步装回来。
- 清掉僵尸文件 `logs\comfyui-headless.pid`（5 B，指向已死进程）与 `.log.prev`。
- 附带：`E:\Temp` 清理 139.2 MB（只删 24 小时前的）；`~/.workbuddy/mcp.json` 现为空。
- 结论：**代码和配置全部保留在仓库，只是不跑**。等 MiniMax H3 的 API key 到位再启动。
