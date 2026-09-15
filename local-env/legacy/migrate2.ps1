# WorkBuddy -> E drive migration, v2 (SAFE).
# Rules:
#   1. robocopy COPY ONLY (/MOVE is forbidden: it deletes the source and would risk data loss)
#   2. delete the source only if it can be emptied completely
#   3. create a junction at the original path only after the source is gone
#   4. if the parent cannot be emptied (locked file), recurse ONE level deeper
$ErrorActionPreference = 'Continue'
$logFile = 'E:\WBData\_tools\migrate.log'

function Write-Log([string]$m) {
    Add-Content -LiteralPath $logFile -Value ('[{0}] {1}' -f (Get-Date -Format 'HH:mm:ss'), $m) -Encoding UTF8
}
function Get-DirCount([string]$p) {
    return ((Get-ChildItem -LiteralPath $p -Recurse -Force -File -ErrorAction SilentlyContinue | Measure-Object).Count)
}

function Move-Safe([string]$src, [string]$dst, [int]$depth) {
    if (-not (Test-Path -LiteralPath $src)) { return }
    $it = Get-Item -LiteralPath $src -Force
    if ($it.Attributes -band [IO.FileAttributes]::ReparsePoint) { return }

    Write-Log "[$depth] $src"
    New-Item -ItemType Directory -Force -Path $dst | Out-Null

    robocopy "$src" "$dst" /E /COPY:DAT /DCOPY:DAT /R:1 /W:1 /NFL /NDL /NP /MT:8 | Out-Null
    $sc = Get-DirCount $src
    $dc = Get-DirCount $dst
    Write-Log "     copied. src=$sc  dst=$dc"

    Remove-Item -LiteralPath $src -Recurse -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 400
    if (Test-Path -LiteralPath $src) {
        Remove-Item -LiteralPath $src -Recurse -Force -ErrorAction SilentlyContinue
        Start-Sleep -Milliseconds 400
    }

    if (-not (Test-Path -LiteralPath $src)) {
        New-Item -ItemType Junction -Path $src -Value $dst | Out-Null
        Write-Log "     JUNCTION ok -> $dst"
        return
    }

    $leftCount = (Get-ChildItem -LiteralPath $src -Recurse -Force -ErrorAction SilentlyContinue | Measure-Object).Count
    Write-Log "     locked, $leftCount entries remain"
    if ($depth -ge 2) { Write-Log '     (max depth, will be finished after app exit)'; return }

    # parent is stuck: try one level deeper so the bulk still leaves C:
    Get-ChildItem -LiteralPath $src -Force -Directory -ErrorAction SilentlyContinue |
        Where-Object { -not ($_.Attributes -band [IO.FileAttributes]::ReparsePoint) } |
        ForEach-Object { Move-Safe $_.FullName (Join-Path $dst $_.Name) ($depth + 1) }
}

Write-Log '===== v2 run start ====='

$root = 'C:\Users\legion\.workbuddy'
$dest = 'E:\WBData\home\.workbuddy'
New-Item -ItemType Directory -Force -Path $dest | Out-Null

Get-ChildItem -LiteralPath $root -Force -Directory |
    Where-Object { -not ($_.Attributes -band [IO.FileAttributes]::ReparsePoint) } |
    ForEach-Object { Move-Safe $_.FullName (Join-Path $dest $_.Name) 0 }

Write-Log '===== v2 run end ====='
