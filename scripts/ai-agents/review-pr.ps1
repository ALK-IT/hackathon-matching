#Requires -Version 5.1
<#
Uruchamia lokalne AI code review / security review / UX review na pojedynczym PR,
korzystając z lokalnie zalogowanego Claude Code (subskrypcja, bez API-key/billing per token)
oraz z GitHub CLI (gh) do pobrania diffu i wysłania komentarza.

Wywoływane automatycznie przez watch-repo.ps1 (label 'ai-review'), albo ręcznie:
  .\review-pr.ps1 -Repo ALK-IT/nazwa-repo -PRNumber 12
#>

param(
    [Parameter(Mandatory = $true)][string]$Repo,
    [Parameter(Mandatory = $true)][int]$PRNumber,
    [switch]$NoLabelSwap
)

$ErrorActionPreference = "Stop"
$scriptRoot = $PSScriptRoot
$promptsDir = Join-Path $scriptRoot "prompts"

$envFile = Join-Path $scriptRoot ".env"
if (Test-Path $envFile) {
    Get-Content -LiteralPath $envFile | Where-Object { $_ -match "^\s*[^#\s][^=]*=" } | ForEach-Object {
        $key, $value = $_.Split("=", 2)
        [System.Environment]::SetEnvironmentVariable($key.Trim(), $value.Trim())
    }
}

function Send-DiscordNotification([string]$message) {
    if (-not $env:DISCORD_WEBHOOK_URL) { return }
    try {
        Invoke-RestMethod -Uri $env:DISCORD_WEBHOOK_URL -Method Post -ContentType "application/json" -Body (@{ content = $message } | ConvertTo-Json) | Out-Null
    }
    catch {
        Write-Host "!! Nie udało się wysłać powiadomienia Discord: $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

function Invoke-Claude([string]$prompt) {
    $tmp = New-TemporaryFile
    try {
        Set-Content -LiteralPath $tmp -Value $prompt -Encoding UTF8
        $result = Get-Content -Raw -LiteralPath $tmp -Encoding UTF8 | & claude -p --output-format text
        return ($result -join "`n")
    }
    finally {
        Remove-Item $tmp -ErrorAction SilentlyContinue
    }
}

Write-Host "==> Pobieram dane PR #$PRNumber z $Repo" -ForegroundColor Cyan
$prJson = gh pr view $PRNumber --repo $Repo --json number,title,body,files,url | ConvertFrom-Json
$diff = gh pr diff $PRNumber --repo $Repo
$changedFiles = $prJson.files | ForEach-Object { $_.path }
$touchesFrontend = $changedFiles | Where-Object { $_ -like "frontend/*" } | Select-Object -First 1

$reviews = @("code-review", "security-review")
if ($touchesFrontend) { $reviews += "ux-review" }

$commentParts = @("## Automatyczny przegląd AI (lokalny Claude Code)`n")

# --- Deterministyczny spec-check (bez wywołania Claude) ---
$hasSpecRef = ($prJson.title + " " + $prJson.body) -match "SPEC-\d{3}"
$isNonTrivial = $changedFiles.Count -gt 3
if ($isNonTrivial -and -not $hasSpecRef) {
    $warning = "Ten PR zmienia $($changedFiles.Count) plików i nie odnosi się do żadnego SPEC-a (.ai/specs/). " +
               "Jeśli to nietrywialna zmiana, dopisz odniesienie w opisie PR (Spec: SPEC-XXX) albo utwórz spec przez /new-spec."
    $commentParts += "### Spec-check`n`n:warning: $warning`n"
}

foreach ($reviewType in $reviews) {
    Write-Host "==> Uruchamiam $reviewType" -ForegroundColor Cyan
    $template = Get-Content -Raw -LiteralPath (Join-Path $promptsDir "$reviewType.md") -Encoding UTF8
    $prompt = $template.Replace("{{PR_NUMBER}}", "$PRNumber").Replace("{{DIFF}}", $diff)
    $output = Invoke-Claude $prompt
    $title = switch ($reviewType) {
        "code-review" { "Code review" }
        "security-review" { "Security review" }
        "ux-review" { "UI/UX review" }
    }
    $commentParts += "### $title`n`n$output`n"
}

$commentBody = $commentParts -join "`n"
$commentFile = New-TemporaryFile
try {
    Set-Content -LiteralPath $commentFile -Value $commentBody -Encoding UTF8
    gh pr comment $PRNumber --repo $Repo --body-file $commentFile | Out-Null
    Write-Host "OK: skomentowano PR #$PRNumber" -ForegroundColor Green
}
finally {
    Remove-Item $commentFile -ErrorAction SilentlyContinue
}

Send-DiscordNotification "🤖 AI review gotowy dla PR #$PRNumber ($Repo): $($prJson.url)"

if (-not $NoLabelSwap) {
    try {
        gh pr edit $PRNumber --repo $Repo --remove-label "ai-review" --add-label "ai-reviewed" | Out-Null
    }
    catch {
        Write-Host "!! Nie udało się podmienić etykiety (może już nie istnieć): $($_.Exception.Message)" -ForegroundColor Yellow
    }
}
