import './App.css'
import SubmissionForm from './SubmissionForm'

function App() {
  return (
    <main style={{ fontFamily: 'sans-serif', textAlign: 'center', marginTop: '4rem' }}>
      <h1>hackathon-matching</h1>
      <p>Zgłoś się na hackathon:</p>
      <SubmissionForm />
    </main>
  )
}

export default App
