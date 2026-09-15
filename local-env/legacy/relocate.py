"""安全搬迁 C: -> E:，并留下 junction 让原路径继续可用。

算法（与 guard-core.ps1 的 Ensure-Junction 等价，但能在前台安全执行）：

    1. 创建目标目录
    2. 目标已存在且源是 junction  -> 已完成，跳过
    3. robocopy 源 -> 目标（/E，不删源）
    4. 核对：目标文件数 < 源文件数 -> 中止，源不动
    5. 删除源目录；删不掉（有句柄占用）-> 中止，源不动、目标保留
    6. mklink /J 建 junction
    7. 复核 junction 可读

任何一步不确定都**中止，绝不在核对完成前删源**。

用法:
    python relocate.py --check
    python relocate.py <C源路径> <E目标路径> [--dry]
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time


def count_files(p: str) -> int:
    n = 0
    for _dp, _dn, fn in os.walk(p, onerror=lambda e: None):
        n += len(fn)
    return n


def is_reparse(p: str) -> bool:
    try:
        st = os.stat(p, follow_symlinks=False)
        return bool(getattr(st, "st_file_attributes", 0) & 0x400)
    except OSError:
        return False


def junction_target(p: str) -> str:
    """读取已存在 junction 的指向（PowerShell 取，最可靠）。"""
    ps = (f"$i = Get-Item -LiteralPath '{p}' -Force; "
          "Write-Output ($i.Target -join '')")
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                       capture_output=True, text=True)
    return (r.stdout or "").strip()


def make_junction(src: str, dst: str) -> tuple[bool, str]:
    r = subprocess.run(["cmd", "/c", "mklink", "/J", src, dst],
                       capture_output=True, text=True,
                       encoding="gbk", errors="replace")
    out = ((r.stdout or "") + (r.stderr or "")).strip()
    return r.returncode == 0, out


def human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} PB"


def dir_size(p: str) -> int:
    t = 0
    for dp, _dn, fn in os.walk(p, onerror=lambda e: None):
        for f in fn:
            try:
                t += os.path.getsize(os.path.join(dp, f))
            except OSError:
                pass
    return t


def relocate(src: str, dst: str, dry: bool = False) -> str:
    print(f"\n=== {src}")
    print(f"    -> {dst}")

    if not os.path.exists(src):
        print("    源不存在，跳过")
        return "missing"

    if is_reparse(src):
        print(f"    源已是 junction -> {junction_target(src)}  ✔ 跳过")
        return "already"

    if os.path.exists(dst) and not is_reparse(dst):
        # 目标已有真实数据：当成断点续传，不删
        print(f"    目标已存在（{count_files(dst)} 文件），将增量同步后再判断")

    sc = count_files(src)
    ss = dir_size(src)
    print(f"    源: {sc} 文件 / {human(ss)}")

    if dry:
        print("    [dry-run] 不执行")
        return "dry"

    os.makedirs(dst, exist_ok=True)

    print("    robocopy 中 ...")
    t0 = time.time()
    r = subprocess.run(
        ["robocopy", src, dst, "/E", "/COPY:DAT", "/DCOPY:DAT",
         "/R:2", "/W:1", "/NFL", "/NDL", "/NP", "/MT:8"],
        capture_output=True, text=True, encoding="gbk", errors="replace")
    if r.returncode >= 8:
        print(f"    !! robocopy 退出码 {r.returncode}，中止（源不动）")
        print("       " + (r.stdout or r.stderr or "")[-600:])
        return "copy-failed"
    print(f"    拷贝完成，用时 {time.time() - t0:.1f}s")

    dc = count_files(dst)
    print(f"    核对: 源 {sc} -> 目标 {dc}")
    if dc < sc:
        print("    !! 目标文件数少于源，中止（源不动）")
        return "verify-failed"

    try:
        shutil.rmtree(src)
    except OSError as e:
        print(f"    !! 无法删除源（可能被占用）: {e}")
        print("       已完成拷贝，源保留。关掉占用进程后可重跑本命令。")
        return "locked"

    if os.path.exists(src):
        print("    !! 源仍然存在，中止")
        return "locked"

    ok, msg = make_junction(src, dst)
    if not ok:
        print(f"    !! junction 创建失败: {msg}")
        print(f"       !! 数据在 {dst}，源目录已不存在，请手动: mklink /J \"{src}\" \"{dst}\"")
        return "junction-failed"
    print(f"    junction 建好: {msg}")

    if os.path.exists(os.path.join(src, ".")) and count_files(src) == dc:
        print(f"    ✔ 复核通过（通过 {src} 可读到 {count_files(src)} 文件）")
        return "ok"
    print("    !! 复核异常，请人工确认")
    return "verify-odd"


TARGETS = [
    # (C 源, E 目标, 说明)
    (r"C:\Users\legion\.cache",
     r"E:\WBData\home\.cache", "CLI 运行时缓存 (codex-runtimes 等)"),
    (r"C:\Users\legion\npm-cache",
     r"E:\WBData\home\npm-cache", "npm 缓存"),
    (r"C:\Users\legion\AppData\Local\pip\cache",
     r"E:\WBData\local\pip-cache", "pip 缓存"),
    (r"C:\Users\legion\AppData\Roaming\npm",
     r"E:\WBData\roaming\npm", "npm 全局包"),
]


def cmd_check() -> None:
    print("=" * 68)
    print("待搬迁清单")
    print("=" * 68)
    total = 0
    for src, dst, desc in TARGETS:
        if not os.path.exists(src):
            print(f"  [跳过] 不存在      {src}")
            continue
        if is_reparse(src):
            print(f"  [已完成] junction  {src} -> {junction_target(src)}")
            continue
        s = dir_size(src)
        total += s
        print(f"  {human(s):>10}  {desc:<28} {src}")
    print(f"\n  合计: {human(total)}")


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry" in sys.argv

    if not args or sys.argv[1] == "--check":
        cmd_check()
        return 0

    if len(args) != 2:
        print(__doc__)
        return 1

    rc = relocate(args[0], args[1], dry)
    return 0 if rc in ("ok", "already", "dry", "missing") else 2


if __name__ == "__main__":
    raise SystemExit(main())
