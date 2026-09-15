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
    @('C:\Users\legion\AppData\Local\@genieworkbuddy-desktop-updater', 'E:\WBData\local\genieworkbuddy-updater')
)
foreach ($m in $maps) { Ensure-Junction $m[0] $m[1] }

# --- C:\Users\legion\.workbuddy ------------------------------------------------
# 2026-09-15 (晚): 用户要求把 C 盘的东西都搬到 E，于是重新纳入搬迁范围。
# （9-14 曾因「WorkBuddy 运行中搬迁会卡死/lock」而排除，这次用两道保险解决：
#   1) 登录时 WorkBuddy 不自启，本来就没在跑；
#   2) Ensure-Junction 的 -BlockIfRunning 会在删除前再查一次进程，
#      正在跑就直接放弃 —— 数据已拷到 E，下次登录再补增量即可。）
# 注意：218k 文件 / 1.6 GB，沙箱里预拷贝跟不上增量（会话备份目录一直在涨），
#       所以不做预拷贝，直接让登录守卫一次性整体搬迁。
Ensure-Junction 'C:\Users\legion\.workbuddy' 'E:\WBData\home\.workbuddy' `
    -BlockIfRunning @('WorkBuddy', 'CodeBuddy', 'workbuddy')

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
