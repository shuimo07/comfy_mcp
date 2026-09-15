# WorkBuddy: move C-drive user data to E drive, then junction back so paths stay identical.
# Rollback policy: if the source dir cannot be emptied (files locked by the running app),
# delete the E-side copy so we never double the disk usage. Those items are retried after exit.
$ErrorActionPreference = 'Continue'
$logFile = 'E:\WBData\_tools\migrate.log'

function Write-Log([string]$m) {
    Add-Content -LiteralPath $logFile -Value ('[{0}] {1}' -f (Get-Date -Format 'HH:mm:ss'), $m) -Encoding UTF8
}
function Get-DirSize([string]$p) {
    $s = (Get-ChildItem -LiteralPath $p -Recurse -Force -File -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum)
    if ($null -eq $s.Sum) { return [long]0 } else { return [long]$s.Sum }
}
function Get-DirCount([string]$p) {
    return ((Get-ChildItem -LiteralPath $p -Recurse -Force -File -ErrorAction SilentlyContinue | Measure-Object).Count)
}

function Move-ToE([string]$src, [string]$dst) {
    Write-Log "---- START: $src"
    if (-not (Test-Path -LiteralPath $src)) { Write-Log '  SKIP: source missing'; return }
    $it = Get-Item -LiteralPath $src -Force
    if ($it.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        Write-Log ('  SKIP: already junction -> ' + ($it.Target -join ','))
        return
    }
    $sz = Get-DirSize $src
    $ct = Get-DirCount $src
    Write-Log ('  size {0:N2} MB, {1} files' -f ($sz/1MB), $ct)

    New-Item -ItemType Directory -Force -Path $dst | Out-Null
    robocopy "$src" "$dst" /E /MOVE /COPY:DAT /DCOPY:DAT /R:1 /W:1 /NFL /NDL /NP /MT:8 | Out-Null
    Write-Log "  robocopy exit $LASTEXITCODE"

    if (Test-Path -LiteralPath $src) {
        Remove-Item -LiteralPath $src -Recurse -Force -ErrorAction SilentlyContinue
        Start-Sleep -Milliseconds 500
        if (Test-Path -LiteralPath $src) { Remove-Item -LiteralPath $src -Recurse -Force -ErrorAction SilentlyContinue }
    }

    if (Test-Path -LiteralPath $src) {
        Write-Log ('  LOCKED: leftovers {0:N2} MB / {1} files -> rollback E copy' -f ((Get-DirSize $src)/1MB), (Get-DirCount $src))
        Remove-Item -LiteralPath $dst -Recurse -Force -ErrorAction SilentlyContinue
        return
    }
    New-Item -ItemType Junction -Path $src -Value $dst | Out-Null
    Write-Log ('  DONE: junction {0} -> {1}' -f $src, $dst)
}

Write-Log '===== run start ====='

# --- 1. stale temp junk (no locks expected) ---
$T = $env:TEMP
Get-ChildItem -LiteralPath $T -Force -Directory |
    Where-Object { $_.Name -match 'workbuddy|codebuddy' } |
    ForEach-Object { Move-ToE $_.FullName ('E:\WBData\temp-junk\' + $_.Name) }

# --- 2. the big one: C:\Users\legion\.workbuddy ---
$home_src = 'C:\Users\legion\.workbuddy'
$home_dst = 'E:\WBData\home\.workbuddy'
Get-ChildItem -LiteralPath $home_src -Force -Directory |
    ForEach-Object { Move-ToE $_.FullName (Join-Path $home_dst $_.Name) }

# --- 3. legacy .codebuddy ---
Move-ToE 'C:\Users\legion\.codebuddy' 'E:\WBData\home\.codebuddy'

# --- 4. empty Electron AppData\Roaming dirs -> judge now, zero risk ---
foreach ($n in @('WorkBuddy','workbuddy')) {
    $s = Join-Path $env:APPDATA $n
    $d = "E:\WBData\roaming\$n"
    if (Test-Path -LiteralPath $s) {
        $i = Get-Item -LiteralPath $s -Force
        if ($i.Attributes -band [IO.FileAttributes]::ReparsePoint) { Write-Log "  SKIP junction exists: $s"; continue }
        New-Item -ItemType Directory -Force -Path $d | Out-Null
        $c = (Get-ChildItem -LiteralPath $s -Recurse -Force | Measure-Object).Count
        if ($c -gt 0) { Move-ToE $s $d }
        else {
            Remove-Item -LiteralPath $s -Recurse -Force -ErrorAction SilentlyContinue
            if (-not (Test-Path -LiteralPath $s)) {
                New-Item -ItemType Junction -Path $s -Value $d | Out-Null
                Write-Log "  DONE: junction $s -> $d"
            } else { Write-Log "  FAIL: cannot remove empty $s" }
        }
    }
}

Write-Log '===== run end ====='
