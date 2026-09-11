import { useRef, useState, type SubmitEvent } from 'react'
import { createSubmission, toErrorMessage } from './api'
import {
  EXPERIENCE_LEVELS,
  EXPERIENCE_LEVEL_LABELS,
  PREFERRED_ROLES,
  PREFERRED_ROLE_LABELS,
  SUBMISSION_LIMITS,
  parseSkills,
  type ExperienceLevel,
  type PreferredRole,
} from './submissionProfile'

type Status = 'idle' | 'submitting' | 'success' | 'error'

type FieldName = 'fullName' | 'email' | 'skills' | 'experienceLevel' | 'preferredRole'

type FieldErrors = Partial<Record<FieldName, string>>

/** Kolejność pól w formularzu.
 *
 * Potrzebna, bo po nieudanej walidacji ustawiamy fokus na PIERWSZYM błędnym
 * polu, a `Object.keys` na obiekcie błędów dałoby kolejność przypadkową -
 * użytkownik czytnika ekranu wylądowałby w środku formularza. */
const FIELD_ORDER: readonly FieldName[] = [
  'fullName',
  'email',
  'skills',
  'experienceLevel',
  'preferredRole',
]

type FormValues = {
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
 * Funkcja jest czysta (żadnego stanu, żadnego DOM-u), więc testuje się ją
 * bez renderowania komponentu.
 */
function validate(values: FormValues): FieldErrors {
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

type Props = {
  /** Wywoływane po udanym zapisie - App używa tego, żeby odświeżyć listę. */
  onSuccess?: () => void
}

const fieldStyle = { display: 'block', width: '100%' }
const errorStyle = { color: 'crimson', margin: '.25rem 0 0', fontSize: '.875rem' } as const
const hintStyle = { color: '#555', margin: '.25rem 0 0', fontSize: '.875rem' } as const

function SubmissionForm({ onSuccess }: Props) {
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [skills, setSkills] = useState('')
  // Poziom i rola startują puste, a nie od pierwszej opcji z listy: gdyby
  // domyślnie stało "Początkujący", zgłoszenia osób, które nie zauważyły tego
  // pola, wyglądałyby dla algorytmu jak świadoma deklaracja.
  const [experienceLevel, setExperienceLevel] = useState<ExperienceLevel | ''>('')
  const [preferredRole, setPreferredRole] = useState<PreferredRole | ''>('')
  const [availability, setAvailability] = useState(true)
  const [status, setStatus] = useState<Status>('idle')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({})

  // Uchwyty do pól, żeby po nieudanej walidacji przenieść fokus na pierwsze
  // błędne (#64). Samo `aria-describedby` nie wystarcza: opis jest czytany
  // dopiero, gdy fokus wejdzie na pole, więc bez tego osoba korzystająca
  // z czytnika kliknęłaby "Wyślij" i nie usłyszała absolutnie nic.
  //
  // Pięć osobnych refów zamiast jednego rejestru `Record<FieldName, ...>`:
  // rejestr wymagałby zapisu do `.current` w funkcji tworzonej przy renderze,
  // co reguła `react-hooks/refs` (React Compiler) słusznie odrzuca. Refy
  // dotykamy wyłącznie w handlerze zdarzenia, czyli tam, gdzie wolno.
  const fullNameRef = useRef<HTMLInputElement>(null)
  const emailRef = useRef<HTMLInputElement>(null)
  const skillsRef = useRef<HTMLTextAreaElement>(null)
  const experienceLevelRef = useRef<HTMLSelectElement>(null)
  const preferredRoleRef = useRef<HTMLSelectElement>(null)

  // Liczone przy renderze, bo licznik pod polem ma pokazywać stan na bieżąco,
  // a nie dopiero po próbie wysłania (#63).
  const skillList = parseSkills(skills)

  const describedBy = (name: FieldName, ...extra: (string | false)[]) => {
    const ids = [...extra, fieldErrors[name] ? `${name}-error` : false].filter(
      (id): id is string => Boolean(id),
    )
    return ids.length > 0 ? ids.join(' ') : undefined
  }

  const handleSubmit = async (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault()

    const errors = validate({
      fullName,
      email,
      rawSkills: skills,
      skillList,
      experienceLevel,
      preferredRole,
    })
    setFieldErrors(errors)

    const firstInvalid = FIELD_ORDER.find((name) => errors[name])
    if (firstInvalid) {
      // Komunikat zbiorczy zostaje wyczyszczony: pola mówią teraz konkretnie,
      // co jest nie tak, a stary błąd z backendu wprowadzałby w błąd.
      setStatus('error')
      setErrorMessage(null)

      const refs: Record<FieldName, { current: HTMLElement | null }> = {
        fullName: fullNameRef,
        email: emailRef,
        skills: skillsRef,
        experienceLevel: experienceLevelRef,
        preferredRole: preferredRoleRef,
      }
      refs[firstInvalid].current?.focus()
      return
    }

    setStatus('submitting')
    setErrorMessage(null)

    // W `try` stoi wyłącznie samo żądanie: błąd w kodzie po sukcesie (np.
    // w `onSuccess`) nie może udawać nieudanego wysłania zgłoszenia.
    try {
      await createSubmission({
        full_name: fullName,
        email,
        skills: skillList,
        // validate() wyżej przepuszcza tylko wybrane pola, więc pusty string
        // już tu nie dotrze - rzutowanie tylko informuje o tym TypeScript.
        experience_level: experienceLevel as ExperienceLevel,
        preferred_role: preferredRole as PreferredRole,
        availability,
      })
    } catch (error) {
      setStatus('error')
      setErrorMessage(toErrorMessage(error))
      return
    }

    setStatus('success')
    setFullName('')
    setEmail('')
    setSkills('')
    setExperienceLevel('')
    setPreferredRole('')
    setAvailability(true)
    onSuccess?.()
  }

  return (
    <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem', maxWidth: '24rem', margin: '0 auto', textAlign: 'left' }}>
      <div>
        <label>
          Imię i nazwisko
          <input
            type="text"
            value={fullName}
            onChange={(event) => setFullName(event.target.value)}
            required
            maxLength={SUBMISSION_LIMITS.fullNameMaxLength}
            aria-invalid={fieldErrors.fullName ? true : undefined}
            aria-describedby={describedBy('fullName')}
            ref={fullNameRef}
            style={fieldStyle}
          />
        </label>
        {/* Komunikat celowo POZA <label>: w środku stałby się częścią nazwy
            pola i czytnik ekranu odczytywałby go przy każdym wejściu na nie. */}
        {fieldErrors.fullName && <p id="fullName-error" style={errorStyle}>{fieldErrors.fullName}</p>}
      </div>
      <div>
        <label>
          Email
          <input
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
            maxLength={SUBMISSION_LIMITS.emailMaxLength}
            aria-invalid={fieldErrors.email ? true : undefined}
            aria-describedby={describedBy('email')}
            ref={emailRef}
            style={fieldStyle}
          />
        </label>
        {fieldErrors.email && <p id="email-error" style={errorStyle}>{fieldErrors.email}</p>}
      </div>
      <div>
        <label>
          Umiejętności (oddziel przecinkami)
          <textarea
            value={skills}
            onChange={(event) => setSkills(event.target.value)}
            placeholder="python, react, figma"
            required
            aria-invalid={fieldErrors.skills ? true : undefined}
            aria-describedby={describedBy('skills', 'skills-hint')}
            ref={skillsRef}
            style={fieldStyle}
          />
        </label>
        <p id="skills-hint" style={hintStyle}>
          {skillList.length} z {SUBMISSION_LIMITS.maxSkills} umiejętności, każda do{' '}
          {SUBMISSION_LIMITS.skillMaxLength} znaków
        </p>
        {fieldErrors.skills && <p id="skills-error" style={errorStyle}>{fieldErrors.skills}</p>}
      </div>
      <div>
        <label>
          Poziom doświadczenia
          <select
            value={experienceLevel}
            onChange={(event) => setExperienceLevel(event.target.value as ExperienceLevel)}
            required
            aria-invalid={fieldErrors.experienceLevel ? true : undefined}
            aria-describedby={describedBy('experienceLevel')}
            ref={experienceLevelRef}
            style={fieldStyle}
          >
            <option value="">Wybierz...</option>
            {EXPERIENCE_LEVELS.map((level) => (
              <option key={level} value={level}>
                {EXPERIENCE_LEVEL_LABELS[level]}
              </option>
            ))}
          </select>
        </label>
        {fieldErrors.experienceLevel && (
          <p id="experienceLevel-error" style={errorStyle}>{fieldErrors.experienceLevel}</p>
        )}
      </div>
      <div>
        <label>
          Preferowana rola
          <select
            value={preferredRole}
            onChange={(event) => setPreferredRole(event.target.value as PreferredRole)}
            required
            aria-invalid={fieldErrors.preferredRole ? true : undefined}
            aria-describedby={describedBy('preferredRole')}
            ref={preferredRoleRef}
            style={fieldStyle}
          >
            <option value="">Wybierz...</option>
            {PREFERRED_ROLES.map((role) => (
              <option key={role} value={role}>
                {PREFERRED_ROLE_LABELS[role]}
              </option>
            ))}
          </select>
        </label>
        {fieldErrors.preferredRole && (
          <p id="preferredRole-error" style={errorStyle}>{fieldErrors.preferredRole}</p>
        )}
      </div>
      <label style={{ display: 'flex', alignItems: 'center', gap: '.5rem' }}>
        <input
          type="checkbox"
          checked={availability}
          onChange={(event) => setAvailability(event.target.checked)}
        />
        Jestem dostępny/a przez cały czas trwania hackathonu
      </label>
      <button type="submit" disabled={status === 'submitting'}>
        {status === 'submitting' ? 'Wysyłanie...' : 'Wyślij zgłoszenie'}
      </button>
      {/* role="status" (grzeczne) dla sukcesu, role="alert" (natychmiastowe)
          dla błędu - inaczej czytnik ekranu nie powie o nich ani słowa, bo
          oba <p> pojawiają się i znikają bez zmiany fokusu (#64). */}
      {status === 'success' && <p role="status" style={{ color: 'green' }}>Zgłoszenie wysłane</p>}
      {status === 'error' && errorMessage && (
        <p role="alert" style={{ color: 'crimson' }}>{errorMessage}</p>
      )}
    </form>
  )
}

export default SubmissionForm
