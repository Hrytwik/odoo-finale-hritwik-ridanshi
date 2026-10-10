# Walks the demo mill forward through the real screens' own endpoints, so the money and dispatch pages have real data:
#   supervisor ends the running dyeing runs -> QC passes the rolls -> dispatch loads one truck per buyer and confirms it
#   (which creates the invoice) -> accountant records a part payment -> supervisor marks attendance for the runs' day.
# Run with the API on :8000 and the web app on :3000, on a database loaded with `npm run db:demo`.
#   npm run demo:flow
# It only ever uses the seeded dev logins and goes through the same rules as the app: nothing is written to the database directly.
param([string]$Base = 'http://127.0.0.1:3000', [double]$PaidShare = 0.5)
$ErrorActionPreference = 'Stop'
$password = 'everest123'
$today = [TimeZoneInfo]::ConvertTimeBySystemTimeZoneId([DateTime]::UtcNow, 'India Standard Time').ToString('yyyy-MM-dd')

function Login($user) {
  $s = New-Object Microsoft.PowerShell.Commands.WebRequestSession
  $null = Invoke-WebRequest -Uri "$Base/api/auth/login" -Method POST -Body (@{ username = $user; password = $password } | ConvertTo-Json) -ContentType 'application/json' -WebSession $s -UseBasicParsing
  return $s
}
function Call($s, $method, $path, $body) {
  try {
    $a = @{ Uri = "$Base$path"; Method = $method; WebSession = $s; UseBasicParsing = $true; TimeoutSec = 60 }
    if ($body) { $a.Body = ($body | ConvertTo-Json -Depth 6); $a.ContentType = 'application/json' }
    $r = Invoke-WebRequest @a
    if (-not $r.Content) { return $null }
    $parsed = $r.Content | ConvertFrom-Json
    # Windows PowerShell hands a JSON list back as one object; send its items out one by one instead
    if ($parsed -is [array]) { $parsed | ForEach-Object { $_ } } else { $parsed }
  } catch {
    $msg = $_.ErrorDetails.Message
    throw "$method $path failed: $msg"
  }
}
function Step($text) { Write-Host "-- $text" -ForegroundColor Green }

$supervisor = Login 'supervisor'; $qc = Login 'qc'; $dispatch = Login 'dispatch'; $accountant = Login 'accountant'; $owner = Login 'owner'

Step 'Ending the running dyeing runs'
foreach ($run in @(Call $supervisor 'GET' '/api/runs?stage=dyeing' $null)) {
  if (-not $run.ended_at) { $null = Call $supervisor 'POST' "/api/runs/$($run.id)/end" @{}; "   ended dyeing run $($run.id) on $($run.machine_code)" }
}

Step 'Quality check: passing every roll that is waiting'
foreach ($roll in @(Call $qc 'GET' '/api/rolls?status=awaiting_qc' $null)) {
  $null = Call $qc 'POST' '/api/qc/inspections' @{ roll_code = $roll.code; verdict = 'pass'; notes = 'Passed in the demo flow' }
  "   $($roll.code) passed ($($roll.metres) m)"
}

Step 'Dispatch: one truck per buyer, then confirm (this creates the invoice)'
$orders = @{}; foreach ($o in @(Call $owner 'GET' '/api/orders' $null)) { $orders[$o.code] = $o }
$byBuyer = @{}
foreach ($roll in @(Call $dispatch 'GET' '/api/rolls?status=in_store' $null)) {
  $buyer = $orders[$roll.order_code].buyer
  if (-not $byBuyer.ContainsKey($buyer.id)) { $byBuyer[$buyer.id] = @{ name = $buyer.name; rolls = @() } }
  $byBuyer[$buyer.id].rolls += $roll.code
}
$truck = 0
foreach ($id in $byBuyer.Keys) {
  $truck++
  $d = Call $dispatch 'POST' '/api/dispatches' @{ buyer_id = [int]$id; vehicle_no = "KA01AB$(1230 + $truck)"; driver_name = 'Demo driver' }
  foreach ($code in $byBuyer[$id].rolls) { $d = Call $dispatch 'POST' "/api/dispatches/$($d.code)/items" @{ roll_code = $code } }
  $d = Call $dispatch 'POST' "/api/dispatches/$($d.code)/confirm" $null
  "   $($d.code) for $($byBuyer[$id].name): $($byBuyer[$id].rolls -join ', ') confirmed"
}

Step "Accounts: a part payment ($([int]($PaidShare * 100)) percent) on each unpaid invoice"
foreach ($row in @(Call $accountant 'GET' '/api/money/receivables' $null)) {
  if ($row.balance -gt 0 -and $row.paid -eq 0) {
    $amount = [Math]::Round($row.total * $PaidShare, 2)
    $null = Call $accountant 'POST' '/api/payments/buyer' @{ invoice_no = $row.invoice_no; amount = $amount; received_on = $today; reference = "NEFT-DEMO-$($row.invoice_no)" }
    "   $($row.invoice_no): received $amount of $($row.total)"
  }
}

Step 'Attendance: everyone present for each shift, today and yesterday (the runs started yesterday evening)'
$workers = @(Call $owner 'GET' '/api/workers' $null) | Where-Object { $_.active }
$yesterday = [DateTime]::ParseExact($today, 'yyyy-MM-dd', $null).AddDays(-1).ToString('yyyy-MM-dd')
foreach ($day in @($yesterday, $today)) {
  foreach ($shift in @(Call $owner 'GET' '/api/shifts' $null)) {
    try {
      $entries = @($workers | ForEach-Object { @{ worker_id = $_.id; status = 'present' } })
      $null = Call $supervisor 'POST' '/api/attendance' @{ date = $day; shift_id = $shift.id; entries = $entries }
      "   $day $($shift.name): $($entries.Count) present"
    } catch { "   $day $($shift.name): skipped ($($_.Exception.Message))" }
  }
}
Write-Host 'Done. Open Receivables, Dispatch and Month-end to see it.' -ForegroundColor Green
