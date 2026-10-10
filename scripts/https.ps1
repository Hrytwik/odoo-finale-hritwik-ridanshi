# Starts Caddy so a phone can open the app over HTTPS (phone cameras need it for the roll scanner).
# Usage (from the repo root, with `npm run dev` already running in another terminal):  npm run https
$ErrorActionPreference = 'Stop'
$caddy = (Get-Command caddy -ErrorAction SilentlyContinue).Source
if (-not $caddy) { Write-Host 'Caddy is not installed. Install it with:  winget install CaddyServer.Caddy   (then open a new terminal)'; exit 1 }

# the laptop's Wi-Fi / LAN address, ignoring virtual adapters (VMware, WSL, Docker)
$ip = Get-NetIPAddress -AddressFamily IPv4 |
  Where-Object { $_.IPAddress -match '^(192\.168|10\.|172\.(1[6-9]|2\d|3[01]))\.' -and $_.InterfaceAlias -notmatch 'vEthernet|WSL|VMware|VirtualBox|Loopback|Docker' } |
  Select-Object -First 1 -ExpandProperty IPAddress
if (-not $ip) { Write-Host 'No Wi-Fi / LAN address found. Connect the laptop to the same Wi-Fi as the phone.'; exit 1 }
$env:LAN_IP = $ip

Write-Host ''
Write-Host "On the phone (same Wi-Fi), open:  https://${ip}:8443"
Write-Host 'The first time, the phone warns about the certificate: choose Advanced / Proceed (it is the laptop''s own local certificate).'
Write-Host "Camera check page (owner login):  https://${ip}:8443/dev/camera"
Write-Host 'If the phone cannot connect, Windows Firewall is blocking port 8443 (a Wi-Fi marked "Public" blocks incoming connections).'
Write-Host 'Run this once in PowerShell as administrator, and remove it after testing:'
Write-Host '  New-NetFirewallRule -DisplayName "Everest HTTPS 8443" -Direction Inbound -Protocol TCP -LocalPort 8443 -Action Allow -Profile Any'
Write-Host '  Remove-NetFirewallRule -DisplayName "Everest HTTPS 8443"    # when you are done'
Write-Host ''
& $caddy run --config (Join-Path $PSScriptRoot '..\Caddyfile')
