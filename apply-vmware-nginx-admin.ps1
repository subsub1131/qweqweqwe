$ErrorActionPreference = 'Stop'
$result = Join-Path $PSScriptRoot 'vmware-nginx-result.log'
try {
    & (Join-Path $PSScriptRoot 'configure-vmware-nginx.ps1') *>&1 | Out-File -LiteralPath $result -Encoding utf8
    Add-Content -LiteralPath $result -Value 'RESULT=SUCCESS'
    exit 0
} catch {
    $_ | Out-String | Add-Content -LiteralPath $result
    Add-Content -LiteralPath $result -Value 'RESULT=FAILED'
    exit 1
}
