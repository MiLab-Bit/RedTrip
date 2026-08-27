$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$nodeRoot = Join-Path $env:LOCALAPPDATA 'RedTripToolchain\node'
$zipPath = Join-Path $env:TEMP 'node-v22.18.0-win-x64.zip'
$uri = 'https://nodejs.org/dist/v22.18.0/node-v22.18.0-win-x64.zip'
$parent = Split-Path $nodeRoot

New-Item -ItemType Directory -Force -Path $parent | Out-Null

if (-not (Test-Path (Join-Path $nodeRoot 'node.exe'))) {
  Write-Host "Downloading $uri"
  Invoke-WebRequest -Uri $uri -OutFile $zipPath -UseBasicParsing
  if (Test-Path $nodeRoot) {
    Remove-Item $nodeRoot -Recurse -Force
  }
  Expand-Archive -Path $zipPath -DestinationPath $parent -Force
  $extracted = Join-Path $parent 'node-v22.18.0-win-x64'
  if (Test-Path $extracted) {
    Rename-Item -Path $extracted -NewName 'node'
  }
}

$nodeExe = Join-Path $nodeRoot 'node.exe'
$npmCmd = Join-Path $nodeRoot 'npm.cmd'

& $nodeExe -v
& $npmCmd -v

Write-Host 'Installing pnpm globally...'
& $npmCmd install -g pnpm@9.15.0

$pnpmCmd = Join-Path $nodeRoot 'pnpm.cmd'
if (-not (Test-Path $pnpmCmd)) {
  $pnpmCmd = Join-Path $nodeRoot 'node_modules\pnpm\bin\pnpm.cmd'
}
& $pnpmCmd -v

$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
if ($userPath -notlike ("*" + $nodeRoot + "*")) {
  [Environment]::SetEnvironmentVariable('Path', ($nodeRoot + ';' + $userPath), 'User')
  Write-Host "Added to User PATH: $nodeRoot"
}

Write-Host "NODE_ROOT=$nodeRoot"
Write-Host 'READY'
