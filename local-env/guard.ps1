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
    @('C:\Users\legion\AppData\Roaming\Comfy Desktop',           'E:\WBData\roaming\ComfyDesktop')
)
foreach ($m in $maps) { Ensure-Junction $m[0] $m[1] }

# --- C:\Users\legion\.workbuddy ------------------------------------------------
# 2026-09-16: 用户明确决定「就不管了，任之吧」—— 停止搬迁，保持 C 盘真实目录。
# 历史：曾整体搬迁（218k 文件 / 2.4 GB），但沙箱预拷贝跟不上增量（会话备份目录一直涨），
#       且始终被运行中的 WorkBuddy 句柄死锁，反复 ABORT。
# ⛔ 禁止再把它加回 $maps、也禁止恢复本段 Ensure-Junction 调用。
#    （对应记忆：~/.workbuddy/MEMORY.md「存储」章节 2026-09-16 更新）

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
