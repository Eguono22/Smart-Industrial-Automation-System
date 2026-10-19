# Shared authenticated session for operational validation scripts.
function New-SiasSession {
    param([string]$Root, [string]$Username)
    if (-not $Username) { throw 'Set SIAS_ADMIN_USERNAME or pass -Username for an administrator account.' }
    $password = $env:SIAS_ADMIN_PASSWORD
    if (-not $password) {
        $secure = Read-Host 'Administrator password' -AsSecureString
        $password = [System.Net.NetworkCredential]::new('', $secure).Password
    }
    $web = New-Object Microsoft.PowerShell.Commands.WebRequestSession
    $me = Invoke-RestMethod -Uri "$Root/api/auth/me" -WebSession $web
    $body = @{ username = $Username; password = $password } | ConvertTo-Json
    $login = Invoke-RestMethod -Uri "$Root/api/auth/login" -Method POST -WebSession $web -Headers @{ 'X-CSRF-Token' = $me.csrf_token } -ContentType 'application/json' -Body $body
    if ($login.user.role -ne 'admin') { throw 'Operational validation requires an administrator account.' }
    return @{ Session = $web; Headers = @{ 'X-CSRF-Token' = $login.csrf_token } }
}
