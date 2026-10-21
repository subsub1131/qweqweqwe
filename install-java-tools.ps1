$ErrorActionPreference = 'Stop'
$jdk = Get-ChildItem 'C:\Program Files\Eclipse Adoptium' -Directory |
    Where-Object { $_.Name -like 'jdk-21*' } | Sort-Object Name -Descending | Select-Object -First 1
if (-not $jdk) { throw 'JDK 21 installation was not found.' }
$env:JAVA_HOME = $jdk.FullName
[Environment]::SetEnvironmentVariable('JAVA_HOME', $jdk.FullName, 'User')

$programRoot = Join-Path $env:LOCALAPPDATA 'Programs\ApacheTomcat'
$tomcatHome = Join-Path $programRoot 'apache-tomcat-11.0.27'
$downloadRoot = Join-Path $env:TEMP 'codex-java-tools-20261015'
New-Item -ItemType Directory -Path $downloadRoot, $programRoot -Force | Out-Null
$archive = Join-Path $downloadRoot 'apache-tomcat-11.0.27-windows-x64.zip'
$source = 'https://downloads.apache.org/tomcat/tomcat-11/v11.0.27/bin/apache-tomcat-11.0.27-windows-x64.zip'
if (-not (Test-Path -LiteralPath (Join-Path $tomcatHome 'bin\catalina.bat'))) {
    Invoke-WebRequest -Uri $source -OutFile $archive
    $checksum = (Invoke-WebRequest -Uri ($source + '.sha512')).Content
    if ($checksum -is [byte[]]) { $checksum = [Text.Encoding]::UTF8.GetString($checksum) }
    $expected = [regex]::Match([string]$checksum, '(?i)\b[a-f0-9]{128}\b').Value
    $actual = (Get-FileHash -LiteralPath $archive -Algorithm SHA512).Hash
    if (-not $expected -or $expected -ne $actual) { throw 'Tomcat SHA-512 verification failed.' }
    Expand-Archive -LiteralPath $archive -DestinationPath $programRoot
    Write-Output 'Tomcat download checksum verified and archive extracted.'
}
[Environment]::SetEnvironmentVariable('CATALINA_HOME', $tomcatHome, 'User')
$env:CATALINA_HOME = $tomcatHome
$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
$pathEntries = @($userPath -split ';' | Where-Object { $_ })
foreach ($entry in @((Join-Path $jdk.FullName 'bin'), (Join-Path $tomcatHome 'bin'))) {
    if ($pathEntries -notcontains $entry) { $pathEntries += $entry }
}
[Environment]::SetEnvironmentVariable('Path', ($pathEntries -join ';'), 'User')
$env:Path = (Join-Path $jdk.FullName 'bin') + ';' + $env:Path
& (Join-Path $jdk.FullName 'bin\java.exe') -version
& (Join-Path $jdk.FullName 'bin\javac.exe') -version
& (Join-Path $tomcatHome 'bin\catalina.bat') version
if ($LASTEXITCODE -ne 0) { throw 'Tomcat version verification failed.' }

$project = Join-Path $PSScriptRoot 'spring-demo'
if (-not (Test-Path -LiteralPath $project)) {
    $starter = Join-Path $downloadRoot 'spring-demo.zip'
    $starterUrl = 'https://start.spring.io/starter.zip?type=maven-project&language=java&javaVersion=21&groupId=com.example&artifactId=spring-demo&name=spring-demo&packageName=com.example.springdemo&dependencies=web'
    Invoke-WebRequest -Uri $starterUrl -OutFile $starter
    Expand-Archive -LiteralPath $starter -DestinationPath $project
    Write-Output 'Spring Boot starter with Maven Wrapper created.'
}
Write-Output ('JAVA_HOME=' + $jdk.FullName)
Write-Output ('CATALINA_HOME=' + $tomcatHome)
Write-Output ('Spring project=' + $project)
