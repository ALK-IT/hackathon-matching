/** Reguły walidacji formularza zgłoszenia - po stronie klienta.
 *
 * Wydzielone z `SubmissionForm.tsx` (#117). Funkcja jest czysta: dostaje
 * wartości pól, zwraca komunikaty. Nie zna Reacta, nie dotyka DOM-u i nie ma
 * stanu, więc nic nie trzymało jej w pliku komponentu poza historią.
 *
 * Osobny moduł, a nie dopisek do `submissionProfile.ts`: tamten plik jest
 * wspólny dla formularza i listy zgłoszeń (słowniki ról, poziomów, `labelFor`),
 * a te reguły dotyczą wyłącznie formularza - lista nie ma czego walidować.
 *
 * Backend waliduje to samo jeszcze raz i to on jest ostateczną instancją
 * (`app/schemas.py`). Ta warstwa istnieje po to, żeby uczestnik dowiedział się
 * o błędzie przed wysłaniem, a nie z odpowiedzi 422.
 */

import { SUBMISSION_LIMITS, type ExperienceLevel, type PreferredRole } from './submissionProfile'

export type FieldName = 'fullName' | 'email' | 'skills' | 'experienceLevel' | 'preferredRole'

export type FieldErrors = Partial<Record<FieldName, string>>

/** Kolejność pól w formularzu.
 *
 * Potrzebna, bo po nieudanej walidacji ustawiamy fokus na PIERWSZYM błędnym
 * polu, a `Object.keys` na obiekcie błędów dałoby kolejność przypadkową -
 * użytkownik czytnika ekranu wylądowałby w środku formularza. */
export const FIELD_ORDER: readonly FieldName[] = [
  'fullName',
  'email',
  'skills',
  'experienceLevel',
  'preferredRole',
]

export type FormValues = {
  fullName: string
  email: string
  rawSkills: string
  skillList: string[]
  experienceLevel: ExperienceLevel | ''
  preferredRole: PreferredRole | ''
}

/** Sprawdza formularz i zwraca komunikat osobno dla każdego błędnego pola.
 *
 * Wcześniej wszystkie te przypadki dawały jeden komunikat "Wypełnij wszystkie
 * pola" (#65). Najgorzej wypadał przy samych przecinkach w umiejętnościach:
 * pole wyglądało na wypełnione, więc komunikat czytało się jak awarię
 * aplikacji, a nie jak podpowiedź. Stąd osobny tekst dla tego przypadku.
 *
 * Limity długości i liczby (#63) sprawdzamy tu, a nie tylko atrybutem
 * `maxLength`: atrybut ogranicza wpisywanie w przeglądarce, ale nie chroni
 * przed wysłaniem formularza z konsoli ani nie powie nic o liczbie
 * umiejętności, która powstaje dopiero po rozbiciu tekstu po przecinkach.
 *
 * `rawSkills` obok `skillList` nie jest duplikatem: surowy tekst rozstrzyga,
 * czy pusta lista wzięła się z pustego pola, czy z samych przecinków - a to
 * dwa różne komunikaty dla użytkownika.
 */
export function validate(values: FormValues): FieldErrors {
  const errors: FieldErrors = {}

  if (!values.fullName.trim()) {
    errors.fullName = 'Podaj imię i nazwisko.'
  } else if (values.fullName.length > SUBMISSION_LIMITS.fullNameMaxLength) {
    errors.fullName = `Imię i nazwisko może mieć najwyżej ${SUBMISSION_LIMITS.fullNameMaxLength} znaków.`
  }

  if (!values.email.trim()) {
    errors.email = 'Podaj adres e-mail.'
  } else if (values.email.length > SUBMISSION_LIMITS.emailMaxLength) {
    errors.email = `Adres e-mail może mieć najwyżej ${SUBMISSION_LIMITS.emailMaxLength} znaków.`
  }

  const tooLong = values.skillList.filter(
    (skill) => skill.length > SUBMISSION_LIMITS.skillMaxLength,
  )

  if (values.skillList.length === 0) {
    errors.skills = values.rawSkills.trim()
      ? 'Wpisz umiejętności oddzielone przecinkami - same przecinki to za mało.'
      : 'Podaj co najmniej jedną umiejętność.'
  } else if (values.skillList.length > SUBMISSION_LIMITS.maxSkills) {
    errors.skills = `Podaj najwyżej ${SUBMISSION_LIMITS.maxSkills} umiejętności (masz ${values.skillList.length}).`
  } else if (tooLong.length > 0) {
    errors.skills = `Każda umiejętność może mieć najwyżej ${SUBMISSION_LIMITS.skillMaxLength} znaków - skróć: ${tooLong[0].slice(0, 20)}...`
  }

  if (!values.experienceLevel) {
    errors.experienceLevel = 'Wybierz poziom doświadczenia.'
  }

  if (!values.preferredRole) {
    errors.preferredRole = 'Wybierz preferowaną rolę.'
  }

  return errors
}
