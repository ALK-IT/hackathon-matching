import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import ErrorBoundary from './ErrorBoundary'

function Bomba(): never {
  throw new Error('celowy błąd renderu')
}

describe('ErrorBoundary', () => {
  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('pokazuje dzieci, gdy nic się nie psuje', () => {
    render(
      <ErrorBoundary>
        <p>zdrowa treść</p>
      </ErrorBoundary>,
    )
    expect(screen.getByText('zdrowa treść')).toBeInTheDocument()
  })

  it('łapie błąd renderu i pokazuje komunikat zamiast białego ekranu (#66)', () => {
    // React wypisuje złapany błąd do konsoli - wyciszamy, żeby log testów
    // nie wyglądał na czerwony przy teście, który MA wywołać wyjątek.
    vi.spyOn(console, 'error').mockImplementation(() => {})

    render(
      <ErrorBoundary>
        <Bomba />
      </ErrorBoundary>,
    )

    expect(screen.getByText(/coś poszło nie tak/i)).toBeInTheDocument()
    expect(screen.getByText(/odśwież stronę/i)).toBeInTheDocument()
  })
})
