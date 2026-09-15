"""把 PowerShell 脚本从「无 BOM 的 UTF-8 / LF」转成「UTF-8 with BOM / CRLF」。

为什么必须这么做：
  Windows PowerShell 5.1 读取**没有 BOM** 的 .ps1 时，会按系统 ANSI 代码页
  （本机是 GBK/936）解码，而不是 UTF-8。于是脚本里的中文注释会变成乱码，
  轻则乱码、重则直接报「意外的标记」语法错误。加 BOM 后 PS 5.1 才会按 UTF-8 读。
"""

import os
import shutil
import time

TARGETS = [
    "E:" + chr(92) + r"WBData\_tools\guard-core.ps1",
    "E:" + chr(92) + r"WBData\_tools\guard.ps1",
]

for p in TARGETS:
    raw = open(p, "rb").read()
    has_bom = raw[:3] == b"\xef\xbb\xbf"
    text = raw.decode("utf-8-sig")
    # 统一成 CRLF
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\r\n")
    # 先备份一份，便于出问题时回滚
    bak = p + ".bak"
    if not os.path.exists(bak):
        shutil.copy2(p, bak)
    with open(p, "wb") as f:
        f.write(b"\xef\xbb\xbf" + text.encode("utf-8"))

    new = open(p, "rb").read()
    print("%s" % p)
    print("   原: BOM=%s  ->  现: BOM=%s  字节 %d -> %d"
          % (has_bom, new[:3] == b"\xef\xbb\xbf", len(raw), len(new)))
    # 剔除 ASCII 之外的内容前先确认中文还在
    nonascii = sum(1 for c in text if ord(c) > 127)
    print("   非 ASCII 字符数: %d（中文注释保留）" % nonascii)
