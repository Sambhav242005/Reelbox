$ErrorActionPreference = 'Stop'
$taskRoot = $PSScriptRoot
$taskPython = Join-Path (Split-Path $taskRoot -Parent) '.venv\Scripts\pythonw.exe'
if (-not (Test-Path -LiteralPath $taskPython)) {
    $taskRuntimePath = Join-Path $taskRoot 'runtime.json'
    if (-not (Test-Path -LiteralPath $taskRuntimePath)) {
        throw 'Install the Python environment using README.md before enabling startup.'
    }
    $taskPython = (Get-Content -LiteralPath $taskRuntimePath -Raw | ConvertFrom-Json).pythonw
}
if (-not (Test-Path -LiteralPath $taskPython)) { throw 'Configured Python executable does not exist.' }
$taskStartup = [Environment]::GetFolderPath('Startup')
$taskShell = New-Object -ComObject WScript.Shell
$taskLink = $taskShell.CreateShortcut((Join-Path $taskStartup 'Reelbox.lnk'))
$taskLink.TargetPath = $taskPython
$taskLink.Arguments = '"' + (Join-Path $taskRoot 'launch.py') + '" --daily'
$taskLink.WorkingDirectory = $taskRoot
$taskLink.WindowStyle = 7
$taskLink.Description = 'Start Reelbox and sync Instagram saves once per day at Windows sign-in.'
$taskLink.Save()
Write-Output 'Reelbox will start at Windows sign-in. Remove Reelbox.lnk from Startup to disable it.'
