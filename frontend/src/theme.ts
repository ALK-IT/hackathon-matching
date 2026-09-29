/** Wspólna paleta i rozmiary tekstu (#114).
 *
 * Powód jest prozaiczny: `crimson` jako kolor błędu był wpisany osobno
 * w czterech miejscach, w trzech różnych komponentach. Zmiana koloru
 * wymagała czterech edycji i wystarczyło przeoczyć jedną, żeby interfejs
 * przestał być spójny - a nic by o tym nie powiedziało.
 *
 * Zakres jest celowo wąski: kolory i dwa rozmiary tekstu, czyli dokładnie
 * to, co dziś się powtarza. Odstępy, szerokości i marginesy zostają
 * w komponentach - są jednorazowe, a wprowadzanie skali odstępów byłoby
 * decyzją projektową, nie porządkowaniem literałów.
 */

export const colors = {
  /** Komunikaty błędów - formularz, lista, wyniki matchowania. */
  error: 'crimson',
  /** Potwierdzenie wysłania zgłoszenia. */
  success: 'green',
  /** Tekst drugorzędny: podpowiedzi i liczniki pod polami. */
  hint: '#555',
  /** Obramowanie elementów: karty zespołu, nagłówek tabeli. */
  border: '#ccc',
  /** Lżejsza linia rozdzielająca wiersze tabeli. */
  borderSubtle: '#eee',
} as const

export const fontSizes = {
  /** Nagłówek sekcji (`h2`) - lista zgłoszeń, wyniki matchowania. */
  sectionHeading: '1.1rem',
  /** Tekst drugorzędny: podpowiedzi i komunikaty błędów przy polach. */
  small: '.875rem',
} as const
