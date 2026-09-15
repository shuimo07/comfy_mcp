import os

root = "C:" + chr(92) + r"Users\legion\.workbuddy"
print("扫描 .workbuddy 内部的 reparse point（junction/symlink）...")
found = []
nfiles = 0
nbytes = 0
for dp, dn, fn in os.walk(root, onerror=lambda e: None):
    nfiles += len(fn)
    for f in fn:
        try:
            nbytes += os.path.getsize(os.path.join(dp, f))
        except OSError:
            pass
    # 检查子目录是否为 reparse point
    for d in list(dn):
        p = os.path.join(dp, d)
        try:
            st = os.stat(p, follow_symlinks=False)
            if getattr(st, "st_file_attributes", 0) & 0x400:
                found.append(p)
        except OSError:
            pass

print("  文件数 %d, 逻辑大小 %.2f GB" % (nfiles, nbytes / 2**30))
if found:
    print("  发现 %d 个嵌套 reparse point:" % len(found))
    for p in found:
        print("    " + p)
else:
    print("  无嵌套 junction ✔（可以整目录搬迁）")
