# -*- coding: utf-8 -*-
"""审计 C 盘 -> E 盘的 junction 映射现状（只读，不修改任何东西）。

用法:
    python audit_links.py            # 审计 guard.ps1 里登记的映射
    python audit_links.py <路径> ... # 审计任意路径

判断 junction 必须用 st_file_attributes & 0x400 (FILE_ATTRIBUTE_REPARSE_POINT)，
不能用 os.path.islink() —— 它识别不了 Windows junction，会返回 False。
"""
import os
import subprocess
import sys

ATTR_REPARSE = 0x400

# guard.ps1 $maps 里登记的映射（源 -> 期望目标）
EXPECTED = [
    # 2026-09-18: C:\Users\legion\.workbuddy 的「根目录」仍然不能做成 junction
    # （它是 WorkBuddy 的 live home，运行中的会话与解释器都在里面，根句柄锁死）。
    # 新策略：改为「每个子目录各自 junction 到 E:\WBData\home\.workbuddy\<同名>」，
    # 由下面的 expand_workbuddy() 动态展开，不写死清单（新增子目录会自动纳入）。
    # 见 guard.ps1「subdirectory migration」章节。
    (r"C:\Users\legion\.codebuddy", r"E:\WBData\home\.codebuddy"),
    (r"C:\Users\legion\.workbuddy-key-fallback", r"E:\WBData\home\.workbuddy-key-fallback"),
    (r"C:\Users\legion\.cache", r"E:\WBData\home\.cache"),
    (r"C:\Users\legion\AppData\Local\pip\cache", r"E:\WBData\local\pip-cache"),
    (r"C:\Users\legion\AppData\Roaming\npm", r"E:\WBData\roaming\npm"),
    (r"C:\Users\legion\AppData\Roaming\WorkBuddy", r"E:\WBData\roaming\WorkBuddy"),
    (r"C:\Users\legion\WorkBuddy", r"E:\WorkBuddy"),
    # 2026-09-16 新增：WorkBuddy 桌面版更新器下载缓存（installer.exe，单个 500MB+，纯缓存）
    (r"C:\Users\legion\AppData\Local\@genieworkbuddy-desktop-updater",
     r"E:\WBData\local\genieworkbuddy-updater"),
    # 2026-09-16 新增：ComfyUI Desktop 的 C 盘落点（更新器安装包 150MB+ / Roaming 配置与日志）
    (r"C:\Users\legion\AppData\Local\comfyui-desktop-2-updater",
     r"E:\WBData\local\comfyui-desktop-2-updater"),
    (r"C:\Users\legion\AppData\Roaming\Comfy Desktop",
     r"E:\WBData\roaming\ComfyDesktop"),
    # 2026-09-18 新增：Power BI Desktop 运行缓存（WebView2 profile + 各类 Cache，
    # 约 300MB / 1500 文件）。跑一次 PBI 就往 C 盘写一次，纯缓存。
    (r"C:\Users\legion\AppData\Local\Microsoft\Power BI Desktop",
     r"E:\WBData\local\PowerBI-Desktop"),
]


def junction_target(path):
    """返回 junction 的 Target，非 junction 返回 None。"""
    try:
        st = os.stat(path, follow_symlinks=False)
    except OSError:
        return None
    if not (getattr(st, "st_file_attributes", 0) & ATTR_REPARSE):
        return None
    # 用 dir /AL 取 Target 最稳（Python 无直接 API）
    d = os.path.dirname(path)
    n = os.path.basename(path)
    try:
        out = subprocess.run(
            ["cmd", "/c", "dir", "/AL", d],
            capture_output=True, timeout=60,
        ).stdout
    except Exception:
        return "<?>"
    for raw in out.splitlines():
        try:
            line = raw.decode("gbk", "replace")
        except Exception:
            line = str(raw)
        if n in line and ("[" in line and "]" in line):
            tgt = line[line.rfind("[") + 1:line.rfind("]")]
            # 去掉内核路径前缀 \\?\ 和 \??\
            for pre in ("\\\\?\\", "\\??\\"):
                if tgt.startswith(pre):
                    tgt = tgt[len(pre):]
            return tgt
    return "<?>"


def count(path, cap=None):
    """返回 (文件数, 字节数, 是否被截断)。"""
    nf = 0
    nb = 0
    if not os.path.exists(path):
        return 0, 0, False
    for dp, dn, fn in os.walk(path, onerror=lambda e: None):
        nf += len(fn)
        for f in fn:
            try:
                nb += os.path.getsize(os.path.join(dp, f))
            except OSError:
                pass
        if cap and nf >= cap:
            return nf, nb, True
    return nf, nb, False


def expand_workbuddy():
    """动态展开 C:\\Users\\legion\\.workbuddy 的每个子目录 -> E 盘对应位置。"""
    wb = r"C:\Users\legion\.workbuddy"
    wb_dst = r"E:\WBData\home\.workbuddy"
    out = []
    if not os.path.isdir(wb):
        return out
    for n in sorted(os.listdir(wb)):
        if any(m in n for m in ("__old", "__probe", "__movetest")):
            continue
        p = os.path.join(wb, n)
        if os.path.isdir(p):
            out.append((p, os.path.join(wb_dst, n)))
    return out


def main():
    pairs = list(EXPECTED) + expand_workbuddy()
    if len(sys.argv) > 1:
        pairs = [(p, None) for p in sys.argv[1:]]

    ok = 0
    pending = []
    print("=" * 78)
    print("%-46s %s" % ("路径", "状态"))
    print("=" * 78)
    for src, want in pairs:
        exists = os.path.lexists(src)
        if not exists:
            print("%-46s %s" % (src, "缺失"))
            pending.append((src, want, "缺失"))
            continue
        tgt = junction_target(src)
        if tgt:
            mark = "OK"
            if want and tgt.rstrip("\\").lower() != want.rstrip("\\").lower():
                mark = "目标不符(期望 %s)" % want
            ok += 1
            print("%-46s junction -> %s   [%s]" % (src, tgt, mark))
        else:
            nf, nb, _ = count(src, cap=200000)
            print("%-46s 真实目录 (未迁移) %d 文件 / %.2f GB" % (src, nf, nb / 2**30))
            pending.append((src, want, "%d 文件 / %.2f GB" % (nf, nb / 2**30)))

    print("=" * 78)
    print("已就位 junction: %d 个" % ok)
    if pending:
        print("待迁移: %d 个" % len(pending))
        for src, want, why in pending:
            print("   - %s  (%s)" % (src, why))
    else:
        print("全部已迁移完成 ✔")


if __name__ == "__main__":
    main()
