# WorkBuddy E-drive guard - runs from the Startup folder every logon.
# Makes every WorkBuddy path on C: a junction into E:, so whatever the app
# writes there in the future is stored on E: instead.

. 'E:\WBData\_tools\guard-core.ps1'

Log '===== guard run ====='

$maps = @(
    @('C:\Users\legion\.workbuddy-key-fallback',    'E:\WBData\home\.workbuddy-key-fallback'),
    @('C:\Users\legion\.codebuddy',                 'E:\WBData\home\.codebuddy'),
    @('C:\Users\legion\.cache',                     'E:\WBData\home\.cache'),
    @('C:\Users\legion\AppData\Local\pip\cache',    'E:\WBData\local\pip-cache'),
    @('C:\Users\legion\AppData\Roaming\npm',        'E:\WBData\roaming\npm'),
    @('C:\Users\legion\AppData\Roaming\WorkBuddy',  'E:\WBData\roaming\WorkBuddy'),
    @('C:\Users\legion\AppData\Roaming\workbuddy',  'E:\WBData\roaming\workbuddy'),
    @('C:\Users\legion\WorkBuddy',                  'E:\WorkBuddy'),
    # 2026-09-16: WorkBuddy 桌面版更新器下载缓存（installer.exe，单个 500MB+）。
    # 每次自动更新都会往这里丢一个新安装包，属于纯下载缓存，放 E 盘不影响更新。
    @('C:\Users\legion\AppData\Local\@genieworkbuddy-desktop-updater', 'E:\WBData\local\genieworkbuddy-updater'),
    # 2026-09-16: ComfyUI Desktop 的两个 C 盘落点（本轮新发现，共约 214MB）。
    #   1) 更新器下载缓存里的安装包（150MB+，纯下载缓存）
    #   2) Roaming 下的配置/日志目录（目录名含空格，注意引用）
    @('C:\Users\legion\AppData\Local\comfyui-desktop-2-updater', 'E:\WBData\local\comfyui-desktop-2-updater'),
    @('C:\Users\legion\AppData\Roaming\Comfy Desktop',           'E:\WBData\roaming\ComfyDesktop'),
    # 2026-09-18: Power BI Desktop 的运行缓存（WebView2 profile 257MB + ExtensionCache /
    #   LuciaCache / CertifiedExtensions / AnalysisServicesWorkspaces …，合计约 300MB）。
    #   每跑一次 Power BI 就往 C 盘写一份，属纯缓存，搬到 E 盘不影响使用（路径不变）。
    @('C:\Users\legion\AppData\Local\Microsoft\Power BI Desktop', 'E:\WBData\local\PowerBI-Desktop')
)
foreach ($m in $maps) { Ensure-Junction $m[0] $m[1] }

# --- C:\Users\legion\.workbuddy  (subdirectory migration) ----------------------
# 2026-09-18: user asked again to keep everything off C:. The .workbuddy ROOT still
# cannot be a junction - it is the LIVE WorkBuddy home (the running session and the
# interpreters this shell uses both live inside it), so the root handle stays locked.
# Policy change: instead of dropping the whole idea, migrate every SUBDIRECTORY
# (recursing into the ones that are held open) to E:\WBData\home\.workbuddy\<same>
# and junction it back. All paths stay identical, so no config, database, shortcut
# or registry entry has to change - the app cannot tell the difference.
#
# The heavy lifting runs DETACHED (migrate_deep.py) so logon is never blocked.
# That script has its own lock (no duplicate runs), its own rename probe as the
# final safety net, and it also repairs a junction that got replaced by a real
# directory. If the bundled python cannot be found - e.g. its own junction is
# broken - we fall back to a synchronous pass over the immediate children only.
$wbHome    = 'C:\Users\legion\.workbuddy'
$wbDstRoot = 'E:\WBData\home\.workbuddy'
if (Test-Path -LiteralPath $wbHome) {
    $wbRunning = @(Get-Process -Name 'WorkBuddy', 'workbuddy', 'WorkBuddy Helper' -ErrorAction SilentlyContinue).Count -gt 0
    if ($wbRunning) {
        Log 'workbuddy home: app is running - subdir migration deferred to next logon'
    } else {
        $py = Get-ChildItem -LiteralPath (Join-Path $wbHome 'binaries\python\versions') -Directory -ErrorAction SilentlyContinue |
              Sort-Object Name |
              ForEach-Object { Join-Path $_.FullName 'python.exe' } |
              Where-Object { Test-Path -LiteralPath $_ } |
              Select-Object -Last 1
        if ($py) {
            Start-Process -FilePath $py -ArgumentList '"E:\WBData\_tools\migrate_deep.py"' -WindowStyle Hidden
            Log ('workbuddy home: detached migration started via ' + $py)
        } else {
            Log 'workbuddy home: bundled python missing - synchronous fallback'
            New-Item -ItemType Directory -Force -Path $wbDstRoot | Out-Null
            Get-ChildItem -LiteralPath $wbHome -Force -Directory -ErrorAction SilentlyContinue | ForEach-Object {
                if ($_.Attributes -band [IO.FileAttributes]::ReparsePoint) { return }
                Ensure-Junction $_.FullName (Join-Path $wbDstRoot $_.Name)
            }
        }
    }
}

# stale WorkBuddy temp dirs left in the old TEMP location
$oldTemp = 'C:\Users\legion\AppData\Local\Temp'
if (Test-Path $oldTemp) {
    Get-ChildItem -LiteralPath $oldTemp -Force -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match 'workbuddy|codebuddy' -and -not ($_.Attributes -band [IO.FileAttributes]::ReparsePoint) } |
        ForEach-Object { Ensure-Junction $_.FullName ('E:\WBData\temp-junk\' + $_.Name) }
}

# keep WorkBuddy from turning its own login autostart back on
$cfg = Join-Path $env:USERPROFILE '.workbuddy\settings.json'
if (Test-Path -LiteralPath $cfg) {
    $txt = Get-Content -LiteralPath $cfg -Raw -ErrorAction SilentlyContinue
    if ($txt -match '"autoLaunchDesired"\s*:\s*true') {
        ($txt -replace '"autoLaunchDesired"\s*:\s*true', '"autoLaunchDesired": false') |
            Set-Content -LiteralPath $cfg -Encoding UTF8 -NoNewline
        Log 'settings.json: autoLaunchDesired reset to false'
    }
}
# also drop the Run value itself, not just mark it disabled
$run = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
if (Get-ItemProperty $run -Name 'WorkBuddy.WorkBuddy' -ErrorAction SilentlyContinue) {
    Remove-ItemProperty -Path $run -Name 'WorkBuddy.WorkBuddy' -Force -ErrorAction SilentlyContinue
    Log 'registry: WorkBuddy.WorkBuddy Run value removed'
}

$appr = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run'
if (-not (Get-ItemProperty $appr -Name 'WorkBuddy.WorkBuddy' -ErrorAction SilentlyContinue)) {
    $ft = [System.BitConverter]::GetBytes([datetime]::UtcNow.ToFileTimeUtc())
    New-ItemProperty -Path $appr -Name 'WorkBuddy.WorkBuddy' -Value ([byte[]](@(0x03,0x00,0x00,0x00) + $ft)) -PropertyType Binary -Force | Out-Null
    Log 'registry: WorkBuddy autostart marked disabled'
}

Log '===== guard done ====='
