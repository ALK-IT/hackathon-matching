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

    // Po #65 komunikat wskazuje konkretne pola, a nie zbiorcze "wypełnij wszystko".
    expect(await screen.findByText('Wybierz poziom doświadczenia.')).toBeInTheDocument()
    expect(screen.getByText('Wybierz preferowaną rolę.')).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('nie wysyła zgłoszenia, gdy w umiejętnościach są same przecinki', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    const { container } = render(<SubmissionForm />)
    fillForm()
    fireEvent.change(screen.getByLabelText(/umiejętności/i), { target: { value: ' , , ' } })
    fireEvent.submit(container.querySelector('form')!)

    // Sedno #65: pole WYGLĄDA na wypełnione, więc ogólne "wypełnij wszystkie
    // pola" czytało się jak awaria aplikacji. Komunikat musi tłumaczyć powód.
    expect(await screen.findByText(/same przecinki to za mało/i)).toBeInTheDocument()
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

  it('błąd walidacji 422 (detail jako tablica pydantic) pokazuje komunikaty (#67)', async () => {
    // Prawdziwy kształt 422 z FastAPI: detail to lista obiektów z msg.
    // Dotąd testowany był wyłącznie detail-string (409), więc ta gałąź
    // extractErrorMessage była martwa dla CI.
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      json: async () => ({
        detail: [
          { loc: ['body', 'email'], msg: 'Podaj poprawny adres e-mail.', type: 'value_error' },
          { loc: ['body', 'skills'], msg: 'Podaj co najmniej jedną umiejętność.', type: 'too_short' },
        ],
      }),
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<SubmissionForm />)
    fillForm()
    fireEvent.click(screen.getByRole('button', { name: /wyślij zgłoszenie/i }))

    expect(await screen.findByText(/Podaj poprawny adres e-mail\./)).toBeInTheDocument()
    expect(screen.getByText(/Podaj co najmniej jedną umiejętność\./)).toBeInTheDocument()
  })
  // --- testy z issues #63 (limity), #64 (a11y) i #65 (konkretne komunikaty) ---

  it('wskazuje każde brakujące pole osobno zamiast jednego komunikatu (#65)', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    const { container } = render(<SubmissionForm />)
    fireEvent.submit(container.querySelector('form')!)

    expect(await screen.findByText('Podaj imię i nazwisko.')).toBeInTheDocument()
    expect(screen.getByText('Podaj adres e-mail.')).toBeInTheDocument()
    expect(screen.getByText('Podaj co najmniej jedną umiejętność.')).toBeInTheDocument()
    expect(screen.getByText('Wybierz poziom doświadczenia.')).toBeInTheDocument()
    expect(screen.getByText('Wybierz preferowaną rolę.')).toBeInTheDocument()
    expect(screen.queryByText(/wypełnij wszystkie pola/i)).not.toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('pola tekstowe mają maxLength zgodny z limitami backendu (#63)', () => {
    render(<SubmissionForm />)

    expect(screen.getByLabelText(/imię i nazwisko/i)).toHaveAttribute('maxlength', '200')
    expect(screen.getByLabelText(/email/i)).toHaveAttribute('maxlength', '320')
  })

  it('licznik pokazuje liczbę wpisanych umiejętności na bieżąco (#63)', () => {
    render(<SubmissionForm />)

    expect(screen.getByText(/0 z 20 umiejętności/i)).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText(/umiejętności/i), {
      target: { value: 'python, react, sql' },
    })

    expect(screen.getByText(/3 z 20 umiejętności/i)).toBeInTheDocument()
  })

  it('odrzuca listę dłuższą niż 20 umiejętności przed wysłaniem (#63)', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    const { container } = render(<SubmissionForm />)
    fillForm()
    fireEvent.change(screen.getByLabelText(/umiejętności/i), {
      target: { value: Array.from({ length: 21 }, (_, i) => `skill${i}`).join(', ') },
    })
    fireEvent.submit(container.querySelector('form')!)

    expect(await screen.findByText(/najwyżej 20 umiejętności \(masz 21\)/i)).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('odrzuca umiejętność dłuższą niż 50 znaków przed wysłaniem (#63)', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    const { container } = render(<SubmissionForm />)
    fillForm()
    fireEvent.change(screen.getByLabelText(/umiejętności/i), {
      target: { value: `python, ${'x'.repeat(51)}` },
    })
    fireEvent.submit(container.querySelector('form')!)

    expect(await screen.findByText(/najwyżej 50 znaków/i)).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('błędne pole dostaje aria-invalid i wskazuje swój komunikat (#64)', async () => {
    vi.stubGlobal('fetch', vi.fn())

    const { container } = render(<SubmissionForm />)
    fireEvent.submit(container.querySelector('form')!)

    const field = await screen.findByLabelText(/imię i nazwisko/i)
    expect(field).toHaveAttribute('aria-invalid', 'true')

    // Powiązanie musi wskazywać na element, który naprawdę istnieje i niesie
    // komunikat - samo aria-describedby z martwym id nic nie daje.
    const describedBy = field.getAttribute('aria-describedby')!
    expect(document.getElementById(describedBy)).toHaveTextContent('Podaj imię i nazwisko.')
  })

  it('fokus przechodzi na pierwsze błędne pole w kolejności formularza (#64)', async () => {
    vi.stubGlobal('fetch', vi.fn())

    const { container } = render(<SubmissionForm />)
    fireEvent.submit(container.querySelector('form')!)

    await waitFor(() =>
      expect(document.activeElement).toBe(screen.getByLabelText(/imię i nazwisko/i)),
    )

    // Po uzupełnieniu pierwszego pola fokus ma iść na kolejne błędne, a nie
    // wracać na początek formularza.
    fireEvent.change(screen.getByLabelText(/imię i nazwisko/i), {
      target: { value: 'Jan Kowalski' },
    })
    fireEvent.submit(container.querySelector('form')!)

    await waitFor(() => expect(document.activeElement).toBe(screen.getByLabelText(/email/i)))
  })

  it('komunikat błędu z backendu jest ogłaszany jako alert (#64)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 409,
        json: async () => ({ detail: 'Zgłoszenie z tym adresem e-mail już istnieje.' }),
      }),
    )

    render(<SubmissionForm />)
    fillForm()
    fireEvent.click(screen.getByRole('button', { name: /wyślij zgłoszenie/i }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(/już istnieje/i)
  })

  it('komunikat sukcesu jest ogłaszany jako status (#64)', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, status: 201, json: async () => ({}) }))

    render(<SubmissionForm />)
    fillForm()
    fireEvent.click(screen.getByRole('button', { name: /wyślij zgłoszenie/i }))

    const status = await screen.findByRole('status')
    expect(status).toHaveTextContent('Zgłoszenie wysłane')
  })
})
