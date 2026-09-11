/** Jedyne miejsce, w którym frontend rozmawia z backendem (#94).
 *
 * Komponenty wołają funkcje operacji (`getSubmissions`, `createSubmission`,
 * `runMatching`) i nie znają adresów ani sposobu obsługi błędów. Każda porażka
 * - brak połączenia, odmowa backendu, odpowiedź bez sensu - kończy się
 * wyjątkiem `ApiError` z komunikatem gotowym do pokazania użytkownikowi.
 * Dzięki temu nowy komponent (np. dashboard z #80) nie powtarza tej logiki
 * po raz kolejny, a zmiana wspólna dla wszystkich żądań - jak token
 * organizatora z #54/#55 - trafia w jedno miejsce.
 */

import type { ExperienceLevel, PreferredRole } from './submissionProfile'

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

const CONNECTION_ERROR = `Nie udało się połączyć z backendem (${API_URL}). Sprawdź, czy backend działa.`
const UNEXPECTED_RESPONSE = 'Backend zwrócił nieoczekiwaną odpowiedź. Spróbuj ponownie.'

export type Submission = {
  id: number
  full_name: string
  email: string
  skills: string[]
  // null tylko dla zgłoszeń zapisanych przed dodaniem pól profilu - backend
  // wymaga ich przy każdym nowym zgłoszeniu.
  experience_level: ExperienceLevel | null
  preferred_role: PreferredRole | null
  availability: boolean
  created_at: string
}

export type Team = {
  id: number
  members: Submission[]
  created_at: string
}

/** Nowe zgłoszenie w postaci, której oczekuje `POST /api/submissions`. */
export type NewSubmission = {
  full_name: string
  email: string
  skills: string[]
  experience_level: ExperienceLevel
  preferred_role: PreferredRole
  availability: boolean
}

/** Porażka rozmowy z backendem, z komunikatem gotowym do pokazania w UI.
 *
 * `status` to kod HTTP, gdy backend w ogóle odpowiedział, a `null` przy braku
 * połączenia. Jeśli porażka ma pierwotną przyczynę - błąd sieci albo
 * nieczytelną treść odpowiedzi - zostaje ona w `cause`, żeby nie zginęła przy
 * diagnozie w konsoli.
 */
export class ApiError extends Error {
  readonly status: number | null

  constructor(message: string, status: number | null = null, options?: ErrorOptions) {
    super(message, options)
    this.name = 'ApiError'
    this.status = status
  }
}

/** Komunikat dla użytkownika z wyjątku złapanego w komponencie.
 *
 * `ApiError` niesie gotowy tekst. Wszystko inne to błąd w naszym kodzie, a nie
 * w rozmowie z backendem - użytkownik dostaje ogólny komunikat, a szczegóły
 * lądują w konsoli, żeby nie zginęły.
 */
export function toErrorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message
  console.error('Nieoczekiwany błąd:', error)
  return 'Coś poszło nie tak. Spróbuj ponownie.'
}

/** Wyciąga komunikat z odpowiedzi błędu backendu.
 *
 * FastAPI zwraca `detail` jako tekst (nasze 409) albo jako listę błędów
 * walidacji (422) - wtedy łączymy ich komunikaty, które backend tłumaczy
 * już na polski.
 */
function extractErrorMessage(body: unknown): string | null {
  if (body && typeof body === 'object' && 'detail' in body) {
    const detail = (body as { detail: unknown }).detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      const messages = detail
        .map((item) =>
          item && typeof item === 'object' && 'msg' in item ? String((item as { msg: unknown }).msg) : null,
        )
        .filter((msg): msg is string => Boolean(msg))
      if (messages.length > 0) return messages.join(', ')
    }
  }
  return null
}

/** Wysyła żądanie i zamienia każdą porażkę na `ApiError`.
 *
 * `failureMessage` to początek komunikatu na wypadek, gdy backend odmówi bez
 * czytelnego `detail`, np. "Nie udało się wysłać zgłoszenia" + kod statusu.
 * Z odpowiedzi czytamy wyłącznie `ok`, `status` i `json()` - na tym opierają
 * się atrapy `fetch` w testach komponentów.
 */
async function request(path: string, failureMessage: string, init?: RequestInit): Promise<Response> {
  let response: Response
  try {
    response = await fetch(`${API_URL}${path}`, init)
  } catch (cause) {
    throw new ApiError(CONNECTION_ERROR, null, { cause })
  }

  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null)
    throw new ApiError(extractErrorMessage(body) ?? `${failureMessage} (${response.status}).`, response.status)
  }
  return response
}

/** Czyta odpowiedź, która ma być listą, i sprawdza, że nią jest.
 *
 * `Promise<T[]>` to tylko obietnica dla TypeScriptu - bez tego sprawdzenia
 * obiekt zamiast listy wywracał render (`.map` na nie-tablicy) poza jakimkolwiek
 * try/catch (#66). Kształtu pojedynczych pozycji świadomie nie sprawdzamy:
 * nowa rola z backendu ma się wyświetlić surowo, a nie wywrócić cały widok.
 */
async function readList<T>(response: Response): Promise<T[]> {
  let data: unknown
  try {
    data = await response.json()
  } catch (cause) {
    // Przyczyna zostaje w `cause`: "Unexpected token '<'" od razu mówi, że
    // zamiast API odpowiedziała strona HTML (np. źle ustawiony VITE_API_URL).
    throw new ApiError(UNEXPECTED_RESPONSE, response.status, { cause })
  }
  if (!Array.isArray(data)) throw new ApiError(UNEXPECTED_RESPONSE, response.status)
  return data as T[]
}

export async function getSubmissions(): Promise<Submission[]> {
  return readList<Submission>(await request('/api/submissions', 'Nie udało się pobrać zgłoszeń'))
}

export async function createSubmission(submission: NewSubmission): Promise<void> {
  // Treść odpowiedzi (utworzone zgłoszenie) pomijamy: formularz po sukcesie
  // tylko się czyści, a lista po odświeżeniu pobiera dane sama.
  await request('/api/submissions', 'Nie udało się wysłać zgłoszenia', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(submission),
  })
}

export async function runMatching(teamSize: number): Promise<Team[]> {
  const response = await request(`/api/match?team_size=${teamSize}`, 'Nie udało się uruchomić matchowania', {
    method: 'POST',
  })
  return readList<Team>(response)
}
