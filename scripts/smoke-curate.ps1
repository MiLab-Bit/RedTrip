# ASCII-only smoke (avoid encoding issues). Prefer toolchain copy if needed.
$ErrorActionPreference = 'Stop'
$body = (@{
  slots = @{
    tone = 'lite'
    duration_min = 90
    companions = 'duo'
    audience = 'adult'
    scene = 'site'
    delivery = 'route'
  }
  retry_count = 0
} | ConvertTo-Json -Depth 5)

$r1 = Invoke-RestMethod -Uri 'http://127.0.0.1:8787/v1/curate' -Method Post -Body $body -ContentType 'application/json'
Write-Host ('direct status=' + $r1.status + ' stops=' + $r1.envelope.route.stops.Count)
$r2 = Invoke-RestMethod -Uri 'http://127.0.0.1:5173/v1/curate' -Method Post -Body $body -ContentType 'application/json'
Write-Host ('proxy status=' + $r2.status + ' stops=' + $r2.envelope.route.stops.Count)
Write-Host 'SMOKE_OK'
