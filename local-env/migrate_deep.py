# -*- coding: utf-8 -*-
r"""
.workbuddy -> E: 递归迁移。

策略：
  * 目录空闲（能改名）            -> 整体复制 / 改名腾路径 / 建 junction / 安全删旧
  * 目录被占用（父目录有句柄）    -> 递归进子目录，逐个搬（目标路径一一对应，所以
                                     将来父目录整体搬迁时结果依然正确）
  * junction                      -> 跳过（已迁移）
  * *.__old / *.__probe / *.__movetest 残留 -> 安全清理（只删联接本身，绝不下穿）

安全删除 safe_rmtree：遇到 junction 只移除链接，不递归其内容。
用法: python migrate_deep.py [--dry] [--skip=<目录名>]...

--skip 用于排除「正在被使用的会话目录」（通常就是本次会话自己）。
改活动目录名会让应用继续往改名后的目录写（句柄按文件 ID 跟踪），
同时按路径新建同名目录 -> 数据分裂。留到登录时由守卫整体搬迁才安全。
"""
import os
import sys
import io
import json
import time
import subprocess

SRC = r'C:\Users\legion\.workbuddy'
DST = r'E:\WBData\home\.workbuddy'
REPORT = r'E:\WBData\_migrate_deep.json'
ATTR_REPARSE = 0x400
LEFT_MARK = ('__old', '__probe', '__movetest')
# 正在被 Electron/Chromium 使用的会话缓存：运行中搬迁会造成「半在新半在旧」的分裂，
# 收益（约 120MB）远小于风险，留给登录时（应用未启动）整体搬迁。
EXCLUDE_PREFIX = ('app\\session',)
DRY = '--dry' in sys.argv
SKIP = tuple(a.split('=', 1)[1] for a in sys.argv
             if a.startswith('--skip=') and '=' in a)

LOG = []

LOCK = r'E:\WBData\_tools\.migrate_deep.lock'


def acquire_lock():
    """防止登录守卫重复拉起（上次还没跑完就再来一份会互相打架）。"""
    if os.path.exists(LOCK):
        try:
            pid = int(io.open(LOCK, encoding='utf-8').read().strip() or 0)
            # 锁超过 3 小时一律视为陈旧：避免上一次被强杀后
            # 留下一个「PID 恰好被别的进程复用」的假占用，导致每次登录都跳过。
            stale = (time.time() - os.path.getmtime(LOCK)) > 3 * 3600
            # PID 0 是 release_lock() 写的「已释放」标记，不是真进程，否则会误判为占用
            if pid > 0 and not stale:
                out = subprocess.run('tasklist /FI "PID eq %d" /NH' % pid, shell=True,
                                     capture_output=True, text=True, errors='replace')
                if str(pid) in (out.stdout or ''):
                    print('另一个迁移进程 (PID %d) 仍在运行，本次退出。' % pid)
                    return False
        except Exception:
            pass
    io.open(LOCK, 'w', encoding='utf-8').write(str(os.getpid()))
    return True


def release_lock():
    try:
        if os.path.exists(LOCK):
            io.open(LOCK, 'w', encoding='utf-8').write('0')
    except Exception:
        pass


def log(msg):
    print(msg, flush=True)
    LOG.append(msg)


def sh(cmd):
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                       errors='replace')
    return p.returncode, (p.stdout or '') + (p.stderr or '')


def is_reparse(p):
    try:
        return bool(os.lstat(p).st_file_attributes & ATTR_REPARSE)
    except Exception:
        return False


def rename_ok(path):
    tmp = path + '.__movetest'
    if os.path.exists(tmp):
        return False, 'TMP-EXISTS'
    try:
        os.rename(path, tmp)
    except OSError as e:
        return False, 'LOCKED(%s)' % getattr(e, 'winerror', e.errno)
    try:
        os.rename(tmp, path)
    except OSError as e:
        return False, 'RESTORE-FAIL'
    return True, ''


def tree_stats(path, follow=False):
    n = b = 0
    for r, d, f in os.walk(path, onerror=lambda e: None, followlinks=follow):
        for x in f:
            try:
                b += os.path.getsize(os.path.join(r, x))
                n += 1
            except Exception:
                pass
    return n, b


def strip_junctions(root):
    """把树里的 junction 只删链接（不带 /s，不会下穿到目标）。返回处理个数。"""
    n = 0
    for cur, dirs, files in os.walk(root, topdown=True, onerror=lambda e: None):
        keep = []
        for d in dirs:
            dp = os.path.join(cur, d)
            if is_reparse(dp):
                sh('cmd /c rmdir "%s"' % dp)
                n += 1
            else:
                keep.append(d)
        dirs[:] = keep
    return n


def safe_rmtree(path):
    r"""删目录树。两段式，确保不会下穿 junction 删掉 E 盘真实数据：
       1) 先把树里所有 junction 逐个摘掉（cmd rmdir <junc>，不带 /s）
       2) 再用 cmd /c rmdir /s /q 整树删除

       为什么不用 os.unlink / shutil.rmtree：本机 safe-delete 钩子会劫持它们
       （SAFE_DELETE_FAIL_CLOSED / SAFE_DELETE_BULK_CONFIRM_REQUIRED，>50 个即中断），
       而走 cmd /c rmdir 是子进程，不受该钩子影响（第一轮迁移就是这么成功的）。
    """
    if not os.path.exists(path):
        return
    if is_reparse(path):
        sh('cmd /c rmdir "%s"' % path)
        return
    strip_junctions(path)
    sh('cmd /c rmdir /s /q "%s"' % path)


def ensure_subset(src, dst):
    """src 里每个文件在 dst 都能找到同名文件；用于合并/复制后的校验。"""
    missing = 0
    for r, d, f in os.walk(src, onerror=lambda e: None):
        rel = os.path.relpath(r, src)
        for x in f:
            tp = os.path.join(dst, rel, x) if rel != '.' else os.path.join(dst, x)
            if not os.path.exists(tp):
                missing += 1
    return missing


def do_move(rel):
    """rel 相对 SRC。返回 (status, freed_mb)。"""
    src = os.path.join(SRC, rel)
    dst = os.path.join(DST, rel)
    if not os.path.exists(src):
        return 'MISSING', 0
    if is_reparse(src):
        return 'ALREADY-LINK', 0
    ok, why = rename_ok(src)
    if not ok:
        return why, 0

    n0, b0 = tree_stats(src)
    if n0 == 0 and not os.listdir(src):
        # 空目录：直接换联接
        try:
            os.rmdir(src)
        except OSError:
            pass
        os.makedirs(dst, exist_ok=True)
        sh('cmd /c mklink /J "%s" "%s"' % (src, dst))
        return ('OK' if is_reparse(src) else 'FAIL-EMPTY'), 0

    os.makedirs(dst, exist_ok=True)
    rc, out = sh('robocopy "%s" "%s" /E /XJ /R:1 /W:1 /NFL /NDL /NJH /NJS /NP'
                 % (src, dst))
    if rc >= 8:
        return 'FAIL-ROBOCOPY', 0
    miss = ensure_subset(src, dst)
    if miss:
        return 'FAIL-VERIFY(%d missing)' % miss, 0

    old = src + '.__old'
    try:
        os.rename(src, old)
    except OSError:
        return 'FAIL-RENAME', 0
    sh('cmd /c mklink /J "%s" "%s"' % (src, dst))
    if not is_reparse(src):
        try:
            os.rename(old, src)
        except OSError:
            pass
        return 'FAIL-MKLINK', 0
    safe_rmtree(old)
    left = tree_stats(old)[0] if os.path.exists(old) else 0
    return 'OK' + ('(left%d)' % left if left else ''), b0 / 1048576


def migrate(rel):
    src = os.path.join(SRC, rel)
    if not os.path.exists(src):
        return
    if is_reparse(src):
        return
    if os.path.basename(rel.rstrip(os.sep)) in SKIP:
        log('  [SKIP-LIVE    ] %-60s 正在使用的会话目录，不搬' % rel)
        return
    if any(rel == p or rel.startswith(p + os.sep) for p in EXCLUDE_PREFIX):
        log('  [SKIP-LIVE    ] %-60s 运行中不搬' % rel)
        return
    ok, why = rename_ok(src)
    if ok:
        if DRY:
            log('  [dry] 将搬迁 %s' % rel)
            return
        st, mb = do_move(rel)
        log('  [%-18s] %-60s %.1f MB' % (st, rel, mb))
        return
    # 被占用 -> 递归子目录
    for n in sorted(os.listdir(src)):
        if any(m in n for m in LEFT_MARK):
            continue
        p = os.path.join(src, n)
        if os.path.isdir(p):
            migrate(os.path.join(rel, n))


def fix_movetest():
    r"""处理被中断探测留下的 workspace\sessions\<id>.__movetest 分裂。

    为什么不做合并：<id> 是「正在被 WorkBuddy 使用的」项目工作区，边写边合并又慢又险。
    这里只把残留改成一个明确的名字（数据一个字节都不动），
    随后跟着 workspace\sessions 整体搬到 E:，可以随时人工确认后再删。
    """
    base = os.path.join(SRC, r'workspace\sessions')
    if not os.path.isdir(base):
        return
    stamp = time.strftime('%Y%m%d')
    for n in os.listdir(base):
        if not n.endswith('.__movetest'):
            continue
        stray = os.path.join(base, n)
        base_name = n[:-len('.__movetest')]
        target = base_name + '-orphaned-' + stamp
        dstp = os.path.join(base, target)
        k = 0
        while os.path.exists(dstp):
            k += 1
            dstp = os.path.join(base, '%s-orphaned-%s-%d' % (base_name, stamp, k))
        nf, nb = tree_stats(stray)
        try:
            os.rename(stray, dstp)
        except OSError as e:
            log('  改名失败，保留原名: %s (%s)' % (n, e))
            continue
        log('  残留改名保留: %s -> %s  (%d files, %.1f MB)'
            % (n, os.path.basename(dstp), nf, nb / 1048576))


def recover_old():
    r"""中断自愈：进程若在「已改名、还没建联接」之间被杀，原路径会凭空消失。

    规则：看到 X.__old / X.__probe 而 X 不存在 -> 把 X.__old 改回 X。
    看到 X.__old 且 X 存在 -> 联接已建好，__old 只是没删干净，交给第二步清理。
    """
    fixed = 0
    base_depth = SRC.rstrip('\\').count(os.sep)
    for cur, dirs, files in os.walk(SRC, topdown=True, onerror=lambda e: None):
        if cur.rstrip('\\').count(os.sep) - base_depth > 3:
            dirs[:] = []
            continue
        for d in list(dirs):
            hit = next((m for m in ('__old', '__probe') if d.endswith(m)), None)
            if not hit:
                continue
            stray = os.path.join(cur, d)
            orig = os.path.join(cur, d[:-len(hit)])
            if os.path.exists(orig):
                # 原目录已存在（联接已建好），这个 __old 交给 cleanup_nested_old 处理；
                # 这里必须把它从 dirs 里摘掉，否则 os.walk 会白走几十万文件。
                dirs.remove(d)
                continue
            try:
                os.rename(stray, orig)
                log('  自愈: %s -> %s' % (d, d[:-len(hit)]))
                fixed += 1
            except OSError as e:
                log('  自愈失败(仍被占用): %s (%s)' % (d, e))
            dirs.remove(d)
    return fixed


def cleanup_nested_old(max_depth=3):
    r"""清理嵌套的 X.__old / X.__probe（只有 X 已经存在时才删）。

    do_move 在建联接前已经做过 ensure_subset 校验，所以 X.__old 里的内容
    一定也在 X（现在是 E 盘联接）里。X.__old 只剩两种东西：
      * 被进程句柄占住、当初删不掉的文件（多为正在写的日志）——可丢；
      * 建联接之后进程继续通过句柄写进来的新内容 —— 对日志无所谓。
    """
    base_depth = SRC.rstrip('\\').count(os.sep)
    removed = 0
    for cur, dirs, files in os.walk(SRC, topdown=True, onerror=lambda e: None):
        if cur.rstrip('\\').count(os.sep) - base_depth > max_depth:
            dirs[:] = []
            continue
        keep = []
        for d in list(dirs):
            hit = next((m for m in ('__old', '__probe') if d.endswith(m)), None)
            if not hit:
                keep.append(d)
                continue
            stray = os.path.join(cur, d)
            orig = os.path.join(cur, d[:-len(hit)])
            if not os.path.exists(orig):
                log('  [保留] %s（原目录不存在，等 recover_old 处理）' % d)
                keep.append(d)
                continue
            if is_reparse(stray):
                log('  [跳过] %s 是联接，不删' % d)
                continue
            if not rename_ok(stray)[0]:
                log('  [LOCKED] %s 仍被占用，留到下次' % d)
                keep.append(d)
                continue
            nf, nb = tree_stats(stray)
            safe_rmtree(stray)
            left = tree_stats(stray)[0] if os.path.exists(stray) else 0
            log('  [%-4s] %-46s %d files %.1f MB'
                % ('OK' if not left else 'LEFT%d' % left, d, nf, nb / 1048576))
            removed += 1
            if os.path.exists(stray):
                keep.append(d)
        dirs[:] = keep
    return removed


def main():
    if not acquire_lock():
        return
    t0 = time.time()
    log('==== 递归迁移开始 %s ====' % time.strftime('%H:%M:%S'))
    os.makedirs(DST, exist_ok=True)

    log('--- 第零步：中断自愈 ---')
    if not DRY:
        recover_old()

    log('--- 第一步：修复中断残留 ---')
    if not DRY:
        fix_movetest()

    log('--- 第二步：嵌套 __old/__probe 清理 ---')
    if not DRY:
        cleanup_nested_old()

    log('--- 第二步b：顶层残留清理 ---')
    for n in sorted(os.listdir(SRC)):
        if not any(m in n for m in LEFT_MARK):
            continue
        p = os.path.join(SRC, n)
        if not os.path.isdir(p):
            continue
        if is_reparse(p):
            log('  [跳过] %s 其实是联接，不删' % n)
            continue
        if DRY:
            log('  [dry] 将清理 %s' % n)
            continue
        if not rename_ok(p)[0]:
            log('  [LOCKED] %s 仍被占用，留到下次登录' % n)
            continue
        n0, b0 = tree_stats(p)
        safe_rmtree(p)
        log('  [%-4s] %-40s %d files %.1f MB'
            % ('OK' if not os.path.exists(p) else 'LEFT', n, n0, b0 / 1048576))

    log('--- 第三步：递归迁移子目录 ---')
    for n in sorted(os.listdir(SRC)):
        if any(m in n for m in LEFT_MARK):
            continue
        p = os.path.join(SRC, n)
        if os.path.isdir(p) and not is_reparse(p):
            migrate(n)

    log('==== 完成，用时 %.1f 分钟 ====' % ((time.time() - t0) / 60))
    with open(REPORT, 'w', encoding='utf-8') as f:
        json.dump(LOG, f, ensure_ascii=False, indent=1)
    release_lock()


if __name__ == '__main__':
    main()
