import { useState } from 'react'
import { runMatching, toErrorMessage, type Team } from './api'
import { EXPERIENCE_LEVEL_LABELS, PREFERRED_ROLE_LABELS, labelFor } from './submissionProfile'

// Maksymalny rozmiar zespołu - zgodnie z issue #27 bez pola wyboru. Uwaga:
// backend traktuje team_size jako GÓRNY LIMIT, nie docelowy rozmiar (przy
// 7 osobach wyjdą zespoły 3+2+2, nie 3+3+1) - nagłówek pokazuje realną
// liczebność. Backend przyjmuje 1-20; gdy dojdzie pole wyboru, wystarczy
// zamienić stałą na stan komponentu.
const TEAM_SIZE = 3

type Status = 'idle' | 'loading' | 'ready' | 'error'

function MatchResults() {
  const [teams, setTeams] = useState<Team[]>([])
  const [status, setStatus] = useState<Status>('idle')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  // Zespoły pobieramy wyłącznie po kliknięciu, nie przy wejściu na stronę:
  // matchowanie ZMIENIA stan (kasuje poprzedni podział), więc nie może
  // odpalać się samo. To ta sama zasada, dla której backend używa POST.
  const handleRunMatching = async () => {
    // POST /api/match kasuje istniejący podział i liczy nowy - dopóki
    // endpoint jest bez autoryzacji (#54), potwierdzenie chroni przynajmniej
    // przed odruchowym nadpisaniem gotowych zespołów (uwaga z review).
    if (!window.confirm('Uruchomienie zastąpi obecny podział na zespoły. Kontynuować?')) {
      return
    }
    setStatus('loading')
    setErrorMessage(null)

    let result: Team[]
    try {
      result = await runMatching(TEAM_SIZE)
    } catch (error) {
      setStatus('error')
      setErrorMessage(toErrorMessage(error))
      return
    }

    setTeams(result)
    setStatus('ready')
  }

  return (
    <section style={{ maxWidth: '40rem', margin: '3rem auto 0', textAlign: 'left' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: '1rem' }}>
        <h2 style={{ fontSize: '1.1rem' }}>Zespoły</h2>
        <button type="button" onClick={() => void handleRunMatching()} disabled={status === 'loading'}>
          {status === 'loading' ? 'Matchowanie...' : 'Uruchom matchowanie'}
        </button>
      </div>

      {status === 'idle' && (
        <p>Kliknij „Uruchom matchowanie", żeby podzielić zgłoszonych uczestników na zespoły.</p>
      )}

      {status === 'loading' && <p role="status">Układanie zespołów...</p>}

      {/* role="alert" ogłasza błąd czytnikom ekranu, a prefiks tekstowy
          sygnalizuje go niezależnie od koloru (WCAG 1.4.1 - uwaga z review). */}
      {status === 'error' && errorMessage && (
        <p role="alert" style={{ color: 'crimson' }}>
          Błąd: {errorMessage}
        </p>
      )}

      {/* Dziś nieosiągalne (pusta baza ucina wcześniej na 409), ale gdyby
          algorytm kiedyś oddał pustą listę, stan nie może zniknąć w nicość. */}
      {status === 'ready' && teams.length === 0 && (
        <p>Matchowanie wykonane, ale nie powstał żaden zespół.</p>
      )}

      {status === 'ready' &&
        teams.map((team, index) => (
          // Key i numer nagłówka z tego samego źródła (uwaga z review): lista
          // jest podmieniana w całości po każdym przebiegu, nigdy nie
          // przestawiana w miejscu, więc indeks jest tu stabilnym kluczem.
          <article key={index} style={{ border: '1px solid #ccc', borderRadius: '4px', padding: '.75rem 1rem', marginTop: '1rem' }}>
            <h3 style={{ fontSize: '1rem', margin: '0 0 .5rem' }}>
              Zespół {index + 1} ({team.members.length} os.)
            </h3>
            <ul style={{ margin: 0, paddingLeft: '1.25rem' }}>
              {team.members.map((member) => (
                <li key={member.id}>
                  {member.full_name} — {labelFor(member.preferred_role, PREFERRED_ROLE_LABELS)},{' '}
                  {labelFor(member.experience_level, EXPERIENCE_LEVEL_LABELS)}
                </li>
              ))}
            </ul>
          </article>
        ))}
    </section>
  )
}

export default MatchResults
