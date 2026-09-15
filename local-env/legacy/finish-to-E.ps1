# WorkBuddy: FINISH stage. Run this AFTER WorkBuddy is fully closed (tray icon too).
# It moves whatever the live pass could not (locked files), collapses the whole
# .workbuddy into ONE junction, relocates the workspace folder, then verifies.
$ErrorActionPreference = 'Continue'
$logFile = 'E:\WBData\_tools\migrate.log'

function Write-Log([string]$m) {
    Add-Content -LiteralPath $logFile -Value ('[{0}] {1}' -f (Get-Date -Format 'HH:mm:ss'), $m) -Encoding UTF8
}
function Get-DirCount([string]$p) {
    return ((Get-ChildItem -LiteralPath $p -Recurse -Force -File -ErrorAction SilentlyContinue | Measure-Object).Count)
}
function Get-DirSize([string]$p) {
    $s = (Get-ChildItem -LiteralPath $p -Recurse -Force -File -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum)
    if ($null -eq $s.Sum) { return [long]0 } else { return [long]$s.Sum }
}

# copy -> verify by file count -> delete source -> junction
function Move-Junction([string]$src, [string]$dst) {
    Write-Log "---- FINISH: $src"
    if (-not (Test-Path -LiteralPath $src)) { Write-Log '  gone already'; return }
    $it = Get-Item -LiteralPath $src -Force
    if ($it.Attributes -band [IO.FileAttributes]::ReparsePoint) { Write-Log '  already junction'; return }

    New-Item -ItemType Directory -Force -Path $dst | Out-Null
    robocopy "$src" "$dst" /E /COPY:DAT /DCOPY:DAT /R:2 /W:1 /NFL /NDL /NP /MT:8 | Out-Null
    $sc = Get-DirCount $src
    $dc = Get-DirCount $dst
    Write-Log "  src=$sc dst=$dc files"
    if ($dc -lt $sc) { Write-Log '  ABORT: destination looks incomplete'; return }

    Remove-Item -LiteralPath $src -Recurse -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 600
    if (Test-Path -LiteralPath $src) {
        Remove-Item -LiteralPath $src -Recurse -Force -ErrorAction SilentlyContinue
        Start-Sleep -Milliseconds 600
    }
    if (Test-Path -LiteralPath $src) { Write-Log ('  STILL LOCKED: {0} files left' -f (Get-DirCount $src)); return }
    New-Item -ItemType Junction -Path $src -Value $dst | Out-Null
    Write-Log "  DONE junction -> $dst"
}

Write-Log '===== FINISH stage start ====='

$proc = Get-Process -Name 'WorkBuddy' -ErrorAction SilentlyContinue
if ($proc) { Write-Log ('WARNING: WorkBuddy still running ({0} processes)' -f $proc.Count) }

$homeSrc = 'C:\Users\legion\.workbuddy'
$homeDst = 'E:\WBData\home\.workbuddy'
New-Item -ItemType Directory -Force -Path $homeDst | Out-Null

# 1) leftover real subfolders
Get-ChildItem -LiteralPath $homeSrc -Force -Directory -ErrorAction SilentlyContinue |
    Where-Object { -not ($_.Attributes -band [IO.FileAttributes]::ReparsePoint) } |
    ForEach-Object { Move-Junction $_.FullName (Join-Path $homeDst $_.Name) }

# 1b) normalize old stray junctions that point at E:\.workbuddy
Get-ChildItem -LiteralPath $homeSrc -Force -Directory -ErrorAction SilentlyContinue |
    Where-Object { ($_.Attributes -band [IO.FileAttributes]::ReparsePoint) -and (($_.Target -join '') -like 'E:\.workbuddy*') } |
    ForEach-Object {
        $name = $_.Name
        Write-Log "-- normalize old junction: $name"
        robocopy "$($_.FullName)" (Join-Path $homeDst $name) /E /COPY:DAT /DCOPY:DAT /R:1 /W:1 /NFL /NDL /NP /MT:8 | Out-Null
        [System.IO.Directory]::Delete($_.FullName, $false)
        New-Item -ItemType Junction -Path $_.FullName -Value (Join-Path $homeDst $name) | Out-Null
        Write-Log "   repointed -> $homeDst\$name"
    }

# 2) root-level files (*.db, *.db-wal, ...)
Get-ChildItem -LiteralPath $homeSrc -Force -File -ErrorAction SilentlyContinue | ForEach-Object {
    $t = Join-Path $homeDst $_.Name
    Copy-Item -LiteralPath $_.FullName -Destination $t -Force -ErrorAction SilentlyContinue
    if ((Test-Path -LiteralPath $t) -and ((Get-Item -LiteralPath $t).Length -eq $_.Length)) {
        Remove-Item -LiteralPath $_.FullName -Force -ErrorAction SilentlyContinue
        Write-Log "   moved file: $($_.Name)"
    } else { Write-Log "   FILE LOCKED: $($_.Name)" }
}

# 3) collapse parent into one junction
$remain = (Get-ChildItem -LiteralPath $homeSrc -Force -ErrorAction SilentlyContinue | Measure-Object).Count
Write-Log "parent remaining entries: $remain"
if ($remain -eq 0) {
    Remove-Item -LiteralPath $homeSrc -Recurse -Force -ErrorAction SilentlyContinue
    if (-not (Test-Path -LiteralPath $homeSrc)) {
        New-Item -ItemType Junction -Path $homeSrc -Value $homeDst | Out-Null
        Write-Log "OK: whole .workbuddy is now ONE junction -> $homeDst"
    } else { Write-Log 'parent still not removable' }
} else {
    Write-Log 'skip collapse: parent not empty (fine, subfolders already redirected)'
}

# 4) workspace folder: C:\Users\legion\WorkBuddy -> E:\WorkBuddy
Move-Junction 'C:\Users\legion\WorkBuddy' 'E:\WorkBuddy'

Write-Log '===== FINISH stage end ====='
