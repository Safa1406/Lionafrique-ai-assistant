import { useEffect, useMemo, useState } from 'react'
import './App.css'

const API_BASE = 'http://127.0.0.1:8000'

const DEFAULT_CONTEXT = {
  program: 'Programme marocain',
  subject: 'Arabe',
  semester: 'Non défini',
  source: 'alnsba (1).pdf',
}

function cycleQuestionTypes(count) {
  const base = ['mcq', 'true_false', 'short_answer']
  return Array.from({ length: count }, (_, index) => base[index % base.length])
}

function normalizeOption(option) {
  if (typeof option === 'string') {
    return { value: option, label: option }
  }

  if (option && typeof option === 'object') {
    const value =
      option.value ??
      option.label ??
      option.text ??
      option.answer ??
      JSON.stringify(option)

    const label =
      option.label ??
      option.text ??
      option.value ??
      option.answer ??
      String(value)

    return {
      value: String(value ?? ''),
      label: String(label ?? ''),
    }
  }

  return {
    value: String(option ?? ''),
    label: String(option ?? ''),
  }
}

async function apiRequest(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
    ...options,
  })

  let body = null

  try {
    body = await response.json()
  } catch {
    body = null
  }

  if (!response.ok) {
    const detail =
      body?.detail ??
      body?.message ??
      `HTTP ${response.status}`

    throw new Error(
      typeof detail === 'string'
        ? detail
        : JSON.stringify(detail),
    )
  }

  return body
}

function App() {
  const [activeTab, setActiveTab] = useState('assistant')
  const [backendStatus, setBackendStatus] = useState('checking')

  const [context, setContext] = useState(DEFAULT_CONTEXT)
  const [studentId, setStudentId] = useState('demo-student')

  const [question, setQuestion] = useState('')
  const [assistantMode, setAssistantMode] = useState('ask')
  const [assistantLoading, setAssistantLoading] = useState(false)
  const [assistantError, setAssistantError] = useState('')
  const [assistantResult, setAssistantResult] = useState(null)

  const [quizCount, setQuizCount] = useState(9)
  const [quizLoading, setQuizLoading] = useState(false)
  const [quizError, setQuizError] = useState('')
  const [quiz, setQuiz] = useState(null)
  const [quizAnswers, setQuizAnswers] = useState({})
  const [quizSubmitting, setQuizSubmitting] = useState(false)
  const [quizResult, setQuizResult] = useState(null)

  const [orientationLoading, setOrientationLoading] = useState(false)
  const [orientationError, setOrientationError] = useState('')
  const [orientation, setOrientation] = useState(null)

  const [exerciseForm, setExerciseForm] = useState({
    subject: 'Mathématiques',
    lesson: 'Équations',
    concept: 'Équations du premier degré',
    score: 4,
    total: 10,
    source: 'equations.pdf',
  })
  const [exerciseLoading, setExerciseLoading] = useState(false)
  const [exerciseMessage, setExerciseMessage] = useState('')

  useEffect(() => {
    apiRequest('/health')
      .then(() => setBackendStatus('online'))
      .catch(() => setBackendStatus('offline'))
  }, [])

  const selectionLabel = useMemo(
    () =>
      [
        context.program,
        context.subject,
        context.semester,
        context.source,
      ]
        .filter(Boolean)
        .join(' • '),
    [context],
  )

  function updateContext(key, value) {
    setContext((current) => ({
      ...current,
      [key]: value,
    }))
  }

  async function runAssistant(event) {
    event.preventDefault()

    if (!question.trim()) {
      setAssistantError('Écris une question ou un sujet à résumer.')
      return
    }

    setAssistantLoading(true)
    setAssistantError('')
    setAssistantResult(null)

    const endpoint =
      assistantMode === 'summary'
        ? '/summarize'
        : '/ask'

    try {
      const data = await apiRequest(endpoint, {
        method: 'POST',
        body: JSON.stringify({
          question: question.trim(),
          number_of_results: 5,
          program: context.program || null,
          subject: context.subject || null,
          semester: context.semester || null,
          source: context.source || null,
        }),
      })

      setAssistantResult(data)
    } catch (error) {
      setAssistantError(error.message)
    } finally {
      setAssistantLoading(false)
    }
  }

  async function generateQuiz() {
    setQuizLoading(true)
    setQuizError('')
    setQuiz(null)
    setQuizAnswers({})
    setQuizResult(null)

    try {
      const count = Math.max(1, Math.min(12, Number(quizCount) || 9))

      const data = await apiRequest('/quiz/generate', {
        method: 'POST',
        body: JSON.stringify({
          program: context.program,
          subject: context.subject,
          semester: context.semester,
          source: context.source,
          difficulty: 'medium',
          count,
          question_types: cycleQuestionTypes(count),
        }),
      })

      setQuiz(data)
    } catch (error) {
      setQuizError(error.message)
    } finally {
      setQuizLoading(false)
    }
  }

  function setQuizAnswer(questionId, answer) {
    setQuizAnswers((current) => ({
      ...current,
      [questionId]: answer,
    }))
  }

  async function submitQuiz() {
    if (!quiz?.quiz_id) {
      return
    }

    setQuizSubmitting(true)
    setQuizError('')

    try {
      const answers = (quiz.questions || []).map((item) => ({
        question_id: item.id,
        answer: String(quizAnswers[item.id] ?? ''),
      }))

      const data = await apiRequest('/quiz/submit', {
        method: 'POST',
        body: JSON.stringify({
          quiz_id: quiz.quiz_id,
          student_id: studentId.trim() || 'demo-student',
          answers,
        }),
      })

      setQuizResult(data)
      await loadOrientation()
    } catch (error) {
      setQuizError(error.message)
    } finally {
      setQuizSubmitting(false)
    }
  }

  async function loadOrientation() {
    const id = studentId.trim() || 'demo-student'

    setOrientationLoading(true)
    setOrientationError('')

    try {
      const data = await apiRequest(
        `/orientation/${encodeURIComponent(id)}`,
      )

      setOrientation(data)
    } catch (error) {
      setOrientationError(error.message)
    } finally {
      setOrientationLoading(false)
    }
  }

  async function addExerciseResult(event) {
    event.preventDefault()

    setExerciseLoading(true)
    setExerciseMessage('')
    setOrientationError('')

    try {
      await apiRequest('/orientation/result', {
        method: 'POST',
        body: JSON.stringify({
          student_id: studentId.trim() || 'demo-student',
          subject: exerciseForm.subject,
          lesson: exerciseForm.lesson,
          concept: exerciseForm.concept,
          score: Number(exerciseForm.score),
          total: Number(exerciseForm.total),
          activity_type: 'exercise',
          source: exerciseForm.source,
        }),
      })

      setExerciseMessage('Résultat d’exercice enregistré.')
      await loadOrientation()
    } catch (error) {
      setOrientationError(error.message)
    } finally {
      setExerciseLoading(false)
    }
  }

  const assistantText =
    assistantMode === 'summary'
      ? assistantResult?.summary
      : assistantResult?.answer

  const sources =
    assistantResult?.sources ??
    assistantResult?.evidence ??
    []

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">LIONAFRIQUE</p>
          <h1>AI Learning Assistant</h1>
          <p className="subtitle">
            Cours, résumé, quiz intelligent et orientation pédagogique.
          </p>
        </div>

        <div
          className={`backend-pill backend-${backendStatus}`}
          title={`Backend: ${backendStatus}`}
        >
          <span className="status-dot" />
          {backendStatus === 'online'
            ? 'Backend connecté'
            : backendStatus === 'offline'
              ? 'Backend hors ligne'
              : 'Connexion...'}
        </div>
      </header>

      <main className="workspace">
        <section className="context-card">
          <div className="section-title-row">
            <div>
              <p className="section-kicker">Contexte d’apprentissage</p>
              <h2>Sélection du cours</h2>
            </div>
            <span className="context-summary">{selectionLabel}</span>
          </div>

          <div className="context-grid">
            <label>
              Programme
              <input
                value={context.program}
                onChange={(event) =>
                  updateContext('program', event.target.value)
                }
              />
            </label>

            <label>
              Matière
              <input
                value={context.subject}
                onChange={(event) =>
                  updateContext('subject', event.target.value)
                }
              />
            </label>

            <label>
              Semestre
              <input
                value={context.semester}
                onChange={(event) =>
                  updateContext('semester', event.target.value)
                }
              />
            </label>

            <label>
              Source / PDF
              <input
                value={context.source}
                onChange={(event) =>
                  updateContext('source', event.target.value)
                }
              />
            </label>
          </div>

          <label className="student-field">
            Identifiant élève
            <input
              value={studentId}
              onChange={(event) => setStudentId(event.target.value)}
              placeholder="demo-student"
            />
          </label>
        </section>

        <nav className="tabs" aria-label="Modules">
          {[
            ['assistant', 'Assistant'],
            ['summary', 'Résumé'],
            ['quiz', 'Quiz'],
            ['orientation', 'Orientation'],
          ].map(([id, label]) => (
            <button
              key={id}
              type="button"
              className={activeTab === id ? 'tab active' : 'tab'}
              onClick={() => {
                setActiveTab(id)

                if (id === 'summary') {
                  setAssistantMode('summary')
                }

                if (id === 'assistant') {
                  setAssistantMode('ask')
                }

                if (id === 'orientation') {
                  loadOrientation()
                }
              }}
            >
              {label}
            </button>
          ))}
        </nav>

        {(activeTab === 'assistant' || activeTab === 'summary') && (
          <section className="panel">
            <div className="panel-heading">
              <div>
                <p className="section-kicker">
                  {activeTab === 'summary'
                    ? 'Synthèse pédagogique'
                    : 'Question / Réponse'}
                </p>
                <h2>
                  {activeTab === 'summary'
                    ? 'Résumer le cours'
                    : 'Interroger le cours'}
                </h2>
              </div>
            </div>

            <form onSubmit={runAssistant} className="assistant-form">
              <textarea
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                placeholder={
                  activeTab === 'summary'
                    ? 'Exemple : Résume ce cours et donne les idées essentielles.'
                    : 'Pose une question basée sur le PDF sélectionné...'
                }
                rows={5}
              />

              <button
                className="primary-button"
                disabled={assistantLoading}
              >
                {assistantLoading
                  ? 'Traitement...'
                  : activeTab === 'summary'
                    ? 'Générer le résumé'
                    : 'Poser la question'}
              </button>
            </form>

            {assistantError && (
              <div className="message error">{assistantError}</div>
            )}

            {assistantResult && (
              <div className="result-card">
                <div className="result-heading">
                  <span className="result-badge">Réponse</span>
                  <strong>
                    {assistantResult.status || 'success'}
                  </strong>
                </div>

                <div className="result-text">
                  {assistantText ||
                    assistantResult.message ||
                    'Aucun texte retourné.'}
                </div>

                {Array.isArray(sources) && sources.length > 0 && (
                  <details className="sources-box">
                    <summary>Sources utilisées</summary>
                    <ul>
                      {sources.map((source, index) => (
                        <li key={`${index}-${source?.file ?? ''}`}>
                          <strong>
                            {source?.file ??
                              source?.source ??
                              `Source ${index + 1}`}
                          </strong>
                          {source?.page != null && (
                            <span>Page {source.page}</span>
                          )}
                        </li>
                      ))}
                    </ul>
                  </details>
                )}
              </div>
            )}
          </section>
        )}

        {activeTab === 'quiz' && (
          <section className="panel">
            <div className="panel-heading">
              <div>
                <p className="section-kicker">Gemini + Grounding</p>
                <h2>Quiz intelligent</h2>
                <p>
                  Les réponses restent validées par le moteur grounded de
                  LIONAFRIQUE. Gemini améliore la génération des questions.
                </p>
              </div>

              <div className="quiz-controls">
                <label>
                  Questions
                  <input
                    type="number"
                    min="3"
                    max="12"
                    value={quizCount}
                    onChange={(event) =>
                      setQuizCount(event.target.value)
                    }
                  />
                </label>

                <button
                  type="button"
                  className="primary-button"
                  onClick={generateQuiz}
                  disabled={quizLoading}
                >
                  {quizLoading ? 'Génération...' : 'Générer le quiz'}
                </button>
              </div>
            </div>

            {quizError && (
              <div className="message error">{quizError}</div>
            )}

            {quiz && (
              <>
                <div className="quiz-meta">
                  <span>
                    Moteur :{' '}
                    <strong>
                      {quiz.generation_engine ||
                        'lionafrique-grounded'}
                    </strong>
                  </span>
                  <span>
                    Gemini :{' '}
                    <strong>{quiz.gemini_status || 'fallback'}</strong>
                  </span>
                  <span>
                    Questions Gemini :{' '}
                    <strong>
                      {quiz.gemini_questions_generated ?? 0}
                    </strong>
                  </span>
                </div>

                <div className="question-list">
                  {(quiz.questions || []).map((item, index) => {
                    const options = Array.isArray(item.options)
                      ? item.options.map(normalizeOption)
                      : []

                    return (
                      <article className="quiz-card" key={item.id}>
                        <div className="quiz-card-top">
                          <span>Question {index + 1}</span>
                          <span className="type-badge">{item.type}</span>
                        </div>

                        <h3>{item.question}</h3>

                        {options.length > 0 ? (
                          <div className="options-list">
                            {options.map((option) => (
                              <label
                                className="option-row"
                                key={`${item.id}-${option.value}`}
                              >
                                <input
                                  type="radio"
                                  name={`question-${item.id}`}
                                  checked={
                                    quizAnswers[item.id] === option.value
                                  }
                                  onChange={() =>
                                    setQuizAnswer(
                                      item.id,
                                      option.value,
                                    )
                                  }
                                />
                                <span>{option.label}</span>
                              </label>
                            ))}
                          </div>
                        ) : (
                          <textarea
                            rows={3}
                            value={quizAnswers[item.id] ?? ''}
                            onChange={(event) =>
                              setQuizAnswer(
                                item.id,
                                event.target.value,
                              )
                            }
                            placeholder="Écris ta réponse..."
                          />
                        )}

                        <div className="question-source">
                          {item.source && <span>{item.source}</span>}
                          {item.page != null && (
                            <span>Page {item.page}</span>
                          )}
                        </div>
                      </article>
                    )
                  })}
                </div>

                <button
                  type="button"
                  className="primary-button submit-quiz"
                  onClick={submitQuiz}
                  disabled={quizSubmitting}
                >
                  {quizSubmitting
                    ? 'Correction...'
                    : 'Valider mes réponses'}
                </button>
              </>
            )}

            {quizResult && (
              <div className="score-card">
                <div>
                  <p className="section-kicker">Résultat</p>
                  <h3>
                    {quizResult.score} / {quizResult.total}
                  </h3>
                </div>
                <div className="score-percent">
                  {quizResult.total
                    ? Math.round(
                        (Number(quizResult.score) /
                          Number(quizResult.total)) *
                          100,
                      )
                    : 0}
                  %
                </div>
                <p>
                  Le résultat a été envoyé automatiquement au module
                  Orientation pour mettre à jour les priorités de révision.
                </p>
              </div>
            )}
          </section>
        )}

        {activeTab === 'orientation' && (
          <section className="panel">
            <div className="panel-heading orientation-heading">
              <div>
                <p className="section-kicker">
                  Orientation pédagogique adaptative
                </p>
                <h2>Plan de progression</h2>
                <p>
                  Basé uniquement sur les résultats de quiz et exercices.
                </p>
              </div>

              <button
                type="button"
                className="secondary-button"
                onClick={loadOrientation}
                disabled={orientationLoading}
              >
                {orientationLoading ? 'Analyse...' : 'Actualiser'}
              </button>
            </div>

            {orientationError && (
              <div className="message error">{orientationError}</div>
            )}

            {orientation && (
              <>
                <div className="orientation-overview">
                  <div className="metric-card">
                    <span>Maîtrise globale</span>
                    <strong>
                      {orientation.overall_mastery == null
                        ? '—'
                        : `${orientation.overall_mastery}%`}
                    </strong>
                  </div>

                  <div className="metric-card">
                    <span>Activités analysées</span>
                    <strong>{orientation.attempt_count ?? 0}</strong>
                  </div>

                  <div className="metric-card">
                    <span>Points à renforcer</span>
                    <strong>{orientation.weak_areas?.length ?? 0}</strong>
                  </div>
                </div>

                <div className="ai-guidance-card">
                  <div className="ai-heading">
                    <div>
                      <p className="section-kicker">Gemini guidance</p>
                      <h3>Conseil personnalisé</h3>
                    </div>
                    <span
                      className={
                        orientation.ai_status === 'success'
                          ? 'ai-pill success'
                          : 'ai-pill fallback'
                      }
                    >
                      {orientation.ai_status || 'fallback'}
                    </span>
                  </div>

                  <p>
                    {orientation.ai_guidance ||
                      orientation.message ||
                      'Pas encore assez de résultats pour générer un conseil.'}
                  </p>
                </div>

                <div className="revision-grid">
                  {(orientation.revision_plan || []).map((item) => (
                    <article className="revision-card" key={`${item.rank}-${item.subject}-${item.concept}`}>
                      <div className="revision-top">
                        <span>Priorité #{item.rank}</span>
                        <span className={`priority priority-${item.priority}`}>
                          {item.priority}
                        </span>
                      </div>

                      <h3>{item.subject}</h3>
                      <p className="concept">{item.concept}</p>

                      <div className="mastery-row">
                        <span>Actuel : {item.current_mastery}%</span>
                        <span>Cible : {item.target_mastery}%</span>
                      </div>

                      <div className="progress-track">
                        <span
                          style={{
                            width: `${Math.max(
                              0,
                              Math.min(
                                100,
                                Number(item.current_mastery) || 0,
                              ),
                            )}%`,
                          }}
                        />
                      </div>

                      <ul>
                        {(item.actions || []).map((action) => (
                          <li key={action}>
                            {action.replaceAll('_', ' ')}
                          </li>
                        ))}
                      </ul>

                      <p className="recommendation">
                        {item.recommendation}
                      </p>
                    </article>
                  ))}
                </div>
              </>
            )}

            <form
              className="exercise-card"
              onSubmit={addExerciseResult}
            >
              <div>
                <p className="section-kicker">Test rapide</p>
                <h3>Ajouter un résultat d’exercice</h3>
              </div>

              <div className="exercise-grid">
                {[
                  ['subject', 'Matière'],
                  ['lesson', 'Leçon'],
                  ['concept', 'Concept'],
                  ['source', 'Source'],
                ].map(([key, label]) => (
                  <label key={key}>
                    {label}
                    <input
                      value={exerciseForm[key]}
                      onChange={(event) =>
                        setExerciseForm((current) => ({
                          ...current,
                          [key]: event.target.value,
                        }))
                      }
                    />
                  </label>
                ))}

                <label>
                  Score
                  <input
                    type="number"
                    min="0"
                    value={exerciseForm.score}
                    onChange={(event) =>
                      setExerciseForm((current) => ({
                        ...current,
                        score: event.target.value,
                      }))
                    }
                  />
                </label>

                <label>
                  Total
                  <input
                    type="number"
                    min="1"
                    value={exerciseForm.total}
                    onChange={(event) =>
                      setExerciseForm((current) => ({
                        ...current,
                        total: event.target.value,
                      }))
                    }
                  />
                </label>
              </div>

              <button
                className="secondary-button"
                disabled={exerciseLoading}
              >
                {exerciseLoading
                  ? 'Enregistrement...'
                  : 'Enregistrer et analyser'}
              </button>

              {exerciseMessage && (
                <div className="message success">
                  {exerciseMessage}
                </div>
              )}
            </form>
          </section>
        )}
      </main>

      <footer>
        LIONAFRIQUE AI Assistant • Grounded learning • Gemini enhanced
      </footer>
    </div>
  )
}

export default App
