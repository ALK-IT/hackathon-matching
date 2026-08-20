import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, fireEvent, cleanup } from '@testing-library/react'
import SubmissionForm from './SubmissionForm'

describe('SubmissionForm', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  afterEach(() => {
    cleanup()
  })

  it('renderuje pola formularza', () => {
    render(<SubmissionForm />)
    expect(screen.getByLabelText(/imię i nazwisko/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/umiejętności/i)).toBeInTheDocument()
  })

  it('po wypełnieniu i wysłaniu formularza woła fetch i pokazuje sukces', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: 1, full_name: 'Jan Kowalski', email: 'jan@example.com', skills: 'React' }),
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<SubmissionForm />)

    fireEvent.change(screen.getByLabelText(/imię i nazwisko/i), { target: { value: 'Jan Kowalski' } })
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'jan@example.com' } })
    fireEvent.change(screen.getByLabelText(/umiejętności/i), { target: { value: 'React' } })
    fireEvent.click(screen.getByRole('button', { name: /wyślij zgłoszenie/i }))

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    const [url, options] = fetchMock.mock.calls[0]
    expect(String(url)).toContain('/api/submissions')
    expect(options.method).toBe('POST')
    expect(JSON.parse(options.body)).toEqual({
      full_name: 'Jan Kowalski',
      email: 'jan@example.com',
      skills: 'React',
    })

    expect(await screen.findByText(/zgłoszenie wysłane/i)).toBeInTheDocument()
  })

  it('pokazuje komunikat błędu z backendu (np. duplikat email)', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 409,
      json: async () => ({ detail: 'Zgłoszenie z tym adresem e-mail już istnieje.' }),
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<SubmissionForm />)

    fireEvent.change(screen.getByLabelText(/imię i nazwisko/i), { target: { value: 'Jan Kowalski' } })
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'jan@example.com' } })
    fireEvent.change(screen.getByLabelText(/umiejętności/i), { target: { value: 'React' } })
    fireEvent.click(screen.getByRole('button', { name: /wyślij zgłoszenie/i }))

    expect(await screen.findByText(/już istnieje/i)).toBeInTheDocument()
  })
})
