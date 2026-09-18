r"""
把 C:\Users\legion\.workbuddy 的各个子目录搬到 E:\WBData\home\.workbuddy，
再在原路径建 junction。路径保持不变 -> 任何配置/数据库都不用改。

安全顺序（杜绝"删一半残留残缺目录"）：
  1. 复制 src -> dst，核对文件数
  2. 把 src 改名为 src.__old   （失败则中止，源目录完好无损）
  3. 在原路径 mklink /J src dst （失败则把 __old 改回来）
  4. 尽力删除 src.__old        （删不掉的通常是正在运行的 exe，无妨）

用法:
    python migrate_workbuddy_home.py --probe   # 只探测
    python migrate_workbuddy_home.py --run     # 真正搬迁
"""
import os
import sys
import json
import time
import subprocess

SRC = r'C:\Users\legion\.workbuddy'
DST = r'E:\WBData\home\.workbuddy'
REPORT = r'E:\WBData\_migrate_report.json'

FILE_ATTRIBUTE_REPARSE_POINT = 0x400

# 正在运行的解释器/工具链放在最后搬，降低对当前会话的扰动
TAIL = ['binaries']


def is_reparse(path):
    try:
        st = os.lstat(path)
        return bool(st.st_file_attributes & FILE_ATTRIBUTE_REPARSE_POINT)
    except Exception:
        return False


def sh(cmd):
    p = subprocess.run(cmd, shell=True, capture_output=True,
                       text=True, errors='replace')
    return p.returncode, (p.stdout or '') + (p.stderr or '')


def rename_ok(path):
    """目录能改名 -> 内部没有被独占到"不可改名"的句柄。"""
    tmp = path + '.__movetest'
    try:
        os.rename(path, tmp)
    except OSError as e:
        return False, 'LOCKED(%s)' % getattr(e, 'winerror', e.errno)
    try:
        os.rename(tmp, path)
    except OSError as e:
        return False, 'RESTORE-FAIL(%s)' % getattr(e, 'winerror', e.errno)
    return True, ''


def tree_stats(path):
    n = 0
    b = 0
    for root, dirs, files in os.walk(path, onerror=lambda e: None):
        for f in files:
            try:
                b += os.path.getsize(os.path.join(root, f))
                n += 1
            except Exception:
                pass
    return n, b


SKIP_MARK = ('__old', '__probe', '__movetest')


def subdirs():
    out = []
    for name in sorted(os.listdir(SRC)):
        if any(m in name for m in SKIP_MARK):
            continue
        p = os.path.join(SRC, name)
        if os.path.isdir(p) and not is_reparse(p):
            out.append(name)
    # 把 TAIL 里的挪到最后
    return sorted(out, key=lambda n: (n in TAIL, n))


def cleanup_old():
    """清掉 *.__old / *.__probe 残留（里面通常只剩正在运行的 exe，删不掉是正常的）。"""
    done = []
    for name in sorted(os.listdir(SRC)):
        if not any(m in name for m in SKIP_MARK):
            continue
        p = os.path.join(SRC, name)
        if not os.path.isdir(p):
            continue
        n0, b0 = tree_stats(p)
        if not rename_ok(p)[0]:
            done.append((name, n0, b0, 'SKIP-LOCKED'))
            continue
        sh('cmd /c rmdir /s /q "%s"' % p)
        if os.path.exists(p):
            n1, b1 = tree_stats(p)
            done.append((name, n1, b1, 'LEFT'))
        else:
            done.append((name, n0, b0, 'OK'))
    return done


def probe():
    result = {}
    for name in subdirs():
        p = os.path.join(SRC, name)
        n, b = tree_stats(p)
        free, why = rename_ok(p)
        result[name] = {'mb': round(b / 1048576, 1), 'files': n,
                        'free': free, 'why': why}
    return result


def run_on(relpath):
    """relpath 相对 SRC，例如 'workspace/sessions/xxxx' 或 'logs/2026-09-15'。"""
    src = os.path.join(SRC, relpath.replace('/', os.sep))
    dst = os.path.join(DST, relpath.replace('/', os.sep))
    rec = {'name': relpath}
    if not os.path.exists(src):
        rec['status'] = 'MISSING'
        return rec
    if is_reparse(src):
        rec['status'] = 'ALREADY-LINK'
        return rec

    free, why = rename_ok(src)
    if not free:
        rec['status'] = 'SKIP-LOCKED'
        rec['why'] = why
        return rec

    n_src, b_src = tree_stats(src)
    rec['src_files'] = n_src
    rec['src_mb'] = round(b_src / 1048576, 1)

    os.makedirs(dst, exist_ok=True)
    rc, out = sh('robocopy "%s" "%s" /E /XJ /R:1 /W:1 /NFL /NDL /NJH /NJS /NP'
                 % (src, dst))
    if rc >= 8:
        rec['status'] = 'FAIL-ROBOCOPY'
        rec['rc'] = rc
        rec['out'] = out[-1200:]
        return rec

    n_dst, b_dst = tree_stats(dst)
    rec['dst_files'] = n_dst
    rec['dst_mb'] = round(b_dst / 1048576, 1)
    if n_dst != n_src:
        rec['status'] = 'FAIL-VERIFY'
        return rec

    old = src + '.__old'
    k = 0
    while os.path.exists(old):
        k += 1
        old = src + '.__old%d' % k
    try:
        os.rename(src, old)
    except OSError as e:
        rec['status'] = 'FAIL-RENAME'
        rec['why'] = str(e)
        return rec

    rc, out = sh('cmd /c mklink /J "%s" "%s"' % (src, dst))
    if not is_reparse(src):
        try:
            os.rename(old, src)
        except Exception:
            pass
        rec['status'] = 'FAIL-MKLINK'
        rec['rc'] = rc
        rec['out'] = out[-800:]
        return rec

    sh('cmd /c rmdir /s /q "%s"' % old)
    rec['left_files'] = tree_stats(old)[0] if os.path.exists(old) else 0
    rec['status'] = 'OK'
    rec['freed_mb'] = round(b_src / 1048576, 1)
    return rec


def run_one(name):
    return run_on(name)


def main():
    args = sys.argv[1:]
    mode = args[0] if args else '--probe'

    if mode == '--probe':
        r = probe()
        print(json.dumps(r, ensure_ascii=False, indent=2))
        with open(REPORT, 'w', encoding='utf-8') as f:
            json.dump(r, f, ensure_ascii=False, indent=2)
        return

    # --run-path a/b/c  [a/b/d ...]
    if mode == '--run-path':
        os.makedirs(DST, exist_ok=True)
        results = []
        for rel in args[1:]:
            rec = run_on(rel)
            print('[%-15s] %-52s %s MB' % (rec.get('status'), rel,
                                           rec.get('src_mb', '')), flush=True)
            results.append(rec)
        with open(REPORT.replace('.json', '_paths.json'), 'w',
                  encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        return

    os.makedirs(DST, exist_ok=True)
    results = []
    for name in subdirs():
        t0 = time.time()
        try:
            rec = run_one(name)
        except Exception as e:
            rec = {'name': name, 'status': 'EXCEPTION', 'why': repr(e)}
        rec['sec'] = round(time.time() - t0, 1)
        results.append(rec)
        print('[%-15s] %-24s %ss  %s MB'
              % (rec.get('status'), name, rec['sec'], rec.get('src_mb', '')),
              flush=True)
        with open(REPORT, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
    total = sum(r.get('freed_mb', 0) for r in results
                if r.get('status') == 'OK')
    print('=' * 56)
    print('已释放约 %.1f MB' % total)

    print('--- 清理 __old 残留 ---')
    for name, n, b, stt in cleanup_old():
        print('  [%-11s] %-24s %6d files  %.1f MB' % (stt, name, n, b / 1048576))
        if stt == 'OK':
            total += b / 1048576
    print('=' * 56)
    print('实际释放合计约 %.1f MB' % total)


if __name__ == '__main__':
    main()
