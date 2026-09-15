# -*- coding: utf-8 -*-
"""下载 ComfyUI checkpoint 到 E 盘 Shared models 目录（支持断点续传）。"""
from __future__ import annotations

import os
import ssl
import sys
import time
import urllib.request
from pathlib import Path

DEST_DIR = Path(r"E:\Comfy-Desktop\ComfyUI-Shared\models\checkpoints")
URL = ("https://huggingface.co/Comfy-Org/stable-diffusion-v1-5-archive"
       "/resolve/main/v1-5-pruned-emaonly-fp16.safetensors")
NAME = "v1-5-pruned-emaonly-fp16.safetensors"

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def remote_size() -> int:
    req = urllib.request.Request(URL, method="HEAD")
    with urllib.request.urlopen(req, timeout=60, context=ctx) as r:
        return int(r.headers.get("Content-Length", 0))


def main() -> int:
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    dest = DEST_DIR / NAME
    tmp = DEST_DIR / (NAME + ".part")

    total = remote_size()
    print(f"远端大小: {total/1e9:.3f} GB -> {dest}", flush=True)
    if dest.exists() and dest.stat().st_size == total:
        print("已存在且完整，跳过。", flush=True)
        return 0

    done = tmp.stat().st_size if tmp.exists() else 0
    if done and done >= total:
        tmp.replace(dest)
        print("续传文件已完整，改名完成。", flush=True)
        return 0

    headers = {"Range": f"bytes={done}-"} if done else {}
    if done:
        print(f"断点续传，从 {done/1e6:.1f} MB 继续", flush=True)

    req = urllib.request.Request(URL, headers=headers)
    started = time.time()
    last = started
    with urllib.request.urlopen(req, timeout=120, context=ctx) as r, open(tmp, "ab") as f:
        while True:
            chunk = r.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            now = time.time()
            if now - last >= 5:
                speed = done / max(now - started, 0.1) / 1e6
                pct = done / total * 100 if total else 0
                print(f"  {done/1e6:8.1f} / {total/1e6:.1f} MB  ({pct:5.1f}%)  {speed:6.1f} MB/s",
                      flush=True)
                last = now

    if total and tmp.stat().st_size != total:
        print(f"!! 大小不符: {tmp.stat().st_size} != {total}", flush=True)
        return 1
    tmp.replace(dest)
    print(f"完成: {dest}  ({dest.stat().st_size/1e9:.3f} GB)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
