import {
  useMemo,
  useState,
} from "react";

import "./LearningTools.css";

const API_URL =
  "http://127.0.0.1:8000";

async function readJsonResponse(
  response
) {
  try {
    return await response.json();
  } catch {
    return {};
  }
}

function normalizeOption(
  option
) {
  if (
    option &&
    typeof option === "object"
  ) {
    const value =
      option.value ??
      option.label ??
      option.text ??
      option.answer ??
      "";

    const label =
      option.label ??
      option.text ??
      option.value ??
      option.answer ??
      "";

    return {
      value: String(value),
      label: String(label),
    };
  }

  return {
    value: String(option ?? ""),
    label: String(option ?? ""),
  };
}

function buildMixedTypes(
  count
) {
  const sequence = [
    "mcq",
    "true_false",
    "short_answer",
  ];

  return Array.from(
    { length: count },
    (_, index) =>
      sequence[
        index %
        sequence.length
      ]
  );
}

function extractSources(
  metadataOptions,
  program,
  subject,
  semester
) {
  const candidates = [];

  for (
    const option
    of metadataOptions || []
  ) {
    if (
      option?.program !== program ||
      option?.subject !== subject
    ) {
      continue;
    }

    const optionSemesters =
      Array.isArray(
        option?.semesters
      )
        ? option.semesters
        : [];

    if (
      semester &&
      optionSemesters.length > 0 &&
      !optionSemesters.includes(
        semester
      )
    ) {
      continue;
    }

    const possibleSources = [
      option?.source,
      option?.file,
      option?.pdf,
      ...(Array.isArray(
        option?.sources
      )
        ? option.sources
        : []),
      ...(Array.isArray(
        option?.files
      )
        ? option.files
        : []),
      ...(Array.isArray(
        option?.documents
      )
        ? option.documents
        : []),
    ];

    for (
      const source
      of possibleSources
    ) {
      if (
        typeof source === "string" &&
        source.trim()
      ) {
        candidates.push(
          source.trim()
        );
      } else if (
        source &&
        typeof source === "object"
      ) {
        const value =
          source.file ??
          source.source ??
          source.name ??
          source.filename ??
          "";

        if (
          typeof value === "string" &&
          value.trim()
        ) {
          candidates.push(
            value.trim()
          );
        }
      }
    }
  }

  return [
    ...new Set(candidates),
  ].sort(
    (first, second) =>
      first.localeCompare(
        second,
        "fr",
        {
          sensitivity: "base",
        }
      )
  );
}

function toPercent(
  value
) {
  const number =
    Number(value);

  if (
    Number.isNaN(number)
  ) {
    return null;
  }

  return Math.max(
    0,
    Math.min(
      100,
      Math.round(number)
    )
  );
}

function profileItemLabel(
  item
) {
  if (
    typeof item === "string"
  ) {
    return item;
  }

  return (
    item?.concept ??
    item?.lesson ??
    item?.subject ??
    item?.name ??
    item?.label ??
    "Élément"
  );
}

function profileItemMastery(
  item
) {
  if (
    typeof item !== "object" ||
    item === null
  ) {
    return null;
  }

  return toPercent(
    item.current_mastery ??
    item.mastery ??
    item.score_percent ??
    item.percentage ??
    item.score
  );
}

function buildPerformanceRows(
  orientation
) {
  const rows = new Map();

  const candidates = [
    ...(orientation?.revision_plan || []),
    ...(orientation?.weak_areas || []),
    ...(orientation?.strengths || []),
  ];

  for (
    const item
    of candidates
  ) {
    if (
      !item ||
      typeof item !== "object"
    ) {
      continue;
    }

    const subject =
      String(
        item.subject ??
        item.area ??
        ""
      ).trim();

    const mastery =
      profileItemMastery(
        item
      );

    if (
      !subject ||
      mastery === null
    ) {
      continue;
    }

    const existing =
      rows.get(subject);

    if (
      !existing
    ) {
      rows.set(
        subject,
        {
          subject,
          values: [
            mastery,
          ],
        }
      );
    } else {
      existing.values.push(
        mastery
      );
    }
  }

  return Array.from(
    rows.values()
  )
    .map(
      (
        row
      ) => ({
        subject:
          row.subject,
        mastery:
          Math.round(
            row.values.reduce(
              (
                total,
                value
              ) =>
                total +
                value,
              0
            ) /
            row.values.length
          ),
      })
    )
    .sort(
      (
        first,
        second
      ) =>
        first.mastery -
        second.mastery
    );
}

function LearningTools({
  metadataOptions,
  selectedProgram,
  selectedSubject,
  selectedSemester,
  isParentBusy = false,
}) {
  const [
    studentId,
    setStudentId,
  ] = useState(
    "demo-student"
  );

  const [
    manualSource,
    setManualSource,
  ] = useState("");

  const [
    selectedSource,
    setSelectedSource,
  ] = useState("");

  const [
    quizCount,
    setQuizCount,
  ] = useState(9);

  const [
    quiz,
    setQuiz,
  ] = useState(null);

  const [
    answers,
    setAnswers,
  ] = useState({});

  const [
    quizResult,
    setQuizResult,
  ] = useState(null);

  const [
    quizLoading,
    setQuizLoading,
  ] = useState(false);

  const [
    quizSubmitting,
    setQuizSubmitting,
  ] = useState(false);

  const [
    quizError,
    setQuizError,
  ] = useState("");

  const [
    orientation,
    setOrientation,
  ] = useState(null);

  const [
    orientationLoading,
    setOrientationLoading,
  ] = useState(false);

  const [
    orientationError,
    setOrientationError,
  ] = useState("");

  const [
    activeLearningTab,
    setActiveLearningTab,
  ] = useState(
    "quiz"
  );

  const availableSources =
    useMemo(
      () =>
        extractSources(
          metadataOptions,
          selectedProgram,
          selectedSubject,
          selectedSemester
        ),
      [
        metadataOptions,
        selectedProgram,
        selectedSubject,
        selectedSemester,
      ]
    );

  const sourceValue =
    selectedSource ||
    manualSource.trim() ||
    availableSources[0] ||
    "";

  const canGenerate =
    Boolean(
      selectedProgram &&
      selectedSubject &&
      sourceValue &&
      !quizLoading &&
      !quizSubmitting &&
      !isParentBusy
    );

  const performanceRows =
    useMemo(
      () =>
        buildPerformanceRows(
          orientation
        ),
      [
        orientation,
      ]
    );

  const strengths =
    Array.isArray(
      orientation?.strengths
    )
      ? orientation.strengths
      : [];

  const weakAreas =
    Array.isArray(
      orientation?.weak_areas
    )
      ? orientation.weak_areas
      : [];

  const overallMastery =
    toPercent(
      orientation?.overall_mastery
    );

  const initials =
    (
      studentId.trim() ||
      "ET"
    )
      .slice(0, 2)
      .toUpperCase();

  const setAnswer = (
    questionId,
    value
  ) => {
    setAnswers(
      (
        previous
      ) => ({
        ...previous,
        [questionId]:
          value,
      })
    );
  };

  const generateQuiz =
    async () => {
      if (
        !canGenerate
      ) {
        setQuizError(
          "Sélectionnez un programme, une matière et une source PDF."
        );
        return;
      }

      setQuizLoading(
        true
      );
      setQuizError("");
      setQuiz(null);
      setAnswers({});
      setQuizResult(null);

      try {
        const count =
          Math.max(
            3,
            Math.min(
              12,
              Number(
                quizCount
              ) || 9
            )
          );

        const response =
          await fetch(
            `${API_URL}/quiz/generate`,
            {
              method:
                "POST",
              headers: {
                "Content-Type":
                  "application/json",
              },
              body:
                JSON.stringify({
                  program:
                    selectedProgram,
                  subject:
                    selectedSubject,
                  semester:
                    selectedSemester ||
                    "Non défini",
                  source:
                    sourceValue,
                  difficulty:
                    "medium",
                  count,
                  question_types:
                    buildMixedTypes(
                      count
                    ),
                }),
            }
          );

        const data =
          await readJsonResponse(
            response
          );

        if (
          !response.ok
        ) {
          throw new Error(
            data.detail ||
            "La génération du quiz a échoué."
          );
        }

        setQuiz(
          data
        );
      } catch (
        error
      ) {
        setQuizError(
          error.message ||
          "La génération du quiz a échoué."
        );
      } finally {
        setQuizLoading(
          false
        );
      }
    };

  const loadOrientation =
    async () => {
      const id =
        studentId.trim() ||
        "demo-student";

      setOrientationLoading(
        true
      );
      setOrientationError(
        ""
      );

      try {
        const response =
          await fetch(
            `${API_URL}/orientation/${encodeURIComponent(
              id
            )}`
          );

        const data =
          await readJsonResponse(
            response
          );

        if (
          !response.ok
        ) {
          throw new Error(
            data.detail ||
            "L’analyse d’orientation a échoué."
          );
        }

        setOrientation(
          data
        );
      } catch (
        error
      ) {
        setOrientationError(
          error.message ||
          "L’analyse d’orientation a échoué."
        );
      } finally {
        setOrientationLoading(
          false
        );
      }
    };

  const submitQuiz =
    async () => {
      if (
        !quiz?.quiz_id
      ) {
        return;
      }

      setQuizSubmitting(
        true
      );
      setQuizError("");

      try {
        const submittedAnswers =
          (
            quiz.questions ||
            []
          ).map(
            (
              item
            ) => ({
              question_id:
                item.id,
              answer:
                String(
                  answers[
                    item.id
                  ] ?? ""
                ),
            })
          );

        const response =
          await fetch(
            `${API_URL}/quiz/submit`,
            {
              method:
                "POST",
              headers: {
                "Content-Type":
                  "application/json",
              },
              body:
                JSON.stringify({
                  quiz_id:
                    quiz.quiz_id,
                  student_id:
                    studentId.trim() ||
                    "demo-student",
                  answers:
                    submittedAnswers,
                }),
            }
          );

        const data =
          await readJsonResponse(
            response
          );

        if (
          !response.ok
        ) {
          throw new Error(
            data.detail ||
            "La correction du quiz a échoué."
          );
        }

        setQuizResult(
          data
        );
        setActiveLearningTab(
          "profile"
        );

        await loadOrientation();
      } catch (
        error
      ) {
        setQuizError(
          error.message ||
          "La correction du quiz a échoué."
        );
      } finally {
        setQuizSubmitting(
          false
        );
      }
    };

  return (
    <section
      className="learning-tools-section"
    >
      <div
        className="learning-tools-header"
      >
        <div>
          <p
            className="card-label"
          >
            Accompagnement personnalisé
          </p>

          <h2>
            Quiz et profil d’apprentissage
          </h2>

          <p>
            Évaluez vos acquis puis suivez
            votre progression et vos priorités
            de révision.
          </p>
        </div>

        <div
          className="learning-tabs"
          role="tablist"
          aria-label="Quiz et profil d’apprentissage"
        >
          <button
            type="button"
            className={
              activeLearningTab ===
              "quiz"
                ? "learning-tab learning-tab-active"
                : "learning-tab"
            }
            onClick={() =>
              setActiveLearningTab(
                "quiz"
              )
            }
          >
            Quiz
          </button>

          <button
            type="button"
            className={
              activeLearningTab ===
              "profile"
                ? "learning-tab learning-tab-active"
                : "learning-tab"
            }
            onClick={() => {
              setActiveLearningTab(
                "profile"
              );
              loadOrientation();
            }}
          >
            Profil d’apprentissage
          </button>
        </div>
      </div>

      <div
        className="learning-context"
      >
        <label>
          Identifiant élève
          <input
            value={
              studentId
            }
            onChange={(
              event
            ) =>
              setStudentId(
                event.target.value
              )
            }
          />
        </label>

        {availableSources.length >
        0 ? (
          <label>
            Source PDF
            <select
              value={
                selectedSource ||
                availableSources[0]
              }
              onChange={(
                event
              ) =>
                setSelectedSource(
                  event.target.value
                )
              }
            >
              {availableSources.map(
                (
                  source
                ) => (
                  <option
                    key={
                      source
                    }
                    value={
                      source
                    }
                  >
                    {source}
                  </option>
                )
              )}
            </select>
          </label>
        ) : (
          <label>
            Source PDF
            <input
              value={
                manualSource
              }
              onChange={(
                event
              ) =>
                setManualSource(
                  event.target.value
                )
              }
              placeholder="Nom du fichier PDF"
            />
          </label>
        )}
      </div>

      {!selectedProgram ||
      !selectedSubject ? (
        <p
          className="learning-note"
        >
          Sélectionnez d’abord
          votre programme et votre matière
          dans l’étape 1.
        </p>
      ) : null}

      {activeLearningTab ===
        "quiz" && (
        <div
          className="learning-panel"
        >
          <div
            className="quiz-toolbar"
          >
            <label>
              Nombre de questions
              <select
                value={
                  quizCount
                }
                onChange={(
                  event
                ) =>
                  setQuizCount(
                    Number(
                      event.target.value
                    )
                  )
                }
                disabled={
                  quizLoading ||
                  quizSubmitting
                }
              >
                <option
                  value={3}
                >
                  3
                </option>
                <option
                  value={6}
                >
                  6
                </option>
                <option
                  value={9}
                >
                  9
                </option>
              </select>
            </label>

            <button
              type="button"
              className="submit-button learning-main-button"
              onClick={
                generateQuiz
              }
              disabled={
                !canGenerate
              }
            >
              {quizLoading
                ? "Génération du quiz..."
                : "Générer le quiz"}
            </button>
          </div>

          {quizError && (
            <div
              className="learning-error"
            >
              {quizError}
            </div>
          )}

          {quiz && (
            <>
              <div
                className="quiz-engine-info"
              >
                <span>
                  Moteur :{" "}
                  <strong>
                    {quiz.generation_engine ||
                      "lionafrique-grounded"}
                  </strong>
                </span>

                <span>
                  Gemini :{" "}
                  <strong>
                    {quiz.gemini_status ||
                      "fallback"}
                  </strong>
                </span>
              </div>

              <div
                className="learning-question-list"
              >
                {(
                  quiz.questions ||
                  []
                ).map(
                  (
                    item,
                    index
                  ) => {
                    const options =
                      Array.isArray(
                        item.options
                      )
                        ? item.options.map(
                          normalizeOption
                        )
                        : [];

                    return (
                      <article
                        className="learning-question-card"
                        key={
                          item.id
                        }
                      >
                        <div
                          className="learning-question-meta"
                        >
                          <span>
                            Question
                            {" "}
                            {index +
                              1}
                          </span>

                          <span>
                            {item.type}
                          </span>
                        </div>

                        <h3>
                          {item.question}
                        </h3>

                        {options.length >
                        0 ? (
                          <div
                            className="learning-options"
                          >
                            {options.map(
                              (
                                option
                              ) => (
                                <label
                                  className="learning-option"
                                  key={
                                    `${item.id}-${option.value}`
                                  }
                                >
                                  <input
                                    type="radio"
                                    name={
                                      `quiz-${item.id}`
                                    }
                                    checked={
                                      answers[
                                        item.id
                                      ] ===
                                      option.value
                                    }
                                    onChange={() =>
                                      setAnswer(
                                        item.id,
                                        option.value
                                      )
                                    }
                                  />

                                  <span>
                                    {option.label}
                                  </span>
                                </label>
                              )
                            )}
                          </div>
                        ) : (
                          <textarea
                            rows="3"
                            value={
                              answers[
                                item.id
                              ] || ""
                            }
                            onChange={(
                              event
                            ) =>
                              setAnswer(
                                item.id,
                                event.target.value
                              )
                            }
                            placeholder="Écrivez votre réponse..."
                          />
                        )}

                        <div
                          className="learning-source-row"
                        >
                          {item.source && (
                            <span>
                              {item.source}
                            </span>
                          )}

                          {item.page !=
                            null && (
                            <span>
                              Page
                              {" "}
                              {item.page}
                            </span>
                          )}
                        </div>
                      </article>
                    );
                  }
                )}
              </div>

              <button
                type="button"
                className="submit-button learning-submit-quiz"
                onClick={
                  submitQuiz
                }
                disabled={
                  quizSubmitting
                }
              >
                {quizSubmitting
                  ? "Correction..."
                  : "Valider le quiz"}
              </button>
            </>
          )}

          {quizResult && (
            <div
              className="learning-score-card"
            >
              <div>
                <p
                  className="card-label"
                >
                  Résultat
                </p>

                <h3>
                  {quizResult.score}
                  {" / "}
                  {quizResult.total}
                </h3>
              </div>

              <strong>
                {quizResult.total
                  ? Math.round(
                    (
                      Number(
                        quizResult.score
                      ) /
                      Number(
                        quizResult.total
                      )
                    ) *
                    100
                  )
                  : 0}
                %
              </strong>
            </div>
          )}
        </div>
      )}

      {activeLearningTab ===
        "profile" && (
        <div
          className="learning-panel"
        >
          <div
            className="student-profile-hero"
          >
            <div
              className="student-avatar"
              aria-hidden="true"
            >
              {initials}
            </div>

            <div
              className="student-profile-main"
            >
              <p
                className="card-label"
              >
                Profil d’apprentissage
              </p>

              <h3>
                {studentId.trim() ||
                  "demo-student"}
              </h3>

              <p>
                Profil dynamique basé sur
                les quiz et les exercices
                réalisés dans LIONAFRIQUE.
              </p>
            </div>

            <button
              type="button"
              className="small-button"
              onClick={
                loadOrientation
              }
              disabled={
                orientationLoading
              }
            >
              {orientationLoading
                ? "Analyse..."
                : "Actualiser"}
            </button>
          </div>

          {orientationError && (
            <div
              className="learning-error"
            >
              {orientationError}
            </div>
          )}

          {orientation && (
            <>
              <div
                className="profile-stat-grid"
              >
                <div
                  className="profile-stat-card profile-stat-primary"
                >
                  <span>
                    Maîtrise globale
                  </span>

                  <strong>
                    {overallMastery ===
                    null
                      ? "—"
                      : `${overallMastery}%`}
                  </strong>

                  <small>
                    Niveau actuel
                  </small>
                </div>

                <div
                  className="profile-stat-card"
                >
                  <span>
                    Activités analysées
                  </span>

                  <strong>
                    {orientation.attempt_count ||
                      0}
                  </strong>

                  <small>
                    Quiz et exercices
                  </small>
                </div>

                <div
                  className="profile-stat-card"
                >
                  <span>
                    Points forts
                  </span>

                  <strong>
                    {strengths.length}
                  </strong>

                  <small>
                    Maîtrise élevée
                  </small>
                </div>

                <div
                  className="profile-stat-card"
                >
                  <span>
                    À améliorer
                  </span>

                  <strong>
                    {weakAreas.length}
                  </strong>

                  <small>
                    Priorités actuelles
                  </small>
                </div>
              </div>

              <div
                className="profile-two-column"
              >
                <section
                  className="profile-subcard"
                >
                  <div
                    className="profile-subcard-header"
                  >
                    <div>
                      <p
                        className="card-label"
                      >
                        Performance
                      </p>

                      <h3>
                        Par matière
                      </h3>
                    </div>
                  </div>

                  {performanceRows.length >
                  0 ? (
                    <div
                      className="subject-performance-list"
                    >
                      {performanceRows.map(
                        (
                          row
                        ) => (
                          <div
                            className="subject-performance-item"
                            key={
                              row.subject
                            }
                          >
                            <div>
                              <strong>
                                {row.subject}
                              </strong>

                              <span>
                                {row.mastery}%
                              </span>
                            </div>

                            <div
                              className="subject-performance-track"
                            >
                              <span
                                style={{
                                  width:
                                    `${row.mastery}%`,
                                }}
                              />
                            </div>
                          </div>
                        )
                      )}
                    </div>
                  ) : (
                    <p
                      className="profile-empty"
                    >
                      Les performances par
                      matière apparaîtront
                      après plusieurs activités.
                    </p>
                  )}
                </section>

                <section
                  className="profile-subcard"
                >
                  <div
                    className="profile-subcard-header"
                  >
                    <div>
                      <p
                        className="card-label"
                      >
                        Diagnostic
                      </p>

                      <h3>
                        Forces et axes
                        d’amélioration
                      </h3>
                    </div>
                  </div>

                  <div
                    className="strength-weak-grid"
                  >
                    <div>
                      <h4>
                        Points forts
                      </h4>

                      {strengths.length >
                      0 ? (
                        <ul
                          className="profile-tag-list"
                        >
                          {strengths
                            .slice(
                              0,
                              5
                            )
                            .map(
                              (
                                item,
                                index
                              ) => (
                                <li
                                  className="profile-tag profile-tag-strong"
                                  key={
                                    `strength-${index}-${profileItemLabel(item)}`
                                  }
                                >
                                  <span>
                                    {profileItemLabel(
                                      item
                                    )}
                                  </span>

                                  {profileItemMastery(
                                    item
                                  ) !==
                                    null && (
                                    <strong>
                                      {profileItemMastery(
                                        item
                                      )}
                                      %
                                    </strong>
                                  )}
                                </li>
                              )
                            )}
                        </ul>
                      ) : (
                        <p
                          className="profile-empty"
                        >
                          Aucun point fort
                          confirmé pour le
                          moment.
                        </p>
                      )}
                    </div>

                    <div>
                      <h4>
                        À améliorer
                      </h4>

                      {weakAreas.length >
                      0 ? (
                        <ul
                          className="profile-tag-list"
                        >
                          {weakAreas
                            .slice(
                              0,
                              5
                            )
                            .map(
                              (
                                item,
                                index
                              ) => (
                                <li
                                  className="profile-tag profile-tag-weak"
                                  key={
                                    `weak-${index}-${profileItemLabel(item)}`
                                  }
                                >
                                  <span>
                                    {profileItemLabel(
                                      item
                                    )}
                                  </span>

                                  {profileItemMastery(
                                    item
                                  ) !==
                                    null && (
                                    <strong>
                                      {profileItemMastery(
                                        item
                                      )}
                                      %
                                    </strong>
                                  )}
                                </li>
                              )
                            )}
                        </ul>
                      ) : (
                        <p
                          className="profile-empty"
                        >
                          Aucun point faible
                          détecté actuellement.
                        </p>
                      )}
                    </div>
                  </div>
                </section>
              </div>

              <div
                className="gemini-guidance"
              >
                <div>
                  <p
                    className="card-label"
                  >
                    Gemini
                  </p>

                  <h3>
                    Conseil personnalisé
                  </h3>
                </div>

                <span
                  className={
                    orientation.ai_status ===
                    "success"
                      ? "gemini-status gemini-status-success"
                      : "gemini-status"
                  }
                >
                  {orientation.ai_status ||
                    "fallback"}
                </span>

                <p>
                  {orientation.ai_guidance ||
                    orientation.message ||
                    "Pas encore assez de résultats pour produire une recommandation."}
                </p>
              </div>

              <section
                className="profile-revision-section"
              >
                <div
                  className="profile-subcard-header"
                >
                  <div>
                    <p
                      className="card-label"
                    >
                      Plan personnalisé
                    </p>

                    <h3>
                      Priorités de révision
                    </h3>
                  </div>
                </div>

                <div
                  className="revision-list"
                >
                  {(
                    orientation.revision_plan ||
                    []
                  ).map(
                    (
                      item
                    ) => (
                      <article
                        className="revision-item"
                        key={
                          `${item.rank}-${item.subject}-${item.concept}`
                        }
                      >
                        <div
                          className="revision-item-header"
                        >
                          <div>
                            <span>
                              Priorité
                              {" #"}
                              {item.rank}
                            </span>

                            <h3>
                              {item.subject}
                            </h3>
                          </div>

                          <strong>
                            {item.current_mastery}
                            %
                          </strong>
                        </div>

                        <p>
                          {item.concept}
                        </p>

                        <div
                          className="revision-progress"
                        >
                          <span
                            style={{
                              width:
                                `${Math.max(
                                  0,
                                  Math.min(
                                    100,
                                    Number(
                                      item.current_mastery
                                    ) ||
                                    0
                                  )
                                )}%`,
                            }}
                          />
                        </div>

                        <ul>
                          {(
                            item.actions ||
                            []
                          ).map(
                            (
                              action
                            ) => (
                              <li
                                key={
                                  action
                                }
                              >
                                {action.replaceAll(
                                  "_",
                                  " "
                                )}
                              </li>
                            )
                          )}
                        </ul>

                        <p
                          className="revision-recommendation"
                        >
                          {item.recommendation}
                        </p>
                      </article>
                    )
                  )}
                </div>
              </section>
            </>
          )}
        </div>
      )}
    </section>
  );
}

export default LearningTools;
