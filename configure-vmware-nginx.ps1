$ErrorActionPreference = 'Stop'
$configPath = 'C:\ProgramData\VMware\vmnetnat.conf'
$original = [IO.File]::ReadAllText($configPath)
if ($original -notmatch '(?m)^device\s*=\s*vmnet8\s*$' -or $original -notmatch '(?m)^ip\s*=\s*100\.100\.100\.2/24\s*$') {
    throw 'Unexpected NAT network configuration; no changes made.'
}
$sectionMatch = [regex]::Match($original, '(?ms)^\[incomingtcp\]\r?\n(.*?)(?=^\[|\z)')
if (-not $sectionMatch.Success) { throw 'TCP forwarding section not found.' }
$rules = @('80 = 100.100.100.10:80', '443 = 100.100.100.10:443')
$missing = @()
foreach ($port in @(80, 443)) {
    $existing = [regex]::Match($sectionMatch.Groups[1].Value, '(?m)^\s*' + $port + '\s*=\s*([^\r\n]+)')
    if ($existing.Success) {
        if ($existing.Groups[1].Value.Trim() -ne ('100.100.100.10:' + $port)) { throw ('Conflicting forwarding rule for port ' + $port) }
    } else {
        if (Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue) { throw ('Host port ' + $port + ' is already used; no changes made.') }
        $missing += ($port.ToString() + ' = 100.100.100.10:' + $port)
    }
}
$service = @(Get-Service | Where-Object { $_.DisplayName -eq 'VMware NAT Service' })
if ($service.Count -ne 1) { throw 'Expected exactly one VMware NAT Service.' }
if ($missing.Count -gt 0) {
    $backupPath = $configPath + '.backup-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
    Copy-Item -LiteralPath $configPath -Destination $backupPath
    if ([IO.File]::ReadAllText($configPath) -ne $original) { throw 'Configuration changed during inspection; no edits applied.' }
    $insertAt = $sectionMatch.Index + $sectionMatch.Length
    $updated = $original.Insert($insertAt, (($missing -join "`r`n") + "`r`n"))
    $written = $false
    try {
        [IO.File]::WriteAllText($configPath, $updated, [Text.UTF8Encoding]::new($false))
        $written = $true
        Restart-Service -InputObject $service[0]
        $service[0].WaitForStatus([System.ServiceProcess.ServiceControllerStatus]::Running, [TimeSpan]::FromSeconds(20))
    } catch {
        if ($written) {
            [IO.File]::WriteAllText($configPath, $original, [Text.UTF8Encoding]::new($false))
            Restart-Service -InputObject $service[0] -ErrorAction Continue
        }
        throw
    }
    Write-Output ('Backup=' + $backupPath)
}
Write-Output 'Active requested rules:'
Select-String -LiteralPath $configPath -Pattern '^80\s*=', '^443\s*='
Get-Service -Name $service[0].Name | Format-Table Name,Status
Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $_.LocalPort -in 80,443 } | Format-Table LocalAddress,LocalPort,OwningProcess
