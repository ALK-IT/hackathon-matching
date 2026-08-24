import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, fireEvent, cleanup } from '@testing-library/react'
import SubmissionForm from './SubmissionForm'

/** Wypełnia wszystkie pola poprawnymi danymi. Testy zmieniają potem tylko to,
 *  co faktycznie badają - dołożenie kolejnego pola do formularza wymaga wtedy
 *  poprawki w jednym miejscu. */
function fillForm() {
  fireEvent.change(screen.getByLabelText(/imię i nazwisko/i), { target: { value: 'Jan Kowalski' } })
  fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'jan@example.com' } })
  fireEvent.change(screen.getByLabelText(/umiejętności/i), { target: { value: 'React, python' } })
  fireEvent.change(screen.getByLabelText(/poziom doświadczenia/i), { target: { value: 'intermediate' } })
  fireEvent.change(screen.getByLabelText(/preferowana rola/i), { target: { value: 'backend' } })
}

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
    expect(screen.getByLabelText(/poziom doświadczenia/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/preferowana rola/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/dostępny/i)).toBeInTheDocument()
  })

  it('po wypełnieniu i wysłaniu formularza woła fetch i pokazuje sukces', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: 1 }),
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<SubmissionForm />)
    fillForm()
    fireEvent.click(screen.getByRole('button', { name: /wyślij zgłoszenie/i }))

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    const [url, options] = fetchMock.mock.calls[0]
    expect(String(url)).toContain('/api/submissions')
    expect(options.method).toBe('POST')
    expect(JSON.parse(options.body)).toEqual({
      full_name: 'Jan Kowalski',
      email: 'jan@example.com',
      // Umiejętności idą do API jako lista, nie jako tekst po przecinkach.
      // Backend nie przyjmie stringa, a wielkość liter normalizuje już on sam.
      skills: ['React', 'python'],
      experience_level: 'intermediate',
      preferred_role: 'backend',
      availability: true,
    })

    expect(await screen.findByText(/zgłoszenie wysłane/i)).toBeInTheDocument()
  })

  it('odznaczony checkbox wysyła availability jako false', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ id: 1 }) })
    vi.stubGlobal('fetch', fetchMock)

    render(<SubmissionForm />)
    fillForm()
    fireEvent.click(screen.getByLabelText(/dostępny/i))
    fireEvent.click(screen.getByRole('button', { name: /wyślij zgłoszenie/i }))

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    expect(JSON.parse(fetchMock.mock.calls[0][1].body).availability).toBe(false)
  })

  it('nie wysyła zgłoszenia bez wybranego poziomu i roli', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    const { container } = render(<SubmissionForm />)
    fireEvent.change(screen.getByLabelText(/imię i nazwisko/i), { target: { value: 'Jan Kowalski' } })
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'jan@example.com' } })
    fireEvent.change(screen.getByLabelText(/umiejętności/i), { target: { value: 'python' } })

    // fireEvent.submit zamiast kliknięcia: omija walidację HTML5 przeglądarki
    // i sprawdza naszą własną, która jest jedynym zabezpieczeniem np. przy
    // wysłaniu formularza z konsoli.
    fireEvent.submit(container.querySelector('form')!)

    expect(await screen.findByText(/wypełnij wszystkie pola/i)).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('nie wysyła zgłoszenia, gdy w umiejętnościach są same przecinki', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    const { container } = render(<SubmissionForm />)
    fillForm()
    fireEvent.change(screen.getByLabelText(/umiejętności/i), { target: { value: ' , , ' } })
    fireEvent.submit(container.querySelector('form')!)

    expect(await screen.findByText(/wypełnij wszystkie pola/i)).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('pokazuje komunikat błędu z backendu (np. duplikat email)', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 409,
      json: async () => ({ detail: 'Zgłoszenie z tym adresem e-mail już istnieje.' }),
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<SubmissionForm />)
    fillForm()
    fireEvent.click(screen.getByRole('button', { name: /wyślij zgłoszenie/i }))

    expect(await screen.findByText(/już istnieje/i)).toBeInTheDocument()
  })
})
