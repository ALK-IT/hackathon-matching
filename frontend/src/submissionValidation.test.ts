import { describe, it, expect } from 'vitest'
import { SUBMISSION_LIMITS } from './submissionProfile'
import { FIELD_ORDER, validate, type FormValues } from './submissionValidation'

/** Poprawny komplet danych. Każdy test psuje dokładnie jedno pole, więc widać,
 *  która reguła go wywołała - i nie trzeba powtarzać całego obiektu. */
function values(overrides: Partial<FormValues> = {}): FormValues {
  return {
    fullName: 'Jan Kowalski',
    email: 'jan@example.com',
    rawSkills: 'python, react',
    skillList: ['python', 'react'],
    experienceLevel: 'intermediate',
    preferredRole: 'backend',
    ...overrides,
  }
}

describe('validate', () => {
  it('poprawne zgłoszenie nie ma żadnych błędów', () => {
    expect(validate(values())).toEqual({})
  })

  it('puste zgłoszenie wskazuje każde pole z osobna (#65)', () => {
    const errors = validate(
      values({
        fullName: '',
        email: '',
        rawSkills: '',
        skillList: [],
        experienceLevel: '',
        preferredRole: '',
      }),
    )

    expect(errors).toEqual({
      fullName: 'Podaj imię i nazwisko.',
      email: 'Podaj adres e-mail.',
      skills: 'Podaj co najmniej jedną umiejętność.',
      experienceLevel: 'Wybierz poziom doświadczenia.',
      preferredRole: 'Wybierz preferowaną rolę.',
    })
  })

  it('same białe znaki to tyle samo co pusto', () => {
    const errors = validate(values({ fullName: '   ', email: '  ' }))

    expect(errors.fullName).toBe('Podaj imię i nazwisko.')
    expect(errors.email).toBe('Podaj adres e-mail.')
  })

  it('same przecinki w umiejętnościach dają inny komunikat niż puste pole (#65)', () => {
    // Sedno #65: pole WYGLĄDA na wypełnione, więc komunikat musi tłumaczyć
    // powód, zamiast sugerować, że użytkownik czegoś nie wpisał.
    const errors = validate(values({ rawSkills: ' , , ', skillList: [] }))

    expect(errors.skills).toMatch(/same przecinki to za mało/)
    expect(errors.skills).not.toMatch(/co najmniej jedną/)
  })

  it('za długie imię jest odrzucane (#63)', () => {
    const errors = validate(values({ fullName: 'x'.repeat(SUBMISSION_LIMITS.fullNameMaxLength + 1) }))

    expect(errors.fullName).toMatch(new RegExp(`${SUBMISSION_LIMITS.fullNameMaxLength} znaków`))
  })

  it('imię o dokładnie maksymalnej długości przechodzi', () => {
    // Granica włącznie - inaczej limit z backendu i z frontu rozjechałyby się
    // o jeden znak i formularz odrzucałby dane, które API by przyjęło.
    const errors = validate(values({ fullName: 'x'.repeat(SUBMISSION_LIMITS.fullNameMaxLength) }))

    expect(errors.fullName).toBeUndefined()
  })

  it('za długi adres e-mail jest odrzucany (#63)', () => {
    const long = 'a'.repeat(SUBMISSION_LIMITS.emailMaxLength) + '@example.com'
    const errors = validate(values({ email: long }))

    expect(errors.email).toMatch(new RegExp(`${SUBMISSION_LIMITS.emailMaxLength} znaków`))
  })

  it('lista dłuższa niż limit jest odrzucana i podaje liczbę (#63)', () => {
    const tooMany = Array.from({ length: SUBMISSION_LIMITS.maxSkills + 1 }, (_, i) => `skill${i}`)
    const errors = validate(values({ skillList: tooMany, rawSkills: tooMany.join(', ') }))

    expect(errors.skills).toMatch(`(masz ${SUBMISSION_LIMITS.maxSkills + 1})`)
  })

  it('lista o dokładnie maksymalnej długości przechodzi', () => {
    const exactly = Array.from({ length: SUBMISSION_LIMITS.maxSkills }, (_, i) => `skill${i}`)
    const errors = validate(values({ skillList: exactly, rawSkills: exactly.join(', ') }))

    expect(errors.skills).toBeUndefined()
  })

  it('pojedyncza za długa umiejętność jest odrzucana i pokazana w komunikacie (#63)', () => {
    const long = 'x'.repeat(SUBMISSION_LIMITS.skillMaxLength + 1)
    const errors = validate(values({ skillList: ['python', long], rawSkills: `python, ${long}` }))

    expect(errors.skills).toMatch(new RegExp(`${SUBMISSION_LIMITS.skillMaxLength} znaków`))
    // Komunikat pokazuje początek winnej pozycji, żeby dało się ją znaleźć
    // w długiej liście - ale przycięty, żeby nie wkleić całego akapitu.
    expect(errors.skills).toMatch('xxxxx')
  })

  it('brak wybranego poziomu i roli to dwa osobne błędy', () => {
    const errors = validate(values({ experienceLevel: '', preferredRole: '' }))

    expect(errors.experienceLevel).toBe('Wybierz poziom doświadczenia.')
    expect(errors.preferredRole).toBe('Wybierz preferowaną rolę.')
    expect(errors.fullName).toBeUndefined()
  })

  it('FIELD_ORDER odpowiada kolejności pól w formularzu (#64)', () => {
    // Po tej kolejności ustawiamy fokus na pierwszym błędnym polu. Rozjazd
    // z układem formularza przeniósłby fokus w jego środek, zamiast na górę.
    expect(FIELD_ORDER).toEqual([
      'fullName',
      'email',
      'skills',
      'experienceLevel',
      'preferredRole',
    ])
  })
})
