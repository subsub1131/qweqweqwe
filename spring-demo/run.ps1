$ErrorActionPreference = 'Stop'
$env:JAVA_HOME = [Environment]::GetEnvironmentVariable('JAVA_HOME', 'User')
if (-not $env:JAVA_HOME) { $env:JAVA_HOME = [Environment]::GetEnvironmentVariable('JAVA_HOME', 'Machine') }
if (-not $env:JAVA_HOME) { throw 'JAVA_HOME is not configured.' }
Push-Location $PSScriptRoot
try {
    & .\mvnw.cmd spring-boot:run
} finally {
    Pop-Location
}
