# Shared helpers for keeping WorkBuddy data off C:
#   Ensure-Junction <C-path> <E-path> [<BlockIfRunning names>]
# Idempotent; never deletes data before it is safely copied to E:.
# robocopy /MOVE is intentionally NOT used anywhere (cross-volume it can lose data).
#
# 2026-09-18 hardening (needed by the new ".workbuddy subdirectory" policy):
#   * Count-Files and Remove-Tree are REPARSE-AWARE. A junction inside the tree is
#     never followed: Count-Files skips it, Remove-Tree unlinks the junction itself.
#     Without this, moving a parent whose child is ALREADY a junction would
#     (a) count the child twice and ABORT forever, and
#     (b) follow the junction and delete the real data on E:.
#   * a rename probe runs before the copy: if the directory is held open by a
#     running process, we give up immediately and retry on the next logon.

$ErrorActionPreference = 'Continue'
$LogDir  = 'E:\WBData\_tools'
$LogFile = "$LogDir\guard.log"
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Force -Path $LogDir | Out-Null }
if ((Test-Path $LogFile) -and ((Get-Item $LogFile).Length -gt 2MB)) { Remove-Item $LogFile -Force -ErrorAction SilentlyContinue }

function Log([string]$m) {
    Add-Content -LiteralPath $LogFile -Value ('[{0}] {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $m) -Encoding UTF8
}

function Test-Reparse([string]$p) {
    try {
        $a = [System.IO.File]::GetAttributes($p)
        return [bool]($a -band [IO.FileAttributes]::ReparsePoint)
    } catch { return $false }
}

function Count-Files([string]$p) {
    # 与 robocopy /XJ 口径一致：不下穿 junction / 符号链接
    $n = 0
    $stack = New-Object System.Collections.Stack
    $stack.Push($p)
    while ($stack.Count -gt 0) {
        $cur = $stack.Pop()
        try { $items = [System.IO.Directory]::GetFileSystemEntries($cur) } catch { continue }
        foreach ($it in $items) {
            try { $attr = [System.IO.File]::GetAttributes($it) } catch { continue }
            if ($attr -band [IO.FileAttributes]::ReparsePoint) { continue }
            if ($attr -band [IO.FileAttributes]::Directory) { $stack.Push($it) } else { $n++ }
        }
    }
    return $n
}

function Remove-Tree([string]$p) {
    # 删目录树；遇到 junction / 符号链接只移除链接本身，绝不进到目标里删东西
    if (-not (Test-Path -LiteralPath $p)) { return }
    if (Test-Reparse $p) {
        try { [System.IO.Directory]::Delete($p, $false) } catch { try { [System.IO.File]::Delete($p) } catch { } }
        return
    }
    try { $items = [System.IO.Directory]::GetFileSystemEntries($p) } catch { return }
    foreach ($it in $items) {
        if (Test-Reparse $it) {
            try { [System.IO.Directory]::Delete($it, $false) } catch { try { [System.IO.File]::Delete($it) } catch { } }
            continue
        }
        $isDir = $false
        try { $isDir = [bool]([System.IO.File]::GetAttributes($it) -band [IO.FileAttributes]::Directory) } catch { }
        if ($isDir) { Remove-Tree $it } else { try { [System.IO.File]::Delete($it) } catch { } }
    }
    try { [System.IO.Directory]::Delete($p, $false) } catch { }
}

function Ensure-Junction([string]$src, [string]$dst, [string[]]$BlockIfRunning = @()) {
    Log "check: $src"

    if (-not (Test-Path -LiteralPath $dst)) { New-Item -ItemType Directory -Force -Path $dst | Out-Null }

    if (-not (Test-Path -LiteralPath $src)) {
        New-Item -ItemType Junction -Path $src -Value $dst | Out-Null
        Log "  created junction -> $dst"
        return
    }

    if (Test-Reparse $src) {
        Log '  already junction'
        return
    }

    # 复制前先试改名：目录被进程占用时改名会失败，此时立刻放弃，源目录完好无损。
    $parent    = Split-Path $src -Parent
    $leaf      = Split-Path $src -Leaf
    $probeName = $leaf + '.__probe'
    if (Test-Path -LiteralPath (Join-Path $parent $probeName)) {
        Log '  ABORT: leftover .__probe beside the source, clean it up first'
        return
    }
    try {
        Rename-Item -LiteralPath $src -NewName $probeName -ErrorAction Stop
    } catch {
        Log '  ABORT: directory is in use (rename probe failed), source untouched, retry next logon'
        return
    }
    try {
        Rename-Item -LiteralPath (Join-Path $parent $probeName) -NewName $leaf -ErrorAction Stop
    } catch {
        Log '  WARN: rename probe could not be rolled back - inspect manually'
        return
    }

    $sc = Count-Files $src
    robocopy "$src" "$dst" /E /COPY:DAT /DCOPY:DAT /R:2 /W:1 /NFL /NDL /NP /MT:8 /XJ | Out-Null
    $dc = Count-Files $dst
    Log "  copied. src=$sc dst=$dc"
    if ($dc -lt $sc) { Log '  ABORT: destination incomplete, source untouched'; return }

    # LAST-CHANCE CHECK: 删除前再确认没有进程占用。
    # 数据已经完整拷到 E: 了，所以这里直接放弃、下次登录重来，代价只是多跑一次增量同步。
    if ($BlockIfRunning.Count -gt 0) {
        $live = @(Get-Process -Name $BlockIfRunning -ErrorAction SilentlyContinue).Count
        if ($live -gt 0) {
            $msg = '  ABORT: {0} process(es) running [{1}] - source untouched, retry next logon' -f $live, ($BlockIfRunning -join ',')
            Log $msg
            return
        }
    }

    Remove-Tree $src
    Start-Sleep -Milliseconds 300
    Remove-Tree $src

    if (Test-Path -LiteralPath $src) {
        Log ('  LOCKED: {0} entries still there, retry next logon' -f (Count-Files $src))
        return
    }
    New-Item -ItemType Junction -Path $src -Value $dst | Out-Null
    Log "  junction created -> $dst"
}
