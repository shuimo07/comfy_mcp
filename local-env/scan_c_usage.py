# -*- coding: utf-8 -*-
"""定向扫描本次任务的 C 盘占用。避免递归超大目录。"""
import os, stat, sys, traceback
from datetime import datetime

OUT = r"E:\WBData\_tools\_scan_c_report.txt"
TODAY = datetime(2026, 9, 18).date()
R = []
def w(s=""):
    R.append(str(s))

def reparse(p):
    try:
        return bool(os.lstat(p).st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)
    except Exception:
        return None

def link_to(p):
    try:
        return os.readlink(p)
    except Exception as e:
        return "<%s>" % e

def h(n):
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return "%.1f %s" % (n, u)
        n /= 1024.0
    return "%.1f PB" % n

def measure(p, cap_files=40000, max_depth=6):
    """受控递归：返回 (bytes, files, truncated)"""
    if reparse(p):
        return (0, 0, True)
    tot = 0
    n = 0
    base = os.path.abspath(p).rstrip("\\").count("\\")
    for root, dirs, files in os.walk(p, onerror=lambda e: None):
        if root.count("\\") - base >= max_depth:
            dirs[:] = []
        else:
            dirs[:] = [d for d in dirs if not reparse(os.path.join(root, d))]
        for f in files:
            try:
                tot += os.path.getsize(os.path.join(root, f))
                n += 1
            except Exception:
                pass
            if n >= cap_files:
                return (tot, n, True)
    return (tot, n, False)

def newest_in(p, cap=40000, max_depth=6):
    """返回 (今日修改文件数, 最新时间戳)"""
    if reparse(p):
        return (0, 0)
    cnt = 0
    newest = 0
    n = 0
    base = os.path.abspath(p).rstrip("\\").count("\\")
    for root, dirs, files in os.walk(p, onerror=lambda e: None):
        if root.count("\\") - base >= max_depth:
            dirs[:] = []
        else:
            dirs[:] = [d for d in dirs if not reparse(os.path.join(root, d))]
        for f in files:
            n += 1
            if n > cap:
                return (cnt, newest)
            try:
                m = os.path.getmtime(os.path.join(root, f))
            except Exception:
                continue
            if datetime.fromtimestamp(m).date() == TODAY:
                cnt += 1
                if m > newest:
                    newest = m
    return (cnt, newest)


try:
    w("=" * 78)
    w("C 盘占用扫描  %s" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    w("=" * 78)

    # ---- 1. 关键目录形态 ----
    w("")
    w("【1】关键目录形态")
    w("-" * 78)
    for p in [r"C:\Users\legion\.workbuddy",
              r"C:\Users\legion\WorkBuddy",
              r"C:\Users\legion\.cache",
              r"C:\Users\legion\AppData\Local\pip\cache",
              r"C:\Users\legion\AppData\Roaming\npm"]:
        rp = reparse(p)
        if rp is None:
            w("%-56s [不存在]" % p)
        elif rp:
            w("%-56s [联接] -> %s" % (p, link_to(p)))
        else:
            w("%-56s [真实目录]" % p)

    # ---- 1b. .workbuddy 一层子项 ----
    w("")
    w("【1b】C:\\Users\\legion\\.workbuddy 下的一层子项（只看形态，不递归算大小）")
    w("-" * 78)
    wb = r"C:\Users\legion\.workbuddy"
    real_sub = []
    try:
        for name in sorted(os.listdir(wb)):
            p = os.path.join(wb, name)
            rp = reparse(p)
            if rp:
                w("  %-38s [联接] -> %s" % (name, link_to(p)))
            elif rp is False:
                if os.path.isdir(p):
                    real_sub.append(p)
                    w("  %-38s [真实目录]  <<< 占 C 盘" % name)
                else:
                    w("  %-38s [文件] %s" % (name, h(os.path.getsize(p))))
    except Exception as e:
        w("  枚举失败: %s" % e)
    w("")
    w("  真实目录逐个测大小（受控深度/文件数上限）：")
    for p in real_sub:
        try:
            s, n, tr = measure(p)
            w("    %-36s %10s / %d 文件%s" % (os.path.basename(p), h(s), n, "  (已截断)" if tr else ""))
        except Exception as e:
            w("    %-36s 失败 %s" % (os.path.basename(p), e))

    # ---- 2. 桌面源数据 ----
    w("")
    w("【2】桌面源数据（本次引用的表格）")
    w("-" * 78)
    DESK = r"C:\Users\legion\Desktop"
    tot = 0
    try:
        for name in sorted(os.listdir(DESK)):
            if name.lower().endswith((".xlsx", ".xls", ".csv")):
                p = os.path.join(DESK, name)
                try:
                    sz = os.path.getsize(p)
                    tot += sz
                    w("  %-36s %9s  改:%s  建:%s" % (
                        name, h(sz),
                        datetime.fromtimestamp(os.path.getmtime(p)).strftime("%m-%d %H:%M"),
                        datetime.fromtimestamp(os.path.getctime(p)).strftime("%m-%d %H:%M")))
                except Exception as e:
                    w("  %-36s <%s>" % (name, e))
    except Exception as e:
        w("  枚举失败: %s" % e)
    w("  桌面表格合计: %s" % h(tot))

    # ---- 3. Power BI 缓存 ----
    w("")
    w("【3】Power BI Desktop 运行缓存（C 盘）")
    w("-" * 78)
    for p in [r"C:\Users\legion\AppData\Local\Microsoft\Power BI Desktop",
              r"C:\Users\legion\AppData\Local\Microsoft\Power BI Desktop Store App",
              r"C:\Users\legion\AppData\Roaming\Microsoft\Power BI Desktop"]:
        if not os.path.exists(p):
            w("%s  [不存在]" % p)
            continue
        s, n, tr = measure(p)
        w("%s" % p)
        w("   合计 %s / %d 文件%s" % (h(s), n, "  (已截断)" if tr else ""))
        try:
            subs = []
            for name in os.listdir(p):
                sp = os.path.join(p, name)
                if os.path.isdir(sp) and not reparse(sp):
                    ss, nn, _ = measure(sp, cap_files=8000, max_depth=4)
                    subs.append((ss, name, nn))
            subs.sort(reverse=True)
            for ss, name, nn in subs[:12]:
                w("     %-42s %10s / %d" % (name, h(ss), nn))
        except Exception as e:
            w("     子项枚举失败: %s" % e)

    # ---- 4. 今日写入 ----
    w("")
    w("【4】今天(09-18)被写过的 C 盘位置")
    w("-" * 78)
    for p in [r"C:\Users\legion\Desktop",
              r"C:\Users\legion\Downloads",
              r"C:\Users\legion\Documents",
              r"C:\Users\legion\WorkBuddy",
              r"C:\Users\legion\AppData\Local\Temp"]:
        if not os.path.exists(p):
            w("%-50s [不存在]" % p)
            continue
        if reparse(p):
            w("%-50s [联接]->%s (在 E 盘)" % (p, link_to(p)))
            continue
        c, nw = newest_in(p, cap=30000, max_depth=5)
        if c:
            w("%-50s 今日写入 %d 个文件；最新 %s" % (p, c, datetime.fromtimestamp(nw).strftime("%H:%M:%S")))
        else:
            w("%-50s 今日无写入" % p)

    # ---- 4b. Temp 大项 ----
    w("")
    w("【4b】%TEMP% 下今日 >1MB 的项")
    w("-" * 78)
    T = r"C:\Users\legion\AppData\Local\Temp"
    try:
        items = []
        for name in os.listdir(T):
            p = os.path.join(T, name)
            try:
                if datetime.fromtimestamp(os.path.getmtime(p)).date() != TODAY:
                    continue
                if os.path.isdir(p):
                    s, n, _ = measure(p, cap_files=5000, max_depth=4)
                else:
                    s, n = os.path.getsize(p), 1
                if s > 1024 * 1024:
                    items.append((s, name, n))
            except Exception:
                pass
        items.sort(reverse=True)
        for s, name, n in items[:25]:
            w("  %10s  %-50s (%d)" % (h(s), name, n))
        if not items:
            w("  （无 >1MB 的今日项）")
    except Exception as e:
        w("  失败: %s" % e)

    # ---- 5. 工作区 ----
    w("")
    w("【5】本会话工作区")
    w("-" * 78)
    WS = r"C:\Users\legion\WorkBuddy\2026-09-18-08-54-30"
    if os.path.exists(WS):
        rp = reparse(WS)
        w("工作区: %s  形态=%s" % (WS, "联接->" + link_to(WS) if rp else "真实目录"))
        s, n, tr = measure(WS)
        w("   大小 %s / %d 文件%s" % (h(s), n, "  (已截断)" if tr else ""))
    else:
        w("工作区不存在: %s" % WS)
    mem = os.path.join(WS, ".workbuddy", "memory")
    if os.path.exists(mem):
        s, n, _ = measure(mem)
        w("   memory 目录 %s / %d 文件" % (h(s), n))

    w("")
    w("=" * 78)
    w("完")
except Exception:
    w("")
    w("!!! 脚本异常 !!!")
    w(traceback.format_exc())

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(R))
print("OK")
