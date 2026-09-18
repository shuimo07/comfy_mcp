# -*- coding: utf-8 -*-
r"""打印搬迁状态与 E 盘目标目录内容。"""
import json
import os

SRC = r'C:\Users\legion\.workbuddy'
DST = r'E:\WBData\home\.workbuddy'

print('===== 迁移报告 =====')
try:
    d = json.load(open(r'E:\WBData\_migrate_report.json', encoding='utf-8'))
    tot = 0
    for r in d:
        print('%-16s %-24s %8s MB %7ss' % (r.get('status'), r.get('name'),
                                           r.get('src_mb', ''), r.get('sec', '')))
        if r.get('status') == 'OK':
            tot += r.get('freed_mb', 0)
    print('--- OK 项累计释放 %.1f MB / 共 %d 条' % (tot, len(d)))
except Exception as e:
    print('  读不到报告:', e)

print()
print('===== C 盘 .workbuddy 各子目录 =====')
for n in sorted(os.listdir(SRC)):
    p = os.path.join(SRC, n)
    try:
        st = os.lstat(p)
    except Exception:
        continue
    if os.path.isdir(p):
        link = '[联接]' if (st.st_file_attributes & 0x400) else '[真实]'
        try:
            c = len(os.listdir(p))
        except Exception:
            c = -1
        print('  %-28s %s  子项 %d' % (n, link, c))

print()
print('===== E 盘目标 E:\\WBData\\home\\.workbuddy =====')
if os.path.isdir(DST):
    for n in sorted(os.listdir(DST)):
        print('  ', n)
else:
    print('  不存在')
