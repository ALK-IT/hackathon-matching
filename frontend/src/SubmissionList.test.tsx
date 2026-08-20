import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, fireEvent, cleanup } from '@testing-library/react'
import SubmissionList from './SubmissionList'

const submissions = [
  { id: 1, full_name: 'Jan Kowalski', email: 'jan@example.com', skills: 'python', created_at: '2026-08-20T10:00:00Z' },
  { id: 2, full_name: 'Anna Nowak', email: 'anna@example.com', skills: 'react', created_at: '2026-08-20T11:00:00Z' },
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
    expect(screen.getByText('react')).toBeInTheDocument()

    const [url] = fetchMock.mock.calls[0]
    expect(String(url)).toContain('/api/submissions')
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
