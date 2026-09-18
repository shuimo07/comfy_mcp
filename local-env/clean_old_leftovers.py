# -*- coding: utf-8 -*-
r"""清理 .workbuddy 顶层的两个 __old 冗余残留（E 端已有副本，先核对再删）。

安全前提：__old 是 migrate_deep 的「已复制+已核对+已建联接」之后的旧副本，
删除它不会丢数据 —— 但我仍然逐个核对目标文件在 E 端存在且大小一致。
"""
import os
import subprocess
import io

WB = r'C:\Users\legion\.workbuddy'
DSTROOT = r'E:\WBData\home\.workbuddy'

# (C 端 __old 目录, 相对路径, E 端对应文件)
CHECKS = [
    (r'binaries.__old', r'node\versions\22.22.2-3\node.exe',
     r'binaries\node\versions\22.22.2-3\node.exe'),
    (r'plugins.__old',
     r'cache.__old\workbuddy-builtin\weixinpay\1.6.109\prebuilds\win32-x64\QmProtectorLib.dll',
     r'plugins\cache\workbuddy-builtin\weixinpay\1.6.109\prebuilds\win32-x64\QmProtectorLib.dll'),
]


def size(p):
    try:
        return os.path.getsize(p)
    except OSError:
        return -1


for old, rel, dstrel in CHECKS:
    cpath = os.path.join(WB, old)
    src_file = os.path.join(cpath, rel)
    dst_file = os.path.join(DSTROOT, dstrel)
    print('=== %s ===' % old)
    if not os.path.isdir(cpath):
        print('  已不存在，跳过')
        continue
    sc, dc = size(src_file), size(dst_file)
    print('  C 端 %s = %d bytes' % (rel, sc))
    print('  E 端 %s = %d bytes' % (dstrel, dc))
    if sc <= 0 or dc != sc:
        print('  !! 大小不一致或缺失 -> 不删，留给登录守卫')
        continue
    print('  核对通过，执行删除 ...')
    p = subprocess.run('cmd /c rmdir /s /q "%s"' % cpath, shell=True,
                       capture_output=True, text=True, errors='replace')
    print('  rmdir rc=%d  %s' % (p.returncode, (p.stdout or p.stderr or '').strip()))
    print('  现在还存在吗: %s' % os.path.isdir(cpath))
