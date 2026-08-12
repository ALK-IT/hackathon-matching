# AI agenci (code review / security review / UX review)

Lokalne skrypty reagujące na zmiany w GitHub, uruchamiane u Ciebie (lub członka zespołu)
przez lokalnie zalogowany **Claude Code** (subskrypcja Claude — bez klucza API i bez
rozliczania per token w Actions).

## Wymagania

- [GitHub CLI](https://cli.github.com/) (`gh`), zalogowane: `gh auth login`
- [Claude Code](https://claude.com/claude-code) zalogowany lokalnie (subskrypcja)
- PowerShell 5.1+ (Windows) lub PowerShell 7+ (cross-platform)

## Jak to działa

1. Ktoś dodaje etykietę **`ai-review`** do pull requesta.
2. `watch-repo.ps1` (odpytywany cyklicznie) wykrywa PR z tą etykietą.
3. Dla każdego takiego PR odpala `review-pr.ps1`:
   - zawsze: **code review** + **security review**,
   - jeśli PR dotyka `frontend/`: dodatkowo **UX/design-system review**.
4. Wynik trafia jako komentarz na PR, etykieta zmienia się na `ai-reviewed`.
5. Opcjonalnie: powiadomienie na Discord, że review gotowy (patrz niżej).

## Discord (opcjonalnie)

Skopiuj `.env.example` do `.env` w tym katalogu (plik `.env` jest w `.gitignore` — nie trafi do repo) i wklej URL webhooka Discorda:

```
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

Webhook tworzysz w Discordzie: Ustawienia kanału → Integracje → Webhooki → Nowy webhook → Kopiuj URL.

Powiadomienia z GitHub Actions (PR opened/merged, issue opened/closed, CI/deploy status) wymagają osobno ustawionego sekretu repo:

```powershell
gh secret set DISCORD_WEBHOOK_URL --repo ALK-IT/hackathon-matching
```

(ten sam webhook URL, tylko jako sekret repo zamiast lokalnego `.env` — GitHub Actions nie ma dostępu do Twojego lokalnego pliku).

## Uruchomienie

Jednorazowe sprawdzenie (np. z crona / Task Schedulera co kilka minut):

```powershell
./scripts/ai-agents/watch-repo.ps1 -Repo ALK-IT/hackathon-matching -Once
```

Ciągłe odpytywanie (proces działa w tle, co 5 min):

```powershell
./scripts/ai-agents/watch-repo.ps1 -Repo ALK-IT/hackathon-matching -PollSeconds 300
```

Ręczne odpalenie na konkretnym PR:

```powershell
./scripts/ai-agents/review-pr.ps1 -Repo ALK-IT/hackathon-matching -PRNumber 12
```

## Harmonogram (Windows Task Scheduler)

```powershell
schtasks /create /tn "ai-review-hackathon-matching" /sc minute /mo 10 `
  /tr "powershell.exe -File `"$PWD\scripts\ai-agents\watch-repo.ps1`" -Repo ALK-IT/hackathon-matching -Once" `
  /f
```

## Prompty

Prompty dla poszczególnych typów review są w [prompts/](prompts/) — dostosuj je do specyfiki projektu
(np. dopisz zasady z konkretnego SPEC-a albo inny zestaw reguł bezpieczeństwa).
