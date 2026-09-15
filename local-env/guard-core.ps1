# Shared helpers for keeping WorkBuddy data off C:
#   Ensure-Junction <C-path> <E-path>
# Idempotent; never deletes data before it is safely copied to E:.
# robocopy /MOVE is intentionally NOT used anywhere (cross-volume it can lose data).

$ErrorActionPreference = 'Continue'
$LogDir  = 'E:\WBData\_tools'
$LogFile = "$LogDir\guard.log"
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Force -Path $LogDir | Out-Null }
if ((Test-Path $LogFile) -and ((Get-Item $LogFile).Length -gt 2MB)) { Remove-Item $LogFile -Force -ErrorAction SilentlyContinue }

function Log([string]$m) {
    Add-Content -LiteralPath $LogFile -Value ('[{0}] {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $m) -Encoding UTF8
}
function Count-Files([string]$p) {
    return ((Get-ChildItem -LiteralPath $p -Recurse -Force -File -ErrorAction SilentlyContinue | Measure-Object).Count)
}

function Ensure-Junction([string]$src, [string]$dst, [string[]]$BlockIfRunning = @()) {
    Log "check: $src"

    if (-not (Test-Path -LiteralPath $dst)) { New-Item -ItemType Directory -Force -Path $dst | Out-Null }

    if (-not (Test-Path -LiteralPath $src)) {
        New-Item -ItemType Junction -Path $src -Value $dst | Out-Null
        Log "  created junction -> $dst"
        return
    }

    $it = Get-Item -LiteralPath $src -Force
    if ($it.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        Log ('  already junction -> ' + ($it.Target -join ''))
        return
    }

    $sc = Count-Files $src
    robocopy "$src" "$dst" /E /COPY:DAT /DCOPY:DAT /R:2 /W:1 /NFL /NDL /NP /MT:8 /XJ | Out-Null
    $dc = Count-Files $dst
    Log "  copied. src=$sc dst=$dc"
    if ($dc -lt $sc) { Log '  ABORT: destination incomplete, source untouched'; return }

    # LAST-CHANCE CHECK: 删除前再确认没有进程占用，否则会删掉正在被写入的数据。
    # 数据已经完整拷到 E: 了，所以这里直接放弃、下次登录重来，代价只是多跑一次增量同步。
    if ($BlockIfRunning.Count -gt 0) {
        $live = @(Get-Process -Name $BlockIfRunning -ErrorAction SilentlyContinue).Count
        if ($live -gt 0) {
            $msg = '  ABORT: {0} process(es) running [{1}] - source untouched, retry next logon' -f $live, ($BlockIfRunning -join ',')
            Log $msg
            return
        }
    }

    Remove-Item -LiteralPath $src -Recurse -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 500
    if (Test-Path -LiteralPath $src) { Remove-Item -LiteralPath $src -Recurse -Force -ErrorAction SilentlyContinue }

    if (Test-Path -LiteralPath $src) {
        Log ('  LOCKED: {0} entries still there, retry next logon' -f (Count-Files $src))
        return
    }
    New-Item -ItemType Junction -Path $src -Value $dst | Out-Null
    Log "  junction created -> $dst"
}
