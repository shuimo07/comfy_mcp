"""
MiniMax H3 视频生成 —— 直连 MiniMax 开放平台官方 API。

为什么不直接用 ComfyUI 自带的 MiniMax 节点：
  自带节点走的是 /proxy/minimax/...（ComfyUI 官方后端中转），鉴权用
  auth_token_comfy_org / api_key_comfy_org，也就是必须买 Comfy 官方积分；
  它既不能填你自己的 MiniMax Key，模型枚举也只到 MiniMax-Hailuo-02，没有 H3。
  所以要「用自己的 Key 直接调 H3」，只能自建节点 —— 就是本文件。

官方 API 规格（2026-09 核对）：
  POST {base}/v2/video_generation          创建异步任务 -> {"task_id": "..."}
  GET  {base}/v2/query/video_generation/{task_id}
                                           查询 -> {"task": {"status": ..., "content": {"url": ...}}}
  国内 base = https://api.minimaxi.com    海外 base = https://api.minimax.io
  请求体：{"model": "MiniMax-H3", "content": [...], "resolution": "768P"|"2K",
           "duration": 4~15, "ratio": "adaptive"|"16:9"|"9:16"|"1:1"|"4:3"|"3:4"|"21:9"}
  content 元素：{"type":"text","text":...}
                {"type":"image_url","image_url":{"url":...},"role":"first_frame"|"last_frame"|"reference_image"}
                {"type":"video_url","video_url":{"url":...},"role":"reference_video"}
                {"type":"audio_url","audio_url":{"url":...},"role":"reference_audio"}
  注意：纯文生视频（t2va）ratio 必填且不能是 adaptive；图生视频 ratio 恒为 adaptive。
        图片可直接传 base64 data URL，视频/音频建议传公网 URL（单个体积上限 50MB/15MB）。
"""

import base64
import io
import json
import os
import time
import urllib.error
import urllib.request

import numpy as np
from PIL import Image

try:  # 在 ComfyUI 里能拿到模型/output 目录
    import folder_paths
except Exception:  # 脱离 ComfyUI 单独跑时降级
    folder_paths = None


BASE_URLS = {
    "cn": "https://api.minimaxi.com",
    "global": "https://api.minimax.io",
}
MODEL_ID = "MiniMax-H3"
RATIOS = ["adaptive", "16:9", "9:16", "1:1", "4:3", "3:4", "21:9"]

KEY_FILE = r"E:\Comfy-Desktop\ComfyUI-Cache\minimax_key.txt"
KEY_HINT = (
    "未找到 MiniMax API Key，三种填法任选其一：\n"
    "  1) 直接用本节点的 api_key 输入框填（临时、不落盘）；\n"
    "  2) 设环境变量 MINIMAX_API_KEY；\n"
    f"  3) 把 key 写进 {KEY_FILE}（单行纯文本，推荐，全流程通用）。\n"
    "Key 获取：https://platform.minimaxi.com → 账户管理 → API Keys"
)

_MIME = {
    ".mp4": "video/mp4", ".mov": "video/quicktime", ".webm": "video/webm",
    ".mp3": "audio/mpeg", ".wav": "audio/wav", ".m4a": "audio/mp4",
}


# --------------------------------------------------------------------------- #
# 工具函数
# --------------------------------------------------------------------------- #
def _resolve_key(explicit: str = "") -> str:
    if explicit and explicit.strip():
        return explicit.strip()
    env = os.environ.get("MINIMAX_API_KEY", "").strip()
    if env:
        return env
    here = os.path.join(os.path.dirname(os.path.abspath(__file__)), "minimax_key.txt")
    for path in (KEY_FILE, here):
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                k = f.read().strip()
            if k:
                return k
        except OSError:
            pass
    raise RuntimeError(KEY_HINT)


def _tensor_to_data_url(image, quality: int = 92, max_side: int = 2048) -> str:
    """ComfyUI 的 IMAGE 张量 [B,H,W,C] (0~1) -> JPEG base64 data URL。"""
    arr = image
    if hasattr(arr, "detach"):
        arr = arr.detach().cpu().numpy()
    arr = np.asarray(arr)
    if arr.ndim == 4:
        arr = arr[0]
    if arr.dtype != np.uint8:
        arr = np.clip(arr * 255.0, 0, 255).astype(np.uint8)
    im = Image.fromarray(arr).convert("RGB")
    if max_side and max(im.size) > max_side:
        r = max_side / float(max(im.size))
        im = im.resize((max(1, int(im.width * r)), max(1, int(im.height * r))), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=quality)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def _file_to_data_url(path: str, max_mb: float) -> str:
    path = (path or "").strip().strip('"')
    if not path:
        return None
    if not os.path.isfile(path):
        raise RuntimeError(f"参考素材文件不存在：{path}")
    size_mb = os.path.getsize(path) / 1048576.0
    if size_mb > max_mb:
        raise RuntimeError(
            f"参考素材 {os.path.basename(path)} 有 {size_mb:.1f}MB，超过 {max_mb}MB 上限。\n"
            "请改用公网可访问的 URL 传入（H3 支持直接吃 URL，也省去 base64 膨胀）。"
        )
    mime = _MIME.get(os.path.splitext(path)[1].lower(), "application/octet-stream")
    with open(path, "rb") as f:
        return f"data:{mime};base64," + base64.b64encode(f.read()).decode()


def _http_json(method: str, url: str, key: str, payload=None, timeout: int = 120):
    data = None
    headers = {"Authorization": f"Bearer {key}"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", "replace")
        except Exception:
            pass
        raise RuntimeError(f"MiniMax API HTTP {e.code} {url}\n{body[:800]}") from None
    except urllib.error.URLError as e:
        raise RuntimeError(f"请求 MiniMax API 失败（网络层）：{e.reason}\n{url}") from None


def _output_dir() -> str:
    if folder_paths is not None:
        try:
            return folder_paths.get_output_directory()
        except Exception:
            pass
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")


def _download(url: str, prefix: str = "minimax_h3", subfolder: str = "minimax_h3",
              timeout: int = 600):
    """下载成片到 ComfyUI output 目录。

    返回 (绝对路径, filename, subfolder)，后两者用于拼成 ComfyUI 的
    {"ui": {"videos": [...]}} 结构 —— 界面能直接预览，MCP 也能按
    videos/video/mp4 这些 key 取回产物。
    """
    out_dir = os.path.join(_output_dir(), subfolder)
    os.makedirs(out_dir, exist_ok=True)
    name = f"{prefix}_{time.strftime('%Y%m%d-%H%M%S')}.mp4"
    dest = os.path.join(out_dir, name)
    i = 1
    while os.path.exists(dest):
        name = f"{prefix}_{time.strftime('%Y%m%d-%H%M%S')}_{i}.mp4"
        dest = os.path.join(out_dir, name)
        i += 1
    req = urllib.request.Request(url, headers={"User-Agent": "ComfyUI-MiniMax-H3-API"})
    with urllib.request.urlopen(req, timeout=timeout) as resp, open(dest, "wb") as f:
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
    return dest, name, subfolder


def _node_return(path, name, subfolder, url, task_id):
    """ComfyUI 节点返回：ui 部分让界面预览 / MCP 能取回产物，result 部分正常往下游传。"""
    return {
        "ui": {"videos": [{"filename": name, "subfolder": subfolder, "type": "output"}]},
        "result": (path, url, task_id),
    }


def _submit_and_wait(base: str, payload: dict, key: str, poll_interval: int,
                     timeout: int, node=None, avg_seconds: int = 150):
    t0 = time.time()
    created = _http_json("POST", f"{base}/v2/video_generation", key, payload, timeout=180)
    task_id = created.get("task_id")
    if not task_id:
        raise RuntimeError(f"创建任务失败，未返回 task_id。响应：{json.dumps(created, ensure_ascii=False)[:800]}")

    bar = None
    if node is not None:
        try:
            import comfy.utils
            bar = comfy.utils.ProgressBar(100)
        except Exception:
            bar = None

    while True:
        if time.time() - t0 > timeout:
            raise RuntimeError(
                f"等待超时（{timeout}s）。任务可能仍在跑，可稍后用 task_id 手动查询：\n"
                f"  GET {base}/v2/query/video_generation/{task_id}\n"
                f"task_id = {task_id}"
            )
        time.sleep(max(3, int(poll_interval)))
        task = _http_json("GET", f"{base}/v2/query/video_generation/{task_id}", key, timeout=60).get("task", {})
        status = task.get("status", "?")
        elapsed = time.time() - t0
        if bar is not None:
            bar.update(min(99, int(elapsed / max(1, avg_seconds) * 100)))
        print(f"[MiniMax H3] {elapsed:6.0f}s  status={status}  task={task_id}")
        if status == "succeeded":
            url = (task.get("content") or {}).get("url")
            if not url:
                raise RuntimeError(f"任务成功但未返回下载地址：{json.dumps(task, ensure_ascii=False)[:600]}")
            return task_id, url, task
        if status in ("failed", "cancelled", "expired"):
            raise RuntimeError(
                f"生成失败：status={status}\n"
                f"error={json.dumps(task.get('error'), ensure_ascii=False)}\n"
                f"task_id={task_id}"
            )


# --------------------------------------------------------------------------- #
# 节点 1：文生视频 / 图生视频（首帧、尾帧、首尾帧）
# --------------------------------------------------------------------------- #
class MiniMaxH3Video:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": ("STRING", {
                    "multiline": True, "default": "",
                    "tooltip": "视频描述，≤7000 字符。可用 [镜头运动] 写运镜；H3 原生带音效，可在提示词里描述声音/台词。",
                }),
                "duration": ("INT", {"default": 5, "min": 4, "max": 15, "step": 1,
                                     "tooltip": "时长（秒），仅整数，4~15。"}),
                "resolution": (["768P", "2K"], {"default": "768P",
                                                 "tooltip": "768P 更便宜，2K 更贵（约 1.6 倍）。"}),
                "ratio": (RATIOS, {"default": "16:9",
                                   "tooltip": "画幅。纯文生视频必填且不能选 adaptive；接了图片则强制 adaptive（由图片决定）。"}),
                "region": (["cn", "global"], {"default": "cn",
                                              "tooltip": "cn = api.minimaxi.com（国内）；global = api.minimax.io。"}),
                "poll_interval": ("INT", {"default": 10, "min": 3, "max": 60, "step": 1,
                                          "tooltip": "轮询间隔（秒），官方建议 10s。"}),
                "timeout": ("INT", {"default": 1800, "min": 60, "max": 7200, "step": 60,
                                    "tooltip": "最长等待秒数。"}),
                "run_nonce": ("INT", {"default": 0, "min": 0, "max": 0xFFFFFFFFFFFFFFFF,
                                      "control_after_generate": True,
                                      "tooltip": "只是用来绕过 ComfyUI 缓存、强制重新生成，不发给 API。"}),
                "api_key": ("STRING", {"default": "", "multiline": False,
                                       "tooltip": "留空则依次读环境变量 MINIMAX_API_KEY、" + KEY_FILE}),
            },
            "optional": {
                "first_frame": ("IMAGE", {"tooltip": "首帧图。接了就是图生视频。"}),
                "last_frame": ("IMAGE", {"tooltip": "尾帧图（可选）。给首帧+尾帧就是首尾帧过渡模式。"}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("video_path", "download_url", "task_id")
    OUTPUT_TOOLTIPS = ("本地 mp4 路径（已存到 ComfyUI output 目录）",
                       "MiniMax 返回的临时下载地址（有时效）",
                       "任务 ID，可用于排查/复跑")
    FUNCTION = "generate"
    CATEGORY = "MiniMax H3 / API"
    # 标记为输出节点：本节点自带副作用（下载 mp4 到 output），
    # 不标记的话 ComfyUI 会以 "Prompt has no outputs" 拒绝执行。
    OUTPUT_NODE = True
    DESCRIPTION = "MiniMax H3 文生视频 / 首帧图生视频 / 首尾帧生视频（直连官方 API，本地不跑模型）"

    def generate(self, prompt, duration, resolution, ratio, region, poll_interval,
                 timeout, run_nonce, api_key,
                 first_frame=None, last_frame=None):
        key = _resolve_key(api_key)
        base = BASE_URLS.get(region, BASE_URLS["cn"])
        if not prompt or not prompt.strip():
            raise RuntimeError("prompt 不能为空 —— H3 要求 content 里必须有一个非空 text 项。")

        content = [{"type": "text", "text": prompt}]
        has_img = False
        if first_frame is not None:
            content.append({"type": "image_url",
                            "image_url": {"url": _tensor_to_data_url(first_frame)},
                            "role": "first_frame"})
            has_img = True
        if last_frame is not None:
            content.append({"type": "image_url",
                            "image_url": {"url": _tensor_to_data_url(last_frame)},
                            "role": "last_frame"})
            has_img = True

        payload = {
            "model": MODEL_ID,
            "content": content,
            "duration": int(duration),
            "resolution": resolution,
            "ratio": "adaptive" if has_img else (ratio if ratio != "adaptive" else "16:9"),
        }
        print(f"[MiniMax H3] 提交任务 resolution={resolution} duration={duration}s "
              f"ratio={payload['ratio']} images={sum(1 for c in content if c['type'] == 'image_url')}")

        task_id, url, task = _submit_and_wait(base, payload, key, poll_interval, timeout,
                                              node=self, avg_seconds=60 + 30 * int(duration))
        path = _download(url, prefix="minimax_h3")
        print(f"[MiniMax H3] 已保存 {path}  (usage={task.get('usage')})")
        return (path, url, task_id)


# --------------------------------------------------------------------------- #
# 节点 2：全能参考生视频（参考图 / 参考视频 / 参考音频 -> 角色·动作·音色一致）
# --------------------------------------------------------------------------- #
class MiniMaxH3ReferenceVideo:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": ("STRING", {
                    "multiline": True, "default": "",
                    "tooltip": "描述要生成的内容。可用「角色说话：<台词>」让 H3 按参考音色念台词。",
                }),
                "duration": ("INT", {"default": 5, "min": 4, "max": 15, "step": 1}),
                "resolution": (["768P", "2K"], {"default": "768P"}),
                "ratio": (RATIOS, {"default": "adaptive"}),
                "region": (["cn", "global"], {"default": "cn"}),
                "poll_interval": ("INT", {"default": 10, "min": 3, "max": 60, "step": 1}),
                "timeout": ("INT", {"default": 1800, "min": 60, "max": 7200, "step": 60}),
                "run_nonce": ("INT", {"default": 0, "min": 0, "max": 0xFFFFFFFFFFFFFFFF,
                                      "control_after_generate": True}),
                "api_key": ("STRING", {"default": "", "multiline": False}),
            },
            "optional": {
                "reference_image": ("IMAGE", {"tooltip": "参考图：人物/主体一致性来源。首 5 张参考图不计费。"}),
                "reference_video_path": ("STRING", {"default": "",
                                                    "tooltip": "参考视频本地路径（≤50MB）。大文件建议直接填公网 URL —— 见下方 url 输入。"}),
                "reference_audio_path": ("STRING", {"default": "",
                                                    "tooltip": "参考音频本地路径（≤15MB），用于指定音色。必须配参考图或参考视频。"}),
                "reference_image_url": ("STRING", {"default": "", "tooltip": "参考图公网 URL（优先于上面的图片输入）"}),
                "reference_video_url": ("STRING", {"default": "", "tooltip": "参考视频公网 URL（优先于本地路径）"}),
                "reference_audio_url": ("STRING", {"default": "", "tooltip": "参考音频公网 URL（优先于本地路径）"}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("video_path", "download_url", "task_id")
    FUNCTION = "generate"
    CATEGORY = "MiniMax H3 / API"
    DESCRIPTION = "MiniMax H3 全能参考生视频（参考图/视频/音频，可保角色、动作、镜头、音色一致）"

    def generate(self, prompt, duration, resolution, ratio, region, poll_interval,
                 timeout, run_nonce, api_key,
                 reference_image=None, reference_video_path="", reference_audio_path="",
                 reference_image_url="", reference_video_url="", reference_audio_url=""):
        key = _resolve_key(api_key)
        base = BASE_URLS.get(region, BASE_URLS["cn"])
        if not prompt or not prompt.strip():
            raise RuntimeError("prompt 不能为空 —— H3 要求 content 里必须有一个非空 text 项。")

        content = [{"type": "text", "text": prompt}]

        img_url = (reference_image_url or "").strip()
        if not img_url and reference_image is not None:
            img_url = _tensor_to_data_url(reference_image)
        if img_url:
            content.append({"type": "image_url", "image_url": {"url": img_url}, "role": "reference_image"})

        vid_url = (reference_video_url or "").strip() or _file_to_data_url(reference_video_path, 50)
        if vid_url:
            content.append({"type": "video_url", "video_url": {"url": vid_url}, "role": "reference_video"})

        aud_url = (reference_audio_url or "").strip() or _file_to_data_url(reference_audio_path, 15)
        if aud_url:
            if not (img_url or vid_url):
                raise RuntimeError("参考音频不能单独使用 —— 必须同时提供参考图或参考视频。")
            content.append({"type": "audio_url", "audio_url": {"url": aud_url}, "role": "reference_audio"})

        if len(content) == 1:
            raise RuntimeError("全能参考模式至少要给一个参考素材（图 / 视频 / 音频）；纯文生视频请用上面的节点。")

        payload = {
            "model": MODEL_ID,
            "content": content,
            "duration": int(duration),
            "resolution": resolution,
            "ratio": ratio,
        }
        print(f"[MiniMax H3] 提交参考生视频 素材数={len(content) - 1} resolution={resolution} duration={duration}s")

        task_id, url, task = _submit_and_wait(base, payload, key, poll_interval, timeout,
                                              node=self, avg_seconds=60 + 30 * int(duration))
        path, name, sub = _download(url, prefix="minimax_h3_ref")
        print(f"[MiniMax H3] 已保存 {path}  (usage={task.get('usage')})")
        return _node_return(path, name, sub, url, task_id)


NODE_CLASS_MAPPINGS = {
    "MiniMaxH3Video": MiniMaxH3Video,
    "MiniMaxH3ReferenceVideo": MiniMaxH3ReferenceVideo,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "MiniMaxH3Video": "MiniMax H3 视频生成 (API)",
    "MiniMaxH3ReferenceVideo": "MiniMax H3 参考生视频 (API)",
}
