/** Słowniki profilu uczestnika - wspólne dla formularza i listy zgłoszeń.
 *
 * Wartości muszą się zgadzać z enumami w `backend/app/enums.py`: backend
 * odrzuca wszystko spoza tego zbioru (422), a baza dodatkowo pilnuje go
 * ograniczeniem CHECK. Etykiety są tylko warstwą wyświetlania - do API
 * zawsze idzie wartość angielska.
 */

export const EXPERIENCE_LEVELS = ['beginner', 'intermediate', 'advanced'] as const
export const PREFERRED_ROLES = ['frontend', 'backend', 'fullstack', 'design', 'data', 'pm', 'other'] as const

export type ExperienceLevel = (typeof EXPERIENCE_LEVELS)[number]
export type PreferredRole = (typeof PREFERRED_ROLES)[number]

export const EXPERIENCE_LEVEL_LABELS: Record<ExperienceLevel, string> = {
  beginner: 'Początkujący',
  intermediate: 'Średniozaawansowany',
  advanced: 'Zaawansowany',
}

export const PREFERRED_ROLE_LABELS: Record<PreferredRole, string> = {
  frontend: 'Frontend',
  backend: 'Backend',
  fullstack: 'Fullstack',
  design: 'Design / UX',
  data: 'Dane / ML',
  pm: 'Project manager',
  other: 'Inna',
}

/** Rozbija listę umiejętności wpisaną po przecinkach na tablicę dla API.
 *
 * Puste fragmenty ("python,,react", "react, ") wypadają - backend odrzuciłby
 * pustą umiejętność błędem 422, a użytkownik nie ma pojęcia, że zostawił
 * wiszący przecinek.
 */
export function parseSkills(input: string): string[] {
  return input
    .split(',')
    .map((skill) => skill.trim())
    .filter((skill) => skill.length > 0)
}

/** Pokazuje wartość z backendu po polsku; `null` dotyczy zgłoszeń sprzed
 *  rozszerzenia modelu, które nie mają tych danych. */
export function labelFor<T extends string>(
  value: T | null | undefined,
  labels: Record<T, string>,
): string {
  if (!value) return '—'
  return labels[value] ?? value
}
