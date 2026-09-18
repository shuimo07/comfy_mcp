$ErrorActionPreference = 'Continue'
$out = @()
foreach ($f in @('E:\WBData\_tools\guard.ps1', 'E:\WBData\_tools\guard-core.ps1')) {
    $tokens = $null
    $errors = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile($f, [ref]$tokens, [ref]$errors)
    if ($errors.Count -eq 0) {
        $out += "OK    $f"
    } else {
        $out += "ERR   $f"
        foreach ($e in $errors) { $out += ("      line {0}: {1}" -f $e.Extent.StartLineNumber, $e.Message) }
    }
}
$out += '--- guard.ps1 .workbuddy block ---'
$out += (Get-Content -LiteralPath 'E:\WBData\_tools\guard.ps1' -Encoding UTF8 | Select-String -Pattern 'workbuddy' -Context 0,0 | ForEach-Object { $_.Line })
Set-Content -LiteralPath 'E:\WBData\_tools\_ps_check.txt' -Value $out -Encoding UTF8
