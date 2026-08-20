import { useState, type SubmitEvent } from 'react'

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

function SubmissionForm({ onSuccess }: Props) {
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [skills, setSkills] = useState('')
  const [status, setStatus] = useState<Status>('idle')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const handleSubmit = async (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault()

    if (!fullName.trim() || !email.trim() || !skills.trim()) {
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
        body: JSON.stringify({ full_name: fullName, email, skills }),
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
          style={{ display: 'block', width: '100%' }}
        />
      </label>
      <label>
        Email
        <input
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
          style={{ display: 'block', width: '100%' }}
        />
      </label>
      <label>
        Umiejętności
        <textarea
          value={skills}
          onChange={(event) => setSkills(event.target.value)}
          required
          style={{ display: 'block', width: '100%' }}
        />
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
