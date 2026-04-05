[CmdletBinding()]
param()

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvActivate = Join-Path $repoRoot "uni_project_env\Scripts\Activate.ps1"
$safeDirectory = $repoRoot.Replace("\", "/")

if (-not (Test-Path $venvActivate)) {
    Write-Error "Virtual environment activation script not found at: $venvActivate"
    return
}

Set-Location $repoRoot

# Prevent Git's ownership safety warning for this local repository on this machine.
git config --global --add safe.directory $safeDirectory | Out-Null

. $venvActivate

Write-Host ""
Write-Host "UniStudio environment is ready." -ForegroundColor Green
Write-Host "Project root: $repoRoot"
Write-Host "Python: $(Get-Command python | Select-Object -ExpandProperty Source)"
Write-Host "Next step: python manage.py runserver" -ForegroundColor Cyan
