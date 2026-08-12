#Requires -Version 5.1
<#
Odpytuje repo o otwarte PR-y z etykietą 'ai-review' i odpala dla każdego review-pr.ps1
(lokalny Claude Code, subskrypcja - bez API-key/billing per token).

Uruchomienie jednorazowe (np. z Task Schedulera / crona / ręcznie):
  .\watch-repo.ps1 -Repo ALK-IT/nazwa-repo -Once

Uruchomienie ciągłe (odpytywanie co N sekund, Ctrl+C żeby przerwać):
  .\watch-repo.ps1 -Repo ALK-IT/nazwa-repo -PollSeconds 300
#>

param(
    [Parameter(Mandatory = $true)][string]$Repo,
    [int]$PollSeconds = 300,
    [switch]$Once
)

$ErrorActionPreference = "Stop"
$scriptRoot = $PSScriptRoot

function Invoke-Round {
    Write-Host "==> Sprawdzam PR-y z etykietą 'ai-review' w $Repo" -ForegroundColor Cyan
    $prs = gh pr list --repo $Repo --label "ai-review" --state open --json number | ConvertFrom-Json
    if (-not $prs -or $prs.Count -eq 0) {
        Write-Host "Brak PR-ów do przejrzenia." -ForegroundColor DarkGray
        return
    }
    foreach ($pr in $prs) {
        try {
            & (Join-Path $scriptRoot "review-pr.ps1") -Repo $Repo -PRNumber $pr.number
        }
        catch {
            Write-Host "!! Błąd przy PR #$($pr.number): $($_.Exception.Message)" -ForegroundColor Red
        }
    }
}

if ($Once) {
    Invoke-Round
}
else {
    while ($true) {
        Invoke-Round
        Start-Sleep -Seconds $PollSeconds
    }
}
