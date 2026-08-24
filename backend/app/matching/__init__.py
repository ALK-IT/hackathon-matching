"""Algorytmy dopasowania zgłoszeń w zespoły.

Osobny pakiet, a nie kolejny plik w `app/services/`, bo tu ma powstać kilka
wariantów algorytmu porównywanych ze sobą (baseline, potem wersja
uwzględniająca profil uczestnika). `app/services/` zostaje warstwą, która
te algorytmy uruchamia i zapisuje wyniki - sama logika doboru jest czysta
i nie wie nic o bazie ani o HTTP.

Warianty i kryteria, które optymalizują, opisuje [README.md](README.md):
`baseline.random_teams` (punkt odniesienia) i `balanced.balanced_teams`
(wyrównane doświadczenie, różnorodność ról i umiejętności).
"""
