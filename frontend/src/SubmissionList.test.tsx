import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, fireEvent, cleanup } from '@testing-library/react'
import SubmissionList from './SubmissionList'

const submissions = [
  {
    id: 1,
    full_name: 'Jan Kowalski',
    email: 'jan@example.com',
    skills: ['python', 'fastapi'],
    experience_level: 'advanced',
    preferred_role: 'backend',
    availability: true,
    created_at: '2026-08-20T10:00:00Z',
  },
  {
    id: 2,
    full_name: 'Anna Nowak',
    email: 'anna@example.com',
    skills: ['react'],
    experience_level: 'beginner',
    preferred_role: 'frontend',
    availability: false,
    created_at: '2026-08-20T11:00:00Z',
  },
]

function mockFetch(value: unknown, ok = true) {
  const fetchMock = vi.fn().mockResolvedValue({ ok, status: ok ? 200 : 500, json: async () => value })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

describe('SubmissionList', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  afterEach(() => {
    cleanup()
  })

  it('pobiera zgłoszenia i pokazuje je w tabeli', async () => {
    const fetchMock = mockFetch(submissions)

    render(<SubmissionList />)

    expect(await screen.findByText('Jan Kowalski')).toBeInTheDocument()
    expect(screen.getByText('anna@example.com')).toBeInTheDocument()
    // Lista umiejętności jest łączona dopiero przy wyświetlaniu.
    expect(screen.getByText('python, fastapi')).toBeInTheDocument()

    const [url] = fetchMock.mock.calls[0]
    expect(String(url)).toContain('/api/submissions')
  })

  it('pokazuje profil uczestnika po polsku, a nie surowe wartości z API', async () => {
    mockFetch(submissions)

    render(<SubmissionList />)

    expect(await screen.findByText('Zaawansowany')).toBeInTheDocument()
    expect(screen.getByText('Początkujący')).toBeInTheDocument()
    expect(screen.getByText('Backend')).toBeInTheDocument()
    expect(screen.queryByText('advanced')).not.toBeInTheDocument()
  })

  it('pokazuje dostępność jako Tak/Nie', async () => {
    mockFetch(submissions)

    render(<SubmissionList />)

    expect(await screen.findByText('Tak')).toBeInTheDocument()
    expect(screen.getByText('Nie')).toBeInTheDocument()
  })

  it('zgłoszenie bez profilu (sprzed rozszerzenia modelu) nie wywraca listy', async () => {
    mockFetch([
      {
        id: 3,
        full_name: 'Stare Zgłoszenie',
        email: 'stare@example.com',
        skills: ['python'],
        experience_level: null,
        preferred_role: null,
        availability: true,
        created_at: '2026-08-01T10:00:00Z',
      },
    ])

    render(<SubmissionList />)

    expect(await screen.findByText('Stare Zgłoszenie')).toBeInTheDocument()
    // Dwie kolumny bez danych - poziom i rola.
    expect(screen.getAllByText('—')).toHaveLength(2)
  })

  it('przy pustej bazie pokazuje komunikat, a nie pustą tabelę', async () => {
    mockFetch([])

    render(<SubmissionList />)

    expect(await screen.findByText(/brak zgłoszeń/i)).toBeInTheDocument()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })

  it('gdy backend nie odpowiada, pokazuje błąd zamiast pustego ekranu', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('brak połączenia')))

    render(<SubmissionList />)

    expect(await screen.findByText(/nie udało się pobrać zgłoszeń/i)).toBeInTheDocument()
  })

  it('przycisk Odśwież pobiera dane ponownie', async () => {
    const fetchMock = mockFetch(submissions)

    render(<SubmissionList />)
    await screen.findByText('Jan Kowalski')
    expect(fetchMock).toHaveBeenCalledTimes(1)

    fireEvent.click(screen.getByRole('button', { name: /odśwież/i }))

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
  })

  it('zmiana reloadToken wymusza ponowne pobranie', async () => {
    const fetchMock = mockFetch(submissions)

    const { rerender } = render(<SubmissionList reloadToken={0} />)
    await screen.findByText('Jan Kowalski')
    expect(fetchMock).toHaveBeenCalledTimes(1)

    rerender(<SubmissionList reloadToken={1} />)

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
  })
})
