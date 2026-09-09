import { Component, type ErrorInfo, type ReactNode } from 'react'

type Props = { children: ReactNode }
type State = { hasError: boolean }

/** Siatka bezpieczeństwa na błędy renderu (#66).
 *
 * Bez niej dowolny wyjątek w renderze któregokolwiek komponentu zdejmuje
 * całe drzewo Reacta - biały ekran zabiera także części aplikacji, które
 * z błędem nie mają nic wspólnego. Musi być komponentem klasowym: hooki
 * nie mają odpowiednika getDerivedStateFromError.
 */
class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false }

  static getDerivedStateFromError(): State {
    return { hasError: true }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Celowo tylko konsola - nie mamy zbierania błędów, a połknięcie
    // wyjątku bez śladu utrudniłoby diagnozę na miejscu.
    console.error('Nieobsłużony błąd renderu:', error, info.componentStack)
  }

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <main style={{ fontFamily: 'sans-serif', textAlign: 'center', marginTop: '4rem' }}>
          <h1>Coś poszło nie tak</h1>
          <p>Odśwież stronę. Jeśli problem wraca, daj znać zespołowi.</p>
        </main>
      )
    }
    return this.props.children
  }
}

export default ErrorBoundary
