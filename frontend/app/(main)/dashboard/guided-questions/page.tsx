"use client";

import { useEffect, useMemo, useState } from "react";
import "./guided-questions.css";

type GuidedQuestion = {
  id?: string;
  key?: string;
  question?: string;
  text?: string;
  options?: string[];
  type?: string;
};

type RecommendationResult =
  | string
  | {
      summary?: string;
      recommendation?: string;
      setup?: Record<string, unknown>;
      [key: string]: unknown;
    };

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

function getQuestionKey(question: GuidedQuestion | undefined, index: number) {
  return String(question?.key || question?.id || `question_${index + 1}`);
}

function getErrorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

export default function GuidedQuestionsPage() {
  const [questions, setQuestions] = useState<GuidedQuestion[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [step, setStep] = useState(0);
  const [prompt, setPrompt] = useState("");
  const [recommendation, setRecommendation] = useState<RecommendationResult | null>(null);
  const [rawOutput, setRawOutput] = useState("");
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    async function loadQuestions() {
      try {
        setLoading(true);
        setError("");

        const res = await fetch(`${API_BASE}/api/ai-onboarding/questions`);

        if (!res.ok) {
          throw new Error("Failed to load guided questions.");
        }

        const data = await res.json();
        setQuestions(Array.isArray(data.questions) ? data.questions : []);
      } catch (err: unknown) {
        setError(getErrorMessage(err, "Failed to load guided questions."));
      } finally {
        setLoading(false);
      }
    }

    loadQuestions();
  }, []);

  const currentQuestion = questions[step];

  const questionKey = useMemo(() => {
    return getQuestionKey(currentQuestion, step);
  }, [currentQuestion, step]);

  const questionText = useMemo(() => {
    if (!currentQuestion) return "";
    return (
      currentQuestion.question || currentQuestion.text || `Question ${step + 1}`
    );
  }, [currentQuestion, step]);

  const isReviewStep = questions.length > 0 && step >= questions.length;
  const hasResult = recommendation !== null;
  const progress =
    questions.length > 0 ? Math.min(((step + 1) / questions.length) * 100, 100) : 0;
  const progressPercent = Math.round(progress);
  const selectedAnswer = answers[questionKey] || "";
  const canContinue = selectedAnswer.trim().length > 0;

  function updateAnswer(value: string) {
    setAnswers((prev) => ({
      ...prev,
      [questionKey]: value,
    }));
  }

  function goNext() {
    if (!canContinue) return;
    setStep((prev) => prev + 1);
  }

  function goBack() {
    setStep((prev) => Math.max(prev - 1, 0));
  }

  async function buildPromptOnly() {
    try {
      setError("");

      const res = await fetch(`${API_BASE}/api/ai-onboarding/build-prompt`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ answers }),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data?.detail || "Failed to build prompt.");
      }

      setPrompt(data.prompt || "");
    } catch (err: unknown) {
      setError(getErrorMessage(err, "Failed to build prompt."));
    }
  }

  async function generateRecommendations() {
    try {
      setGenerating(true);
      setError("");

      let promptText = prompt;

      if (!promptText) {
        const promptRes = await fetch(`${API_BASE}/api/ai-onboarding/build-prompt`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ answers }),
        });

        const promptData = await promptRes.json();

        if (!promptRes.ok) {
          throw new Error(promptData?.detail || "Failed to build prompt.");
        }

        promptText = promptData.prompt || "";
        setPrompt(promptText);
      }

      const res = await fetch(`${API_BASE}/api/ai-onboarding/generate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ prompt: promptText }),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data?.detail || "Failed to generate recommendations.");
      }

      setRecommendation(data.recommendation || data.raw_output || "Generated.");
      setRawOutput(data.raw_output || "");
    } catch (err: unknown) {
      setError(getErrorMessage(err, "Failed to generate recommendations."));
    } finally {
      setGenerating(false);
    }
  }

  if (loading) {
    return (
      <main className="guided-page">
        <div className="guided-loading">Loading guided questions...</div>
      </main>
    );
  }

  return (
    <main className="guided-page">
      <section className="guided-hero">
        <div>
          <span className="guided-eyebrow">AI Onboarding</span>
          <h1>Build your cloud recommendation profile</h1>
          <p>
            Answer one question at a time. Your answers are converted into a structured
            prompt, then sent to the AI recommendation engine.
          </p>
        </div>

        <div className="guided-hero-card">
          <span>Current Flow</span>
          <strong>Guided setup</strong>
          <p>For AWS accounts with less than 7 days of usage data.</p>
        </div>
      </section>

      <section className="guided-wizard-card">
        {error && <div className="guided-api-error">{error}</div>}

        {!hasResult && !generating && (
          <>
            <div className="guided-progress-top">
              <div>
                <span className="guided-step-label">
                  {isReviewStep ? "Review" : `Step ${step + 1} of ${questions.length}`}
                </span>
                <h2>
                  {isReviewStep
                    ? "Review your answers"
                    : "Answer the question below"}
                </h2>
              </div>

              <div
                className="guided-progress-number"
                data-progress={isReviewStep ? "Done" : `${progressPercent}%`}
              >
                {isReviewStep ? "✓" : step + 1}
              </div>
            </div>

            {!isReviewStep && (
              <div className="guided-progress-track">
                <div
                  className="guided-progress-fill"
                  style={{ width: `${progress}%` }}
                />
              </div>
            )}
          </>
        )}

        {generating && (
          <div className="guided-generating">
            <div className="guided-spinner" />
            <h3>Generating recommendations...</h3>
            <p>Please wait while the AI optimizer prepares the result.</p>
          </div>
        )}

        {!generating && !isReviewStep && !hasResult && currentQuestion && (
          <div className="guided-question-screen">
            <h3>{questionText}</h3>

            {currentQuestion.options && currentQuestion.options.length > 0 ? (
              <div className="guided-options">
                {currentQuestion.options.map((option) => {
                  const selected = selectedAnswer === option;

                  return (
                    <button
                      key={option}
                      type="button"
                      className={`guided-option ${selected ? "selected" : ""}`}
                      onClick={() => updateAnswer(option)}
                    >
                      <span className="guided-radio">{selected && <span />}</span>
                      {option}
                    </button>
                  );
                })}
              </div>
            ) : (
              <textarea
                className="guided-textarea"
                placeholder="Write your answer here..."
                value={selectedAnswer}
                onChange={(event) => updateAnswer(event.target.value)}
              />
            )}

            <div className="guided-actions">
              <button
                type="button"
                className="guided-secondary-btn"
                onClick={goBack}
                disabled={step === 0}
              >
                Back
              </button>

              <button
                type="button"
                className="guided-primary-btn"
                onClick={goNext}
                disabled={!canContinue}
              >
                {step === questions.length - 1 ? "Review Answers" : "Next ->"}
              </button>
            </div>
          </div>
        )}

        {!generating && isReviewStep && !hasResult && (
          <div className="guided-review">
            <div className="guided-flow-note">
              <strong>Review before generating</strong>
              <span>
                Generate the prompt first, then use it to create AI recommendations.
              </span>
            </div>

            {questions.map((question, index) => {
              const key = getQuestionKey(question, index);
              const text = question.question || question.text || `Question ${index + 1}`;

              return (
                <div className="guided-review-row" key={key}>
                  <div className="guided-review-index">{index + 1}</div>
                  <div>
                    <h4>{text}</h4>
                    <p>{answers[key] || "No answer"}</p>
                  </div>
                </div>
              );
            })}

            {prompt && (
              <div className="guided-prompt-card">
                <div className="guided-flow-note success">
                  <strong>Prompt generated</strong>
                  <span>You can now generate recommendations.</span>
                </div>

                <pre className="guided-prompt-preview">{prompt}</pre>
              </div>
            )}

            <div className="guided-actions">
              <button
                type="button"
                className="guided-secondary-btn"
                onClick={goBack}
              >
                Back
              </button>

              {!prompt ? (
                <button
                  type="button"
                  className="guided-primary-btn"
                  onClick={buildPromptOnly}
                >
                  Generate Prompt
                </button>
              ) : (
                <button
                  type="button"
                  className="guided-primary-btn"
                  onClick={generateRecommendations}
                >
                  Generate Recommendations
                </button>
              )}
            </div>
          </div>
        )}

        {!generating && hasResult && (
          <div className="guided-result">
            <div className="guided-flow-note success">
              <strong>Recommendations generated</strong>
              <span>Your AI optimization result is ready.</span>
            </div>

            <div className="guided-result-section">
              <h3>Recommendation</h3>
              <p className="guided-explanation">
                {typeof recommendation === "string"
                  ? recommendation
                  : recommendation?.summary ||
                    recommendation?.recommendation ||
                    "AI recommendations generated successfully."}
              </p>
            </div>

            {typeof recommendation === "object" && recommendation?.setup && (
              <div className="guided-result-section">
                <h3>Suggested Setup</h3>

                <div className="guided-setup-grid">
                  {Object.entries(recommendation.setup).map(([key, value]) => (
                    <div className="guided-setup-card" key={key}>
                      <span>{key.replaceAll("_", " ")}</span>
                      <p>{String(value)}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <details className="guided-details">
              <summary>Raw output</summary>
              <pre>
                {rawOutput ||
                  (typeof recommendation === "object"
                    ? JSON.stringify(recommendation, null, 2)
                    : recommendation)}
              </pre>
            </details>

            <div className="guided-actions">
              <button
                type="button"
                className="guided-secondary-btn"
                onClick={() => {
                  setStep(0);
                  setAnswers({});
                  setPrompt("");
                  setRecommendation(null);
                  setRawOutput("");
                  setError("");
                }}
              >
                Start Again
              </button>
            </div>
          </div>
        )}
      </section>
    </main>
  );
}
