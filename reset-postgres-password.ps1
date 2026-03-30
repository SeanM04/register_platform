# Run this script from an elevated PowerShell window.
[CmdletBinding()]
param(
    [string]$ServiceName = "postgresql-x64-18",
    [string]$DataDir = "C:\Program Files\PostgreSQL\18\data",
    [string]$PsqlPath = "C:\Program Files\PostgreSQL\18\bin\psql.exe",
    [string]$DbUser = "postgres"
)

$ErrorActionPreference = "Stop"

function Test-IsAdministrator {
    $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($currentUser)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function ConvertTo-PlainText([Security.SecureString]$SecureString) {
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureString)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}

if (-not (Test-IsAdministrator)) {
    throw "Please run this script in PowerShell as Administrator."
}

$pgHbaPath = Join-Path $DataDir "pg_hba.conf"
$backupPath = Join-Path $DataDir "pg_hba.conf.bak"

if (-not (Test-Path $pgHbaPath)) {
    throw "Could not find pg_hba.conf at $pgHbaPath"
}

if (-not (Test-Path $PsqlPath)) {
    throw "Could not find psql.exe at $PsqlPath"
}

$securePassword = Read-Host "Enter a new password for the '$DbUser' user" -AsSecureString
$confirmPassword = Read-Host "Confirm the new password" -AsSecureString
$plainPassword = ConvertTo-PlainText $securePassword
$plainConfirm = ConvertTo-PlainText $confirmPassword

if ([string]::IsNullOrWhiteSpace($plainPassword)) {
    throw "The password cannot be empty."
}

if ($plainPassword -ne $plainConfirm) {
    throw "The passwords did not match."
}

$escapedPassword = $plainPassword.Replace("'", "''")
$originalContent = Get-Content $pgHbaPath -Raw

if (-not (Test-Path $backupPath)) {
    Copy-Item $pgHbaPath $backupPath
}

$updatedContent = $originalContent `
    -replace '(?m)^(host\s+all\s+all\s+127\.0\.0\.1/32\s+)(\S+)', '${1}trust' `
    -replace '(?m)^(host\s+all\s+all\s+::1/128\s+)(\S+)', '${1}trust' `
    -replace '(?m)^(local\s+all\s+all\s+)(\S+)', '${1}trust'

if ($updatedContent -eq $originalContent) {
    throw "No matching localhost authentication lines were updated in pg_hba.conf."
}

Set-Content -Path $pgHbaPath -Value $updatedContent

try {
    Restart-Service $ServiceName

    & $PsqlPath -U $DbUser -h localhost -d postgres -c "ALTER USER $DbUser WITH PASSWORD '$escapedPassword';"
    if ($LASTEXITCODE -ne 0) {
        throw "psql failed to update the password."
    }

    Set-Content -Path $pgHbaPath -Value $originalContent
    Restart-Service $ServiceName

    Write-Host ""
    Write-Host "Password updated successfully for user '$DbUser'." -ForegroundColor Green
    Write-Host "You can now sign in through pgAdmin with the new password."
}
catch {
    Set-Content -Path $pgHbaPath -Value $originalContent
    Restart-Service $ServiceName -ErrorAction SilentlyContinue
    throw
}
finally {
    $plainPassword = $null
    $plainConfirm = $null
}
