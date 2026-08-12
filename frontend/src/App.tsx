import { useCallback, useEffect, useState } from 'react'
import './App.css'

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

function App() {
  const [message, setMessage] = useState<string>('Ładowanie...')
  const [error, setError] = useState<string | null>(null)

  const fetchHello = useCallback(() => {
    setError(null)
    setMessage('Ładowanie...')
    fetch(`${API_URL}/api/hello`)
      .then((res) => {
        if (!res.ok) throw new Error(`Backend odpowiedział ${res.status}`)
        return res.json()
      })
      .then((data) => setMessage(data.message))
      .catch(() => setError(`Nie udało się połączyć z backendem (${API_URL}). Sprawdź, czy backend działa.`))
  }, [])

  useEffect(() => {
    fetchHello()
  }, [fetchHello])

  return (
    <main style={{ fontFamily: 'sans-serif', textAlign: 'center', marginTop: '4rem' }}>
      <h1>hackathon-matching</h1>
      <p>Frontend (React + Vite) połączony z backendem (FastAPI):</p>
      {error ? <p style={{ color: 'crimson' }}>{error}</p> : <p>{message}</p>}
      <button onClick={fetchHello}>Odśwież</button>
    </main>
  )
}

export default App
