import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { FormEvent, KeyboardEvent } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api, errorMessage } from '../api/client';
import type { AnswerResult, Question, SessionDetail } from '../api/types';
import { LoadError } from '../components/LoadError';
import { PageStatus } from '../components/PageStatus';

interface Feedback {
  result: AnswerResult;
}

export function PracticePage() {
  const { sessionId = '' } = useParams();
  const navigate = useNavigate();
  const [session, setSession] = useState<SessionDetail | null>(null);
  const [currentPosition, setCurrentPosition] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [answer, setAnswer] = useState('');
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const nextButtonRef = useRef<HTMLButtonElement>(null);
  const busyRef = useRef(false);
  const advanceTimerRef = useRef<number | null>(null);

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError('');
    try {
      const result = await api.getSession(sessionId, signal);
      if (result.status === 'completed') {
        navigate(`/sessions/${encodeURIComponent(sessionId)}/summary`, { replace: true });
        return;
      }
      setSession(result);
      const next = result.questions.find((question) => !question.answered);
      if (!next) {
        navigate(`/sessions/${encodeURIComponent(sessionId)}/summary`, { replace: true });
        return;
      }
      setCurrentPosition(next.position);
      setFeedback(null);
      setAnswer('');
    } catch (caught) {
      if (signal?.aborted) return;
      setError(errorMessage(caught));
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, [navigate, sessionId]);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => {
      controller.abort();
      if (advanceTimerRef.current !== null) window.clearTimeout(advanceTimerRef.current);
    };
  }, [load]);

  const current: Question | undefined = useMemo(
    () => session?.questions.find((question) => question.position === currentPosition),
    [session, currentPosition],
  );

  async function submitAnswer(value: string) {
    if (!session || !current || busyRef.current) return;
    busyRef.current = true;
    setSubmitting(true);
    setError('');
    try {
      const result = await api.submitAnswer(session.id, current.position, value);
      setFeedback({ result });
      setSession((previous) => {
        if (!previous) return previous;
        return {
          ...previous,
          answered_count: result.session.answered_count,
          correct_count: result.session.correct_count,
          status: result.session.status,
        };
      });
      window.requestAnimationFrame(() => nextButtonRef.current?.focus());
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      busyRef.current = false;
      setSubmitting(false);
    }
  }

  const advance = useCallback(() => {
    if (advanceTimerRef.current !== null) {
      window.clearTimeout(advanceTimerRef.current);
      advanceTimerRef.current = null;
    }
    if (!session || !feedback || busyRef.current) return;
    const next = session.questions.find((question) => question.position > (current?.position ?? -1) && !question.answered);
    if (!next) {
      navigate(`/sessions/${encodeURIComponent(session.id)}/summary`, { replace: true });
      return;
    }
    setCurrentPosition(next.position);
    setFeedback(null);
    setAnswer('');
    window.requestAnimationFrame(() => inputRef.current?.focus());
  }, [session, feedback, current, navigate]);

  // Only a correct answer moves on by itself; a miss stays until the learner presses the next button or Enter.
  useEffect(() => {
    if (!feedback?.result.is_correct) return;
    advanceTimerRef.current = window.setTimeout(advance, 700);
    return () => {
      if (advanceTimerRef.current !== null) window.clearTimeout(advanceTimerRef.current);
      advanceTimerRef.current = null;
    };
  }, [feedback, advance]);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (feedback) {
      advance();
      return;
    }
    const trimmed = answer.trim();
    if (!trimmed || submitting) return;
    void submitAnswer(trimmed);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Enter' && feedback) {
      event.preventDefault();
      advance();
    }
  }

  if (loading) return <PageStatus label="Đang mở lượt luyện tập…" />;
  if (error && !session) return <LoadError message={error} onRetry={() => void load()} />;
  if (!session || !current) return <PageStatus label="Đang chuyển đến phần tổng kết…" />;

  const completed = session.answered_count;
  const displayPosition = current.position + 1;
  const progressPercent = session.total > 0 ? (completed / session.total) * 100 : 0;
  const lastAnswer = !!feedback && completed >= session.total;

  return (
    <div className="practice-page">
      <div className="practice-topbar">
        <Link className="back-link" to={`/lessons/${encodeURIComponent(session.lesson.slug)}`} aria-label="Thoát về bài học">← <span>Thoát</span></Link>
        <div className="practice-lesson-name">{session.lesson.title}</div>
        <span className="practice-score"><span className="score-dot" aria-hidden="true" />{session.correct_count} đúng</span>
      </div>
      <div className="practice-progress-row">
        <span>Câu <strong>{displayPosition}</strong><span className="progress-muted"> / {session.total}</span></span>
        <span>{session.answered_count} / {session.total} hoàn thành</span>
      </div>
      <div className="practice-progress-track" role="progressbar" aria-label="Tiến độ lượt luyện tập" aria-valuemin={0} aria-valuemax={session.total} aria-valuenow={session.answered_count}>
        <span style={{ width: `${progressPercent}%` }} />
      </div>

      <section className={`question-card${feedback ? feedback.result.is_correct ? ' question-correct' : ' question-wrong' : ''}`} aria-labelledby="question-prompt">
        <div className="question-overline">
          <span className="eyebrow">HÃY ĐỌC THÀNH TIẾNG</span>
          {current.is_focus && <span className="focus-badge"><span aria-hidden="true">↻</span> Ôn lại</span>}
        </div>
        <div className="question-content">
          <p className="question-prompt" id="question-prompt" lang="ja">{current.prompt}</p>
          {current.meaning && <p className="question-meaning">{current.meaning}</p>}
        </div>
        <form className="answer-form" onSubmit={handleSubmit}>
          {error && <div className="form-error" role="alert">{error}</div>}
          <label className="field-label" htmlFor="answer-input">Cách đọc romaji
            <input
              ref={inputRef}
              id="answer-input"
              name="answer"
              type="text"
              lang="en"
              autoComplete="off"
              autoCorrect="off"
              autoCapitalize="off"
              spellCheck={false}
              enterKeyHint={feedback ? 'next' : 'done'}
              inputMode="text"
              required={!feedback}
              maxLength={200}
              disabled={!!feedback || submitting}
              autoFocus
              value={answer}
              onChange={(event) => setAnswer(event.target.value)}
              onKeyDown={handleKeyDown}
              aria-describedby={feedback ? 'answer-feedback' : undefined}
            />
          </label>
          <button ref={nextButtonRef} className="button button-primary button-wide answer-submit" type="submit" disabled={submitting || (!feedback && !answer.trim())}>
            {submitting ? 'Đang kiểm tra…' : feedback ? lastAnswer ? 'Xem kết quả' : 'Câu tiếp theo' : 'Kiểm tra'}
            {!submitting && <span aria-hidden="true">→</span>}
          </button>
          {!feedback && <button className="dont-know-button" type="button" disabled={submitting} onClick={() => void submitAnswer('?')}>Không biết</button>}
        </form>
        <div className={`answer-feedback${feedback ? feedback.result.is_correct ? ' feedback-correct' : ' feedback-wrong' : ''}`} id="answer-feedback" aria-live="polite" aria-atomic="true">
          {feedback && <>
            <span className="feedback-icon" aria-hidden="true">{feedback.result.is_correct ? '✓' : '×'}</span>
            <div><strong>{feedback.result.is_correct ? 'Chính xác!' : 'Chưa đúng rồi'}</strong>
              {!feedback.result.is_correct && <p>{feedback.result.expected_romaji.join(' · ')} <span lang="ja">{feedback.result.expected_readings.join(' · ')}</span></p>}
            </div>
          </>}
        </div>
      </section>
      <p className="practice-hint">Nhấn <kbd>Enter</kbd> để {feedback ? 'sang câu tiếp theo' : 'kiểm tra câu trả lời'}</p>
    </div>
  );
}
