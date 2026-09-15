# -*- coding: utf-8 -*-
"""把 .workbuddy 里陈旧的运行日志/追踪搬到 E 盘。

为什么不用 junction
-------------------
`.workbuddy` 的整体搬迁走的是登录守卫的 `robocopy /E /XJ`：
`/XJ` 会跳过源里的子联接，但源侧计数（Get-ChildItem -Recurse）仍会把它的内容算进去，
于是 `dst < src` 被判成「目标不完整」→ **整体搬迁永远 ABORT**。
所以 `.workbuddy` 内部一个子联接都不能挂，日志只能改用「搬陈旧文件」的方式。

安全策略
--------
逐个文件：复制到 E → 校验字节数一致 → 删源。
任何一步失败（典型是被进程占用）就**回滚已复制的那份**，源原样保留。
即要么整体成功、要么完全不动，不会出现「两边各一份」或「两边都没有」。

用法
----
    python archive_old_logs.py                # 默认搬 >2 小时未改动的
    python archive_old_logs.py --hours 24     # 只搬 >24 小时的
    python archive_old_logs.py --dry-run      # 只列出将要搬什么，不动任何文件
"""
import argparse
import ctypes
import os
import shutil
import time

WORKBUDDY = r"C:\Users\legion\.workbuddy"

# 源子目录 -> E 盘归档位置
MAP = {
    "logs": r"E:\WBData\home\.workbuddy-logs",
    "traces": r"E:\WBData\home\.workbuddy-traces",
}

k32 = ctypes.windll.kernel32
k32.DeleteFileW.argtypes = [ctypes.c_wchar_p]
k32.DeleteFileW.restype = ctypes.c_int


def move_one(src, dst, size):
    """复制→校验→删源；任一步失败则回滚。返回 True 表示真的搬走了。"""
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    try:
        shutil.copy2(src, dst)
    except Exception:
        return False
    if not os.path.exists(dst) or os.path.getsize(dst) != size:
        k32.DeleteFileW(dst)
        return False
    if k32.DeleteFileW(src):
        return True
    k32.DeleteFileW(dst)  # 删源失败（多半被占用）→ 回滚，不留重复副本
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=float, default=2.0,
                    help="只搬「超过这么多小时未改动」的文件（默认 2）")
    ap.add_argument("--dry-run", action="store_true", help="只列出，不搬")
    args = ap.parse_args()

    cut = time.time() - args.hours * 3600
    tot_moved = tot_bytes = tot_skip = tot_fail = 0

    for sub, dst_root in MAP.items():
        src_root = os.path.join(WORKBUDDY, sub)
        if not os.path.isdir(src_root):
            print("=== %s  (不存在，跳过)" % src_root)
            continue

        targets, skip = [], 0
        for cur, _dirs, files in os.walk(src_root):
            for f in files:
                fp = os.path.join(cur, f)
                try:
                    st = os.lstat(fp)
                except OSError:
                    continue
                if st.st_mtime >= cut:
                    skip += 1          # 还在写，绝不碰
                    continue
                targets.append((fp, os.path.relpath(fp, src_root), st.st_size))

        size_mb = sum(t[2] for t in targets) / 1048576
        print("=== %s" % src_root)
        print("    候选 %d 个 / %.1f MB ；跳过活跃文件 %d 个" % (len(targets), size_mb, skip))
        if args.dry_run:
            for fp, rel, sz in targets[:20]:
                print("      %9.1f MB  %s" % (sz / 1048576, rel))
            if len(targets) > 20:
                print("      ... 共 %d 个" % len(targets))
            tot_skip += skip
            continue

        m = b = fail = 0
        for fp, rel, sz in targets:
            if move_one(fp, os.path.join(dst_root, rel), sz):
                m += 1
                b += sz
            else:
                fail += 1
        print("    已搬到 E: %d 个 / %.1f MB ；被占用未搬 %d 个" % (m, b / 1048576, fail))
        tot_moved += m
        tot_bytes += b
        tot_skip += skip
        tot_fail += fail

    print()
    print("合计：搬到 E %d 个 / %.1f MB ；未搬 活跃 %d 个、被占用 %d 个"
          % (tot_moved, tot_bytes / 1048576, tot_skip, tot_fail))


if __name__ == "__main__":
    main()
