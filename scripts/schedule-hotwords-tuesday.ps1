# Register a weekly Tuesday task to remind / run L3 hotword publish.
# Does NOT scrape Xiaohongshu; expects inbox filled by Agent first.
# Usage (Admin optional):
#   powershell -ExecutionPolicy Bypass -File scripts/schedule-hotwords-tuesday.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) { $Py = "python" }

$Action = New-ScheduledTaskAction -Execute $Py -Argument "`"$Root\scripts\update_hotwords.py`"" -WorkingDirectory $Root
# Every Tuesday 10:00
$Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Tuesday -At 10:00am
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName "RedTrip-Hotwords-Tuesday" -Action $Action -Trigger $Trigger -Settings $Settings -Force | Out-Null
Write-Host "Scheduled: RedTrip-Hotwords-Tuesday (Tue 10:00)"
Write-Host "Before each run, fill content/hotwords/inbox/week.json via collect_hotwords_weekly.txt"
