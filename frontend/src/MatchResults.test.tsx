import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, fireEvent, cleanup } from '@testing-library/react'
import MatchResults from './MatchResults'

const teams = [
  {
    id: 1,
    created_at: '2026-08-27T10:00:00Z',
    members: [
      {
        id: 1,
        full_name: 'Jan Kowalski',
        email: 'jan@example.com',
        skills: ['python'],
        experience_level: 'advanced',
        preferred_role: 'backend',
        availability: true,
        created_at: '2026-08-27T09:00:00Z',
      },
      {
        id: 2,
        full_name: 'Anna Nowak',
        email: 'anna@example.com',
        skills: ['react'],
        experience_level: 'beginner',
        preferred_role: 'frontend',
        availability: true,
        created_at: '2026-08-27T09:01:00Z',
      },
    ],
  },
  {
    id: 2,
    created_at: '2026-08-27T10:00:00Z',
    members: [
      {
        id: 3,
        full_name: 'Piotr Wiśniewski',
        email: 'piotr@example.com',
        skills: ['figma'],
        // null jak w zgłoszeniach sprzed rozszerzenia modelu - widok musi
        // pokazać kreskę, a nie się wywrócić.
        experience_level: null,
        preferred_role: null,
        availability: true,
        created_at: '2026-08-27T09:02:00Z',
      },
    ],
  },
]

describe('MatchResults', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  afterEach(() => {
    cleanup()
  })

  it('przed kliknięciem pokazuje zachętę, nie zespoły', () => {
    render(<MatchResults />)

    expect(screen.getByRole('button', { name: /uruchom matchowanie/i })).toBeInTheDocument()
    expect(screen.getByText(/kliknij/i)).toBeInTheDocument()
    expect(screen.queryByText(/zespół 1/i)).not.toBeInTheDocument()
  })

  it('po kliknięciu woła POST /api/match i pokazuje zespoły ze składami', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 201, json: async () => teams })
    vi.stubGlobal('fetch', fetchMock)

    render(<MatchResults />)
    fireEvent.click(screen.getByRole('button', { name: /uruchom matchowanie/i }))

    expect(await screen.findByText(/zespół 1/i)).toBeInTheDocument()

    const [url, options] = fetchMock.mock.calls[0]
    expect(String(url)).toContain('/api/match?team_size=')
    expect(options.method).toBe('POST')

    // Kryterium z issue: każdy uczestnik widoczny dokładnie raz.
    for (const name of ['Jan Kowalski', 'Anna Nowak', 'Piotr Wiśniewski']) {
      expect(screen.getAllByText(new RegExp(name))).toHaveLength(1)
    }

    // Rola i poziom po polsku, null jako kreska.
    expect(screen.getByText(/Backend, Zaawansowany/)).toBeInTheDocument()
    expect(screen.getByText(/Frontend, Początkujący/)).toBeInTheDocument()
    expect(screen.getByText(/—, —/)).toBeInTheDocument()
  })

  it('pusta baza (409) pokazuje komunikat z backendu, nie surowy błąd', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 409,
      json: async () => ({ detail: 'Brak zgłoszeń do zmatchowania - najpierw dodaj uczestników.' }),
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<MatchResults />)
    fireEvent.click(screen.getByRole('button', { name: /uruchom matchowanie/i }))

    expect(await screen.findByText(/brak zgłoszeń do zmatchowania/i)).toBeInTheDocument()
  })

  it('brak połączenia z backendem pokazuje komunikat, nie pusty ekran', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('brak połączenia')))

    render(<MatchResults />)
    fireEvent.click(screen.getByRole('button', { name: /uruchom matchowanie/i }))

    expect(await screen.findByText(/nie udało się połączyć z backendem/i)).toBeInTheDocument()
  })

  it('przycisk jest zablokowany na czas matchowania', async () => {
    let resolveFetch: (value: unknown) => void = () => {}
    vi.stubGlobal(
      'fetch',
      vi.fn().mockReturnValue(new Promise((resolve) => (resolveFetch = resolve))),
    )

    render(<MatchResults />)
    const button = screen.getByRole('button', { name: /uruchom matchowanie/i })
    fireEvent.click(button)

    await waitFor(() => expect(button).toBeDisabled())

    resolveFetch({ ok: true, status: 201, json: async () => [] })
    await waitFor(() => expect(button).not.toBeDisabled())
  })
})
