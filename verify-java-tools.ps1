$ErrorActionPreference = 'Stop'
$jdk = [Environment]::GetEnvironmentVariable('JAVA_HOME', 'User')
$java = Join-Path $jdk 'bin\java.exe'
$tomcat = [Environment]::GetEnvironmentVariable('CATALINA_HOME', 'User')
$logRoot = Join-Path $PSScriptRoot 'spring-demo\target'
$processes = @()
try {
    foreach ($port in @(8080, 8081)) {
        if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) {
            throw ('Port already in use; will not stop another service: ' + $port)
        }
    }
    # Bind the standalone development server to this computer.
    $serverXml = Join-Path $tomcat 'conf\server.xml'
    $serverConfig = [IO.File]::ReadAllText($serverXml)
    if ($serverConfig.Contains('<Connector port="8080"')) {
        $serverConfig = $serverConfig.Replace('<Connector port="8080"', '<Connector address="127.0.0.1" port="8080"')
        [IO.File]::WriteAllText($serverXml, $serverConfig, [Text.UTF8Encoding]::new($false))
    }
    $tomcatArgs = @(
        ('-Dcatalina.home="' + $tomcat + '"'),
        ('-Dcatalina.base="' + $tomcat + '"'),
        ('-Djava.io.tmpdir="' + (Join-Path $tomcat 'temp') + '"'),
        '-classpath',
        ('"' + (Join-Path $tomcat 'bin\bootstrap.jar') + ';' + (Join-Path $tomcat 'bin\tomcat-juli.jar') + '"'),
        'org.apache.catalina.startup.Bootstrap', 'start'
    )
    $tomcatProcess = Start-Process -FilePath $java -ArgumentList $tomcatArgs -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logRoot 'tomcat-check.out.log') -RedirectStandardError (Join-Path $logRoot 'tomcat-check.err.log')
    $processes += $tomcatProcess
    $bootJar = Join-Path $logRoot 'spring-demo-0.0.1-SNAPSHOT.jar'
    $bootProcess = Start-Process -FilePath $java -ArgumentList @('-jar', ('"' + $bootJar + '"')) -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logRoot 'spring-check.out.log') -RedirectStandardError (Join-Path $logRoot 'spring-check.err.log')
    $processes += $bootProcess
    foreach ($url in @('http://127.0.0.1:8080/', 'http://127.0.0.1:8081/')) {
        $response = $null
        for ($attempt = 0; $attempt -lt 25; $attempt++) {
            try {
                $response = Invoke-WebRequest -Uri $url -TimeoutSec 2
                if ($response.StatusCode -eq 200) { break }
            } catch { Start-Sleep -Milliseconds 500 }
        }
        if (-not $response -or $response.StatusCode -ne 200) { throw ('HTTP check failed: ' + $url) }
        if ($url -like '*8081*') {
            $body = $response.Content | ConvertFrom-Json
            if ($body.status -ne 'ok') { throw 'Spring Boot response did not match.' }
            Write-Output ('Spring Boot HTTP 200: ' + $response.Content)
        } else {
            Write-Output 'Standalone Tomcat HTTP 200 on 127.0.0.1:8080.'
        }
    }
} finally {
    foreach ($process in $processes) {
        if (-not $process.HasExited) { Stop-Process -Id $process.Id -ErrorAction SilentlyContinue }
    }
}
$ide = Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Packages\VMware.SpringToolSuite_Microsoft.Winget.Source_8wekyb3d8bbwe\sts-5.0.1.RELEASE\SpringToolsForEclipse.exe'
if (-not (Test-Path -LiteralPath $ide)) { throw 'Spring Tools IDE executable not found.' }
$desktop = [Environment]::GetFolderPath('DesktopDirectory')
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut((Join-Path $desktop 'Spring Tools.lnk'))
$shortcut.TargetPath = $ide
$shortcut.WorkingDirectory = Split-Path $ide
$shortcut.Save()
Write-Output ('IDE shortcut created: ' + (Join-Path $desktop 'Spring Tools.lnk'))
Write-Output 'HTTP verification complete; temporary servers stopped.'
