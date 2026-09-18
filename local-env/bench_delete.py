# -*- coding: utf-8 -*-
r"""对比不同删目录方式的速度，挑最快的用于清理 __old 残留。"""
import os
import shutil
import subprocess
import time

ROOT = r'E:\WBData\_deltest'


def make_fixture(tag, n=1500):
    d = os.path.join(ROOT, tag)
    if os.path.isdir(d):
        shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d, exist_ok=True)
    for i in range(n):
        sub = os.path.join(d, 'sub%02d' % (i % 40))
        os.makedirs(sub, exist_ok=True)
        with open(os.path.join(sub, 'f%05d.txt' % i), 'w') as f:
            f.write('x' * 200)
    return d


def rate(d, sec, n=1500):
    return n / sec if sec > 0 else 0


def count(p):
    n = 0
    for r, dd, ff in os.walk(p, onerror=lambda e: None):
        n += len(ff)
    return n


results = []

# A) cmd rmdir /s /q
d = make_fixture('a')
t = time.time()
subprocess.run('cmd /c rmdir /s /q "%s"' % d, shell=True, capture_output=True)
el = time.time() - t
results.append(('A cmd rmdir /s /q', el, rate(d, el)))

# B) robocopy /MIR  空目录 -> 目标
d = make_fixture('b')
empty = os.path.join(ROOT, '_empty')
os.makedirs(empty, exist_ok=True)
t = time.time()
subprocess.run('robocopy "%s" "%s" /MIR /MT:16 /R:0 /W:0 /NFL /NDL /NJH /NJS /NP'
               % (empty, d), shell=True, capture_output=True)
el = time.time() - t
results.append(('B robocopy /MIR /MT:16', el, rate(d, el)))
left_b = count(d)

# C) python shutil.rmtree
d = make_fixture('c')
t = time.time()
try:
    shutil.rmtree(d)
    err = ''
except Exception as e:
    err = repr(e)[:120]
el = time.time() - t
results.append(('C shutil.rmtree', el, rate(d, el)))
if err:
    results[-1] = ('C shutil.rmtree', el, rate(d, el), err)

# D) python os.scandir 递归手工删
d = make_fixture('d')
t = time.time()


def nuke(p):
    if not os.path.isdir(p):
        return
    with os.scandir(p) as it:
        for e in it:
            if e.is_dir(follow_symlinks=False):
                nuke(e.path)
            else:
                try:
                    os.unlink(e.path)
                except Exception:
                    pass
    try:
        os.rmdir(p)
    except Exception:
        pass


nuke(d)
el = time.time() - t
results.append(('D python scandir 手工删', el, rate(d, el)))

print('===== 删除 1500 文件耗时对比 =====')
for r in results:
    if len(r) == 4:
        print('  %-24s %6.2fs  %8.0f 文件/秒   注:%s' % (r[0], r[1], r[2], r[3]))
    else:
        print('  %-24s %6.2fs  %8.0f 文件/秒' % r)
print('B 残留文件数:', left_b)

shutil.rmtree(ROOT, ignore_errors=True)
