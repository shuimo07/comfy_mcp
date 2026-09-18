# -*- coding: utf-8 -*-
"""轻量进度探针：不遍历大目录，只看 .workbuddy 顶层各子项是联接还是真实目录。"""
import os, sys, time

SRC = r'C:\Users\legion\.workbuddy'
DST = r'E:\WBData\home\.workbuddy'
ATTR_REPARSE = 0x400


def is_rep(p):
    try:
        return bool(os.lstat(p).st_file_attributes & ATTR_REPARSE)
    except Exception:
        return False


def quick_size(p, cap_files=4000):
    """只数到 cap_files 就停，避免拖慢正在跑的迁移。"""
    n = b = 0
    for r, d, f in os.walk(p, onerror=lambda e: None):
        for x in f:
            try:
                b += os.path.getsize(os.path.join(r, x))
            except Exception:
                pass
            n += 1
            if n >= cap_files:
                return n, b, True
    return n, b, False


def main():
    lines = []
    lines.append('时间 %s' % time.strftime('%H:%M:%S'))
    lines.append('%-14s %-10s %s' % ('子项', '类型', '大小/文件数'))
    lines.append('-' * 62)
    tot_real = 0
    for n in sorted(os.listdir(SRC)):
        p = os.path.join(SRC, n)
        if not os.path.isdir(p):
            continue
        if is_rep(p):
            lines.append('%-14s %-10s -> %s' % (n, 'JUNCTION',
                         os.readlink(p) if hasattr(os, 'readlink') else ''))
            continue
        cnt, sz, cut = quick_size(p)
        tot_real += sz
        lines.append('%-14s %-10s %.1f MB / %d%s files' % (
            n, '真实目录', sz / 1048576, cnt, '+' if cut else ''))
    lines.append('-' * 62)
    lines.append('C 盘 .workbuddy 真实占用（未截断部分）合计: %.2f GB' % (tot_real / 1073741824))
    out = '\n'.join(lines)
    print(out)


main()
