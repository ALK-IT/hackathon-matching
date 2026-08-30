import { useState } from 'react'
import { EXPERIENCE_LEVEL_LABELS, PREFERRED_ROLE_LABELS, labelFor } from './submissionProfile'
import type { Submission } from './SubmissionList'

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

// Rozmiar zespołu na sztywno - zgodnie z issue #27. Backend przyjmuje 1-20,
// więc gdy dojdzie pole wyboru, wystarczy zamienić stałą na stan komponentu.
const TEAM_SIZE = 3

export type Team = {
  id: number
  members: Submission[]
  created_at: string
}

type Status = 'idle' | 'loading' | 'ready' | 'error'

/** Wyciąga komunikat z odpowiedzi backendu.
 *
 * Backend zwraca `detail` jako tekst (409 - brak zgłoszeń) albo listę błędów
 * walidacji (422). Przy rozmiarze zespołu na sztywno 422 nie powinno się
 * zdarzyć, ale odpowiedź obsługujemy w całości, żeby zmiana stałej na pole
 * wyboru nie zaskoczyła nikogo surowym JSON-em na ekranie.
 */
function extractErrorMessage(body: unknown): string | null {
  if (body && typeof body === 'object' && 'detail' in body) {
    const detail = (body as { detail: unknown }).detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      const messages = detail
        .map((item) =>
          item && typeof item === 'object' && 'msg' in item ? String((item as { msg: unknown }).msg) : null,
        )
        .filter((msg): msg is string => Boolean(msg))
      if (messages.length > 0) return messages.join(', ')
    }
  }
  return null
}

function MatchResults() {
  const [teams, setTeams] = useState<Team[]>([])
  const [status, setStatus] = useState<Status>('idle')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  // Zespoły pobieramy wyłącznie po kliknięciu, nie przy wejściu na stronę:
  // matchowanie ZMIENIA stan (kasuje poprzedni podział), więc nie może
  // odpalać się samo. To ta sama zasada, dla której backend używa POST.
  const runMatching = async () => {
    setStatus('loading')
    setErrorMessage(null)

    try {
      const response = await fetch(`${API_URL}/api/match?team_size=${TEAM_SIZE}`, {
        method: 'POST',
      })

      if (!response.ok) {
        const body: unknown = await response.json().catch(() => null)
        setStatus('error')
        setErrorMessage(
          extractErrorMessage(body) ?? `Nie udało się uruchomić matchowania (${response.status}).`,
        )
        return
      }

      const data: Team[] = await response.json()
      setTeams(data)
      setStatus('ready')
    } catch {
      setStatus('error')
      setErrorMessage(`Nie udało się połączyć z backendem (${API_URL}). Sprawdź, czy backend działa.`)
    }
  }

  return (
    <section style={{ maxWidth: '40rem', margin: '3rem auto 0', textAlign: 'left' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: '1rem' }}>
        <h2 style={{ fontSize: '1.1rem' }}>Zespoły</h2>
        <button type="button" onClick={() => void runMatching()} disabled={status === 'loading'}>
          {status === 'loading' ? 'Matchowanie...' : 'Uruchom matchowanie'}
        </button>
      </div>

      {status === 'idle' && (
        <p>Kliknij „Uruchom matchowanie", żeby podzielić zgłoszonych uczestników na zespoły.</p>
      )}

      {status === 'loading' && <p>Układanie zespołów...</p>}

      {status === 'error' && errorMessage && <p style={{ color: 'crimson' }}>{errorMessage}</p>}

      {status === 'ready' &&
        teams.map((team, index) => (
          <article key={team.id} style={{ border: '1px solid #ccc', borderRadius: '4px', padding: '.75rem 1rem', marginTop: '1rem' }}>
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
