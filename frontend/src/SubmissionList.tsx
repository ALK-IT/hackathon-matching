import { useCallback, useEffect, useState } from 'react'
import {
  EXPERIENCE_LEVEL_LABELS,
  PREFERRED_ROLE_LABELS,
  labelFor,
  type ExperienceLevel,
  type PreferredRole,
} from './submissionProfile'

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export type Submission = {
  id: number
  full_name: string
  email: string
  skills: string[]
  // null tylko dla zgłoszeń zapisanych przed dodaniem pól profilu - backend
  // wymaga ich przy każdym nowym zgłoszeniu.
  experience_level: ExperienceLevel | null
  preferred_role: PreferredRole | null
  availability: boolean
  created_at: string
}

type Status = 'loading' | 'ready' | 'error'

type Props = {
  /** Zmiana tej wartości wymusza ponowne pobranie listy.
   *  Dzięki temu App może odświeżyć listę po wysłaniu formularza,
   *  bez sięgania do wnętrza tego komponentu. */
  reloadToken?: number
}

const headerStyle = { textAlign: 'left', borderBottom: '1px solid #ccc', padding: '.4rem .5rem .4rem 0' } as const
const cellStyle = { borderBottom: '1px solid #eee', padding: '.4rem .5rem .4rem 0', verticalAlign: 'top' } as const

const COLUMNS = ['Imię i nazwisko', 'Email', 'Umiejętności', 'Poziom', 'Rola', 'Pełna dostępność']

function SubmissionList({ reloadToken = 0 }: Props) {
  const [submissions, setSubmissions] = useState<Submission[]>([])
  const [status, setStatus] = useState<Status>('loading')

  const load = useCallback(async () => {
    setStatus('loading')
    try {
      const response = await fetch(`${API_URL}/api/submissions`)
      if (!response.ok) throw new Error(`Backend odpowiedział ${response.status}`)
      const data: Submission[] = await response.json()
      setSubmissions(data)
      setStatus('ready')
    } catch {
      setStatus('error')
    }
  }, [])

  // Pusta lista zależności w useCallback sprawia, że `load` jest zawsze tą samą
  // funkcją - bez tego efekt uznawałby ją za zmienioną przy każdym przerysowaniu
  // i wpadłby w nieskończoną pętlę zapytań.
  useEffect(() => {
    void load()
  }, [load, reloadToken])

  return (
    <section style={{ maxWidth: '56rem', margin: '3rem auto 0', textAlign: 'left' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: '1rem' }}>
        <h2 style={{ fontSize: '1.1rem' }}>Zgłoszeni uczestnicy</h2>
        <button type="button" onClick={() => void load()} disabled={status === 'loading'}>
          {status === 'loading' ? 'Odświeżanie...' : 'Odśwież'}
        </button>
      </div>

      {status === 'loading' && <p>Ładowanie zgłoszeń...</p>}

      {status === 'error' && (
        <p style={{ color: 'crimson' }}>
          Nie udało się pobrać zgłoszeń ({API_URL}). Sprawdź, czy backend działa.
        </p>
      )}

      {status === 'ready' && submissions.length === 0 && <p>Brak zgłoszeń</p>}

      {status === 'ready' && submissions.length > 0 && (
        // Tabela ma teraz sześć kolumn, więc na wąskim ekranie musi się dać
        // przewinąć w poziomie zamiast rozpychać całą stronę.
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {COLUMNS.map((column) => (
                  <th key={column} style={headerStyle}>
                    {column}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {submissions.map((submission) => (
                <tr key={submission.id}>
                  <td style={cellStyle}>{submission.full_name}</td>
                  <td style={cellStyle}>{submission.email}</td>
                  {/* Backend zwraca listę - łączymy ją dopiero przy wyświetlaniu. */}
                  <td style={cellStyle}>{submission.skills.join(', ')}</td>
                  <td style={cellStyle}>
                    {labelFor(submission.experience_level, EXPERIENCE_LEVEL_LABELS)}
                  </td>
                  <td style={cellStyle}>{labelFor(submission.preferred_role, PREFERRED_ROLE_LABELS)}</td>
                  <td style={cellStyle}>{submission.availability ? 'Tak' : 'Nie'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

export default SubmissionList
