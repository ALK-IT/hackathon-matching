import { useState } from 'react'
import './App.css'
import SubmissionForm from './SubmissionForm'
import SubmissionList from './SubmissionList'

function App() {
  // Licznik podbijany po każdym udanym zgłoszeniu. Lista obserwuje tę wartość
  // i pobiera dane od nowa, gdy się zmieni. To standardowy sposób, w jaki dwa
  // sąsiednie komponenty porozumiewają się przez wspólnego rodzica - żaden
  // z nich nie musi wiedzieć o istnieniu drugiego.
  const [reloadToken, setReloadToken] = useState(0)

  return (
    <main style={{ fontFamily: 'sans-serif', textAlign: 'center', marginTop: '4rem' }}>
      <h1>hackathon-matching</h1>
      <p>Zgłoś się na hackathon:</p>
      <SubmissionForm onSuccess={() => setReloadToken((token) => token + 1)} />
      <SubmissionList reloadToken={reloadToken} />
    </main>
  )
}

export default App
