$ErrorActionPreference = 'Stop'
$nodeRoot = 'C:\Users\Administrator\AppData\Local\RedTripToolchain\node'
$node = Join-Path $nodeRoot 'node.exe'
$pnpm = Join-Path $nodeRoot 'pnpm.cmd'
$root = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $root

Write-Host "ROOT=$root"
& $node -v
& $pnpm -v
& $pnpm install
& $pnpm --filter '@redtrip/contracts' build
& $pnpm --filter '@redtrip/web' typecheck
Write-Host 'BOOTSTRAP_OK'
