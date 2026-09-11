import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { ApiError, createSubmission, getSubmissions, runMatching, toErrorMessage, type NewSubmission } from './api'

/** Atrapa odpowiedzi z tym, na czym opiera się warstwa API: `ok`, `status`, `json()`. */
function respond(status: number, body?: unknown, { invalidJson = false } = {}) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => {
      if (invalidJson) throw new SyntaxError('Unexpected token < in JSON')
      return body
    },
  }
}

function stubFetch(response: unknown) {
  const fetchMock = vi.fn().mockResolvedValue(response)
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

const newSubmission: NewSubmission = {
  full_name: 'Jan Kowalski',
  email: 'jan@example.com',
  skills: ['python'],
  experience_level: 'beginner',
  preferred_role: 'backend',
  availability: true,
}

describe('api', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  describe('getSubmissions', () => {
    it('zwraca listę zgłoszeń z GET /api/submissions', async () => {
      const submissions = [{ id: 1, full_name: 'Jan Kowalski' }]
      const fetchMock = stubFetch(respond(200, submissions))

      await expect(getSubmissions()).resolves.toEqual(submissions)
      expect(String(fetchMock.mock.calls[0][0])).toMatch(/\/api\/submissions$/)
    })

    it('obiekt zamiast listy to ApiError, a nie dane, które wywrócą render (#66)', async () => {
      stubFetch(respond(200, { detail: 'niespodzianka' }))

      await expect(getSubmissions()).rejects.toThrow(/nieoczekiwaną odpowiedź/)
    })

    it('niepoprawny JSON przy sukcesie to też nieoczekiwana odpowiedź, z błędem parsowania w `cause`', async () => {
      stubFetch(respond(200, undefined, { invalidJson: true }))

      const error = await getSubmissions().catch((caught: unknown) => caught)

      expect(error).toBeInstanceOf(ApiError)
      expect((error as ApiError).message).toMatch(/nieoczekiwaną odpowiedź/)
      expect((error as ApiError).status).toBe(200)
      // Bez tego w konsoli zostałoby samo "nieoczekiwana odpowiedź" - a to
      // "Unexpected token '<'" zdradza, że odpowiedziała strona HTML, nie API.
      expect((error as ApiError).cause).toBeInstanceOf(SyntaxError)
    })
  })

  describe('obsługa błędów wspólna dla wszystkich operacji', () => {
    it('brak połączenia daje ApiError bez statusu, z pierwotną przyczyną w `cause`', async () => {
      const networkError = new TypeError('Failed to fetch')
      vi.stubGlobal('fetch', vi.fn().mockRejectedValue(networkError))

      const error = await getSubmissions().catch((caught: unknown) => caught)

      expect(error).toBeInstanceOf(ApiError)
      expect((error as ApiError).message).toMatch(/nie udało się połączyć z backendem/i)
      expect((error as ApiError).status).toBeNull()
      expect((error as ApiError).cause).toBe(networkError)
    })

    it('`detail` jako tekst (409) trafia do komunikatu bez zmian, razem ze statusem', async () => {
      stubFetch(respond(409, { detail: 'Zgłoszenie z tym adresem e-mail już istnieje.' }))

      const error = await createSubmission(newSubmission).catch((caught: unknown) => caught)

      expect(error).toBeInstanceOf(ApiError)
      expect((error as ApiError).message).toBe('Zgłoszenie z tym adresem e-mail już istnieje.')
      expect((error as ApiError).status).toBe(409)
    })

    it('`detail` jako lista błędów walidacji (422) łączy ich komunikaty', async () => {
      stubFetch(
        respond(422, {
          detail: [
            { loc: ['body', 'email'], msg: 'Podaj poprawny adres e-mail.', type: 'value_error' },
            { loc: ['body', 'skills'], msg: 'Podaj co najmniej jedną umiejętność.', type: 'too_short' },
          ],
        }),
      )

      await expect(createSubmission(newSubmission)).rejects.toThrow(
        'Podaj poprawny adres e-mail., Podaj co najmniej jedną umiejętność.',
      )
    })

    it('odmowa bez czytelnego `detail` daje komunikat operacji z kodem statusu', async () => {
      stubFetch(respond(500, undefined, { invalidJson: true }))

      await expect(runMatching(3)).rejects.toThrow('Nie udało się uruchomić matchowania (500).')
    })
  })

  describe('createSubmission', () => {
    it('wysyła POST z danymi jako JSON', async () => {
      const fetchMock = stubFetch(respond(201, { id: 1 }))

      await createSubmission(newSubmission)

      const [url, options] = fetchMock.mock.calls[0]
      expect(String(url)).toMatch(/\/api\/submissions$/)
      expect(options.method).toBe('POST')
      expect(options.headers).toEqual({ 'Content-Type': 'application/json' })
      expect(JSON.parse(options.body)).toEqual(newSubmission)
    })

    it('przy sukcesie nie czyta treści odpowiedzi - formularz jej nie potrzebuje', async () => {
      stubFetch(respond(201, undefined, { invalidJson: true }))

      await expect(createSubmission(newSubmission)).resolves.toBeUndefined()
    })
  })

  describe('runMatching', () => {
    it('wysyła POST z rozmiarem zespołu i zwraca zespoły', async () => {
      const teams = [{ id: 1, members: [], created_at: '2026-09-11T10:00:00Z' }]
      const fetchMock = stubFetch(respond(201, teams))

      await expect(runMatching(4)).resolves.toEqual(teams)
      const [url, options] = fetchMock.mock.calls[0]
      expect(String(url)).toMatch(/\/api\/match\?team_size=4$/)
      expect(options.method).toBe('POST')
    })

    it('obiekt zamiast listy zespołów to ApiError', async () => {
      stubFetch(respond(201, { detail: 'x' }))

      await expect(runMatching(3)).rejects.toThrow(/nieoczekiwaną odpowiedź/)
    })
  })

  describe('toErrorMessage', () => {
    it('z ApiError bierze gotowy komunikat', () => {
      expect(toErrorMessage(new ApiError('Konkretny powód.', 409))).toBe('Konkretny powód.')
    })

    it('inny wyjątek to błąd w naszym kodzie: ogólny komunikat, szczegóły w konsoli', () => {
      const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
      const bug = new TypeError("Cannot read properties of undefined (reading 'map')")

      expect(toErrorMessage(bug)).toBe('Coś poszło nie tak. Spróbuj ponownie.')
      expect(consoleError).toHaveBeenCalledWith('Nieoczekiwany błąd:', bug)
    })
  })
})
