# -*- coding: utf-8 -*-
"""测算迁移剩余工作量：只统计「仍是真实目录」的部分。"""
import os, time

SRC = r'C:\Users\legion\.workbuddy'
ATTR_REPARSE = 0x400


def is_rep(p):
    try:
        return bool(os.lstat(p).st_file_attributes & ATTR_REPARSE)
    except Exception:
        return False


def stats(p):
    n = b = 0
    for r, d, f in os.walk(p, onerror=lambda e: None):
        d[:] = [x for x in d if not is_rep(os.path.join(r, x))]
        for x in f:
            try:
                b += os.path.getsize(os.path.join(r, x))
            except Exception:
                pass
            n += 1
    return n, b


t0 = time.time()
rows = []
total_n = total_b = 0
for n in sorted(os.listdir(SRC)):
    p = os.path.join(SRC, n)
    if not os.path.isdir(p) or is_rep(p):
        continue
    nf, nb = stats(p)
    rows.append((n, nf, nb))
    total_n += nf
    total_b += nb

print('%-52s %10s %10s' % ('C 盘 .workbuddy 里仍是真实目录的', '文件数', 'MB'))
print('-' * 76)
for n, nf, nb in rows:
    print('%-52s %10d %10.1f' % (n, nf, nb / 1048576))
print('-' * 76)
print('%-52s %10d %10.1f' % ('合计', total_n, total_b / 1048576))
sp = 20.0
print()
print('按 20 文件/秒（沙箱实测）估算: 约 %.0f 分钟' % (total_n / sp / 60))
print('本次统计耗时 %.1f 秒' % (time.time() - t0))
