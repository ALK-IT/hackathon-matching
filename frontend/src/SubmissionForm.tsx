import { useState, type SubmitEvent } from 'react'
import {
  EXPERIENCE_LEVELS,
  EXPERIENCE_LEVEL_LABELS,
  PREFERRED_ROLES,
  PREFERRED_ROLE_LABELS,
  parseSkills,
  type ExperienceLevel,
  type PreferredRole,
} from './submissionProfile'

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

type Status = 'idle' | 'submitting' | 'success' | 'error'

function extractErrorMessage(body: unknown): string | null {
  if (body && typeof body === 'object' && 'detail' in body) {
    const detail = (body as { detail: unknown }).detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      const messages = detail
        .map((item) => (item && typeof item === 'object' && 'msg' in item ? String((item as { msg: unknown }).msg) : null))
        .filter((msg): msg is string => Boolean(msg))
      if (messages.length > 0) return messages.join(', ')
    }
  }
  return null
}

type Props = {
  /** Wywoływane po udanym zapisie - App używa tego, żeby odświeżyć listę. */
  onSuccess?: () => void
}

const fieldStyle = { display: 'block', width: '100%' }

function SubmissionForm({ onSuccess }: Props) {
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [skills, setSkills] = useState('')
  // Poziom i rola startują puste, a nie od pierwszej opcji z listy: gdyby
  // domyślnie stało "Początkujący", zgłoszenia osób, które nie zauważyły tego
  // pola, wyglądałyby dla algorytmu jak świadoma deklaracja.
  const [experienceLevel, setExperienceLevel] = useState<ExperienceLevel | ''>('')
  const [preferredRole, setPreferredRole] = useState<PreferredRole | ''>('')
  const [availability, setAvailability] = useState(true)
  const [status, setStatus] = useState<Status>('idle')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const handleSubmit = async (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault()

    // Umiejętności sprawdzamy po rozbiciu, nie na surowym tekście: samo ","
    // ma niezerową długość, ale nie daje ani jednej umiejętności.
    const skillList = parseSkills(skills)

    if (!fullName.trim() || !email.trim() || skillList.length === 0 || !experienceLevel || !preferredRole) {
      setStatus('error')
      setErrorMessage('Wypełnij wszystkie pola.')
      return
    }

    setStatus('submitting')
    setErrorMessage(null)

    try {
      const response = await fetch(`${API_URL}/api/submissions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          full_name: fullName,
          email,
          skills: skillList,
          experience_level: experienceLevel,
          preferred_role: preferredRole,
          availability,
        }),
      })

      if (!response.ok) {
        const body: unknown = await response.json().catch(() => null)
        setStatus('error')
        setErrorMessage(extractErrorMessage(body) ?? `Nie udało się wysłać zgłoszenia (${response.status}).`)
        return
      }

      setStatus('success')
      setFullName('')
      setEmail('')
      setSkills('')
      setExperienceLevel('')
      setPreferredRole('')
      setAvailability(true)
      onSuccess?.()
    } catch {
      setStatus('error')
      setErrorMessage(`Nie udało się połączyć z backendem (${API_URL}). Sprawdź, czy backend działa.`)
    }
  }

  return (
    <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem', maxWidth: '24rem', margin: '0 auto', textAlign: 'left' }}>
      <label>
        Imię i nazwisko
        <input
          type="text"
          value={fullName}
          onChange={(event) => setFullName(event.target.value)}
          required
          style={fieldStyle}
        />
      </label>
      <label>
        Email
        <input
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
          style={fieldStyle}
        />
      </label>
      <label>
        Umiejętności (oddziel przecinkami)
        <textarea
          value={skills}
          onChange={(event) => setSkills(event.target.value)}
          placeholder="python, react, figma"
          required
          style={fieldStyle}
        />
      </label>
      <label>
        Poziom doświadczenia
        <select
          value={experienceLevel}
          onChange={(event) => setExperienceLevel(event.target.value as ExperienceLevel)}
          required
          style={fieldStyle}
        >
          <option value="">Wybierz...</option>
          {EXPERIENCE_LEVELS.map((level) => (
            <option key={level} value={level}>
              {EXPERIENCE_LEVEL_LABELS[level]}
            </option>
          ))}
        </select>
      </label>
      <label>
        Preferowana rola
        <select
          value={preferredRole}
          onChange={(event) => setPreferredRole(event.target.value as PreferredRole)}
          required
          style={fieldStyle}
        >
          <option value="">Wybierz...</option>
          {PREFERRED_ROLES.map((role) => (
            <option key={role} value={role}>
              {PREFERRED_ROLE_LABELS[role]}
            </option>
          ))}
        </select>
      </label>
      <label style={{ display: 'flex', alignItems: 'center', gap: '.5rem' }}>
        <input
          type="checkbox"
          checked={availability}
          onChange={(event) => setAvailability(event.target.checked)}
        />
        Jestem dostępny/a przez cały czas trwania hackathonu
      </label>
      <button type="submit" disabled={status === 'submitting'}>
        {status === 'submitting' ? 'Wysyłanie...' : 'Wyślij zgłoszenie'}
      </button>
      {status === 'success' && <p style={{ color: 'green' }}>Zgłoszenie wysłane</p>}
      {status === 'error' && errorMessage && <p style={{ color: 'crimson' }}>{errorMessage}</p>}
    </form>
  )
}

export default SubmissionForm
