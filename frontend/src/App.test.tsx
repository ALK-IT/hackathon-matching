import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import App from './App'

describe('App', () => {
  beforeEach(() => {
    // App montuje SubmissionList, ktora od razu pobiera dane. Bez zaslepki
    // test probowalby sie polaczyc z prawdziwym backendem.
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => [] }))
  })

  afterEach(() => {
    vi.restoreAllMocks()
    cleanup()
  })

  it('renderuje formularz i listę zgłoszeń', async () => {
    render(<App />)
    expect(screen.getByRole('button', { name: /wyślij zgłoszenie/i })).toBeInTheDocument()
    expect(await screen.findByText(/brak zgłoszeń/i)).toBeInTheDocument()
  })
})
