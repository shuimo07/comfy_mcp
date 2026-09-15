# ComfyUI-MiniMax-H3-API

直连 **MiniMax H3 官方开放平台 API** 的 ComfyUI 节点。本地不加载模型、不占显存，
只发 HTTP 请求 + 下载成片，所以 4060 笔记本（8G 显存）也能出 2K 带原生音效的视频。

## 为什么不用 ComfyUI 自带的 MiniMax 节点

ComfyUI 自带 `comfy_api_nodes/nodes_minimax.py` 里确实有 MiniMax 节点，但它：

- 走 `/proxy/minimax/...`（**ComfyUI 官方后端中转**），鉴权是 `auth_token_comfy_org` /
  `api_key_comfy_org` —— 必须买 **Comfy 官方积分**，**不能填你自己的 MiniMax Key**；
- 模型枚举只到 `MiniMax-Hailuo-02` / `T2V-01` 那一代，**没有 H3**。

所以要「用自己的 Key 直接调 H3」，只能自建节点 —— 就是这个包。

## 装了之后得到什么

分类 `MiniMax H3 / API` 下两个节点：

| 节点 | 用途 |
|---|---|
| `MiniMax H3 视频生成 (API)` | 文生视频 / 首帧图生视频 / 首尾帧过渡 |
| `MiniMax H3 参考生视频 (API)` | 参考图 + 参考视频 + 参考音频 → 角色·动作·镜头·音色一致 |

输出三个：`video_path`（本地 mp4 绝对路径）、`download_url`（MiniMax 临时地址）、`task_id`（排查用）。
mp4 会落到 `ComfyUI/output/minimax_h3/`，节点还会返回 ComfyUI 标准的 `ui.videos`，
所以**界面能直接预览，MCP 也能按 `videos` key 取回产物**。

## 配置 API Key（三选一，优先级从高到低）

1. 节点上的 `api_key` 输入框直接填（临时，不落盘）；
2. 环境变量 `MINIMAX_API_KEY`；
3. 把 key 写进 `E:\Comfy-Desktop\ComfyUI-Cache\minimax_key.txt`（**单行纯文本，推荐**，一次配好全流程通用）。

Key 获取：<https://platform.minimaxi.com> → 账户管理 → API Keys。

> 第 3 种方式在 ComfyUI 每次启动时生效；改完 key 不用重启，节点是运行时读取的。

## 参数说明

| 参数 | 说明 |
|---|---|
| `region` | `cn` = `api.minimaxi.com`（国内，推荐）；`global` = `api.minimax.io` |
| `duration` | 4~15 秒，**仅整数** |
| `resolution` | `768P` 或 `2K`（2K 单价约 1.6 倍） |
| `ratio` | `16:9` `9:16` `1:1` `4:3` `3:4` `21:9` `adaptive`。**纯文生视频必须选非 adaptive**；接了图则由图片决定，节点会自动改成 `adaptive` |
| `poll_interval` | 轮询间隔，官方建议 10 秒 |
| `timeout` | 最长等待秒数，默认 1800 |
| `run_nonce` | 只是用来绕过 ComfyUI 缓存强制重新生成，**不发给 API** |

关于缓存：ComfyUI 会按节点输入做缓存，输入没变时重复执行会**直接复用上次结果、不再花钱**。
想强制重出，把 `run_nonce` 改个数字。

## 费用（2026-09 参考，以官网为准）

- 768P 约 ¥0.50/秒 → 5 秒≈¥2.5
- 2K 约 ¥0.80/秒 → 5 秒≈¥4
- 参考图首 5 张不计费；参考视频按自身时长**额外**计费

## 对接 ComfyUI-MCP

`E:\ComfyUI-MCP\workflows\` 下已放好两个工作流，MCP 会自动注册成工具：

- `minimax_h3_video.json` → 工具 `minimax_h3_video(prompt, duration)`
- `minimax_h3_i2v.json` → 工具 `minimax_h3_i2v(image, prompt, duration)`

注意：H3 出片通常要 1~5 分钟，而 MCP 客户端等待窗口有限（约 30 秒后会返回
`status: running` 的任务句柄）。这时用任务查询工具按 `prompt_id` 取回结果即可，
不要去重复提交，否则会重复计费。

## 已知边界

- 参考视频/音频走本地文件时会转成 base64，单文件上限 50MB / 15MB，且整体请求体上限 64MB；
  **大素材建议直接填公网 URL**（`reference_video_url` / `reference_audio_url`）。
- 首帧/尾帧与参考素材**不能混用**，官方限制。
- 任务只能查最近 7 天。
