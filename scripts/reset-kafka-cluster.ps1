<#
Reset Kafka cluster ID mismatch after ZooKeeper data reset.

What it does:
1) Stops kafka and zookeeper services (compose)
2) Removes all meta.properties files under ./data/kafka (bind-mounted into /kafka)
3) Optionally resets ZooKeeper named volumes (use -ResetZookeeper)
4) Starts zookeeper, then starts kafka

Usage:
  # Use base compose (DB bind mount)
  .\scripts\reset-kafka-cluster.ps1

  # Use Windows override (switch DB to named volume)
  .\scripts\reset-kafka-cluster.ps1 -UseWinOverride

  # Also reset ZooKeeper volumes (wipes ZK data)
  .\scripts\reset-kafka-cluster.ps1 -ResetZookeeper

Helpful debug commands:
  docker compose logs kafka -f
  docker compose logs zookeeper -f
  docker compose exec kafka bash
    kafka-topics.sh --describe --bootstrap-server kafka:9092
    kafka-console-consumer.sh --bootstrap-server=kafka:9092 --topic events --partition 0 --offset earliest
#>

param(
  [switch]$UseWinOverride,
  [switch]$ResetZookeeper
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# Compose file arguments (always include base). Add Windows override if requested or present.
$composeArgs = @('-f', "./docker-compose.yml")
if ($UseWinOverride -or (Test-Path './docker-compose.win.yaml')) {
  $composeArgs += @('-f', "./docker-compose.win.yaml")
}

function Run-Compose {
  param([Parameter(Mandatory)] [string[]] $Args)
  Write-Host "docker compose $($Args -join ' ')" -ForegroundColor Cyan
  docker compose @Args
}

# 1) Stop kafka and zookeeper (ignore errors if not running)
try {
  Run-Compose -Args ($composeArgs + @('stop', 'kafka', 'zookeeper')) | Out-Null
} catch {
  Write-Warning "Compose stop failed or services not running: $($_.Exception.Message)"
}

# 2) Remove Kafka meta.properties under ./data/kafka
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
$kafkaData = Join-Path $repoRoot 'data/kafka'
if (Test-Path $kafkaData) {
  $metaFiles = Get-ChildItem -Path $kafkaData -Recurse -Filter 'meta.properties' -ErrorAction SilentlyContinue
  if ($metaFiles.Count -gt 0) {
    foreach ($f in $metaFiles) {
      Write-Host "Deleting: $($f.FullName)" -ForegroundColor Yellow
      Remove-Item -LiteralPath $f.FullName -Force -ErrorAction SilentlyContinue
    }
  } else {
    Write-Host "No meta.properties found under $kafkaData" -ForegroundColor DarkYellow
  }
} else {
  Write-Host "Kafka data directory not found: $kafkaData (nothing to delete)" -ForegroundColor DarkYellow
}

# 3) Optionally reset ZooKeeper named volumes (wipe ZK state)
if ($ResetZookeeper) {
  try {
    Run-Compose -Args ($composeArgs + @('down', 'zookeeper')) | Out-Null
  } catch {
    Write-Warning "Compose down zookeeper failed: $($_.Exception.Message)"
  }
  $projectName = Split-Path -Leaf (Get-Location)
  $zkDataVol = "${projectName}_zookeeper_data"
  $zkLogVol  = "${projectName}_zookeeper_log"
  Write-Host "Removing volumes: $zkDataVol, $zkLogVol" -ForegroundColor Yellow
  try { docker volume rm $zkDataVol $zkLogVol | Out-Null } catch { Write-Warning $_ }
}

# 4) Start zookeeper, wait a bit, then start kafka
Run-Compose -Args ($composeArgs + @('up', '-d', 'zookeeper')) | Out-Null
Start-Sleep -Seconds 3
Run-Compose -Args ($composeArgs + @('up', '-d', 'kafka')) | Out-Null

Write-Host "Done. Tail logs with:\n  docker compose $($composeArgs -join ' ') logs -f zookeeper\n  docker compose $($composeArgs -join ' ') logs -f kafka" -ForegroundColor Green
