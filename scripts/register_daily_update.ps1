param(
    [string]$TaskName = "NSE 1000 Crore Screener Update",
    [string]$ProjectPath = (Resolve-Path "$PSScriptRoot\..").Path,
    [string]$PythonPath = "python"
)

$scriptPath = Join-Path $ProjectPath "scripts\update_data.py"

if (-not (Test-Path $scriptPath)) {
    throw "Could not find updater script at $scriptPath"
}

$action = New-ScheduledTaskAction `
    -Execute $PythonPath `
    -Argument "`"$scriptPath`"" `
    -WorkingDirectory $ProjectPath

$trigger = New-ScheduledTaskTrigger -Daily -At 5:00PM
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "Updates data\stocks.json for the local NSE 1000 crore screener every day at 5:00 PM." `
    -Force

Write-Host "Registered '$TaskName' to run daily at 5:00 PM."
