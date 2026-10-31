import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom';
import type { ChapterTestDetail } from '../api/types';
import { api, errorMessage } from '../api/client';
import { LoadError } from '../components/LoadError';
import { PageStatus } from '../components/PageStatus';

export const OPTION_LETTERS = ['a', 'b', 'c', 'd'] as const;
/** After a first choice, move on once the learner has seen their circle. */
export const NEXT_QUESTION_DELAY_MS = 450;

export function ChapterTestPage() {
  const { testId = '' } = useParams();
  const navigate = useNavigate();
  const [test, setTest] = useState<ChapterTestDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [error, setError] = useState('');
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [needsTap, setNeedsTap] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const audioRef = useRef<HTMLAudioElement>(null);
  const advanceTimer = useRef<number | null>(null);
  // Choices are saved one after another so the server keeps the learner's last choice.
  const saves = useRef<Promise<unknown>>(Promise.resolve());

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setLoadError('');
    try {
      const result = await api.getChapterTest(testId, signal);
      setTest(result);
      const firstOpen = result.questions.findIndex((question) => question.choice === null);
      setIndex(firstOpen === -1 ? 0 : firstOpen);
    } catch (caught) {
      if (signal?.aborted) return;
      setLoadError(errorMessage(caught));
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, [testId]);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  const cancelAdvance = useCallback(() => {
    if (advanceTimer.current !== null) {
      window.clearTimeout(advanceTimer.current);
      advanceTimer.current = null;
    }
  }, []);
  useEffect(() => cancelAdvance, [cancelAdvance]);

  useEffect(() => {
    const listener = (event: KeyboardEvent) => keyHandler.current(event);
    window.addEventListener('keydown', listener);
    return () => window.removeEventListener('keydown', listener);
  }, []);

  const play = useCallback(() => {
    const audio = audioRef.current;
    if (!audio) return;
    audio.currentTime = 0;
    setNeedsTap(false);
    // Browsers block sound until the page has been tapped; then the play button takes over.
    void Promise.resolve(audio.play()).catch(() => setNeedsTap(true));
  }, []);

  const question = test?.questions[index];
  const audioUrl = question?.audio_url ?? null;
  useEffect(() => {
    if (audioUrl && test?.status === 'active') play();
  }, [audioUrl, index, play, test?.status]);

  function goTo(next: number) {
    if (!test) return;
    cancelAdvance();
    setConfirming(false);
    setIndex(Math.max(0, Math.min(test.total - 1, next)));
  }

  function choose(choice: number) {
    if (!test || !question || submitting) return;
    const position = question.position;
    const previous = question.choice;
    cancelAdvance();
    setError('');
    setConfirming(false);
    setTest((current) => current && {
      ...current,
      answered_count: current.answered_count + (previous === null ? 1 : 0),
      questions: current.questions.map((item) => item.position === position ? { ...item, choice } : item),
    });
    saves.current = saves.current.then(() => api.answerChapterTest(test.id, position, choice)).then(
      (saved) => setTest((current) => current && { ...current, answered_count: saved.answered_count }),
      (caught: unknown) => {
        setError(errorMessage(caught));
        setTest((current) => current && {
          ...current,
          answered_count: current.answered_count - (previous === null ? 1 : 0),
          questions: current.questions.map((item) => item.position === position ? { ...item, choice: previous } : item),
        });
      },
    );
    if (previous === null && index < test.total - 1) {
      advanceTimer.current = window.setTimeout(() => {
        advanceTimer.current = null;
        setIndex((current) => current === index ? current + 1 : current);
      }, NEXT_QUESTION_DELAY_MS);
    }
  }

  async function submit() {
    if (!test || submitting) return;
    const open = test.questions.filter((item) => item.choice === null).length;
    if (open > 0 && !confirming) {
      setConfirming(true);
      return;
    }
    cancelAdvance();
    setSubmitting(true);
    setError('');
    try {
      await saves.current;
      await api.submitChapterTest(test.id);
      navigate(`/tests/${encodeURIComponent(test.id)}/result`);
    } catch (caught) {
      setError(errorMessage(caught));
      setSubmitting(false);
    }
  }

  function handleKeyDown(event: KeyboardEvent) {
    if (event.altKey || event.ctrlKey || event.metaKey || event.repeat) return;
    const key = event.key.toLowerCase();
    const letter = OPTION_LETTERS.indexOf(key as (typeof OPTION_LETTERS)[number]);
    const digit = /^[1-4]$/.test(key) ? Number(key) : 0;
    if (letter !== -1 || digit) {
      event.preventDefault();
      choose(letter !== -1 ? letter : digit - 1);
    } else if (key === 'r') {
      event.preventDefault();
      play();
    } else if (key === 'arrowright') {
      goTo(index + 1);
    } else if (key === 'arrowleft') {
      goTo(index - 1);
    }
  }
  const keyHandler = useRef(handleKeyDown);
  keyHandler.current = handleKeyDown;

  if (loading) return <PageStatus label="Đang mở bài kiểm tra…" />;
  if (loadError || !test) return <LoadError message={loadError || 'Không tìm thấy bài kiểm tra.'} onRetry={() => void load()} />;
  if (test.status === 'completed') return <Navigate to={`/tests/${encodeURIComponent(test.id)}/result`} replace />;
  if (test.status === 'abandoned' || !question) {
    return (
      <div className="state-card">
        <h2>Bài kiểm tra này đã được thay bằng đề mới</h2>
        <p>Mỗi chương chỉ giữ một bài đang làm. Hãy quay lại trang chính để làm tiếp.</p>
        <Link className="button button-primary" to="/">Về trang chính</Link>
      </div>
    );
  }

  const open = test.total - test.answered_count;
  const isLast = index === test.total - 1;
  const progressPercent = test.total ? Math.round((test.answered_count / test.total) * 100) : 0;

  return (
    <div className="practice-page test-page">
      <div className="practice-topbar">
        <Link className="back-link" to="/" aria-label="Tạm dừng, về trang chính">← <span>Tạm dừng</span></Link>
        <div className="practice-lesson-name">{test.title}</div>
        <span className="practice-score">{test.answered_count}/{test.total} đã chọn</span>
      </div>
      <div className="practice-progress-row">
        <span>Câu <strong>{index + 1}</strong><span className="progress-muted"> / {test.total}</span></span>
        <span>{question.part_label}</span>
      </div>
      <div className="practice-progress-track" role="progressbar" aria-label="Số câu đã chọn" aria-valuemin={0} aria-valuemax={test.total} aria-valuenow={test.answered_count}>
        <span style={{ width: `${progressPercent}%` }} />
      </div>

      <section className="question-card test-question" aria-labelledby="test-question-heading">
        <div className="question-overline">
          <span className="eyebrow" id="test-question-heading">NGHE VÀ CHỌN ĐÁP ÁN ĐÚNG · CÂU {index + 1}</span>
        </div>
        <div className="listen-row">
          <audio
            ref={audioRef}
            src={audioUrl ?? undefined}
            preload="auto"
            onPlay={() => setPlaying(true)}
            onPause={() => setPlaying(false)}
            onEnded={() => setPlaying(false)}
          />
          <button className={`listen-button${playing ? ' is-playing' : ''}`} type="button" onClick={play} disabled={!audioUrl} aria-label={needsTap ? 'Nghe câu hỏi' : 'Nghe lại câu hỏi'}>
            <span className="listen-icon" aria-hidden="true">{playing ? '♪' : '▶'}</span>
            <span>{playing ? 'Đang phát…' : needsTap ? 'Bấm để nghe' : 'Nghe lại'}</span>
          </button>
        </div>
        <div className="option-grid" role="radiogroup" aria-label={`Lựa chọn cho câu ${index + 1}`}>
          {question.options.map((option, optionIndex) => {
            const selected = question.choice === optionIndex;
            return (
              <button
                key={`${question.position}-${optionIndex}`}
                className={`option-button${selected ? ' is-selected' : ''}`}
                type="button"
                role="radio"
                aria-checked={selected}
                disabled={submitting}
                onClick={() => choose(optionIndex)}
              >
                <span className="option-letter" aria-hidden="true">{OPTION_LETTERS[optionIndex]}</span>
                <span className="option-text" lang="ja">{option}</span>
              </button>
            );
          })}
        </div>
        {error && <div className="form-error" role="alert">{error}</div>}
        <div className="test-nav">
          <button className="button button-quiet" type="button" onClick={() => goTo(index - 1)} disabled={index === 0}>← Câu trước</button>
          {isLast
            ? <button className="button button-primary" type="button" onClick={() => void submit()} disabled={submitting}>{submitting ? 'Đang chấm…' : 'Nộp bài'}</button>
            : <button className="button button-secondary" type="button" onClick={() => goTo(index + 1)}>Câu sau →</button>}
        </div>
      </section>

      <section className="answer-sheet" aria-labelledby="answer-sheet-heading">
        <div className="answer-sheet-heading">
          <h2 id="answer-sheet-heading">Phiếu trả lời</h2>
          <span>{open > 0 ? `Còn ${open} câu chưa chọn` : 'Đã chọn đủ 30 câu'}</span>
        </div>
        <ol className="answer-sheet-grid">
          {test.questions.map((item, itemIndex) => (
            <li key={item.position}>
              <button
                type="button"
                className={`sheet-cell${item.choice !== null ? ' is-answered' : ''}${itemIndex === index ? ' is-current' : ''}`}
                aria-current={itemIndex === index ? 'step' : undefined}
                aria-label={`Câu ${itemIndex + 1}${item.choice !== null ? `, đã chọn ${OPTION_LETTERS[item.choice] ?? ''}` : ', chưa chọn'}`}
                onClick={() => goTo(itemIndex)}
              >
                <span>{itemIndex + 1}</span>
                <small aria-hidden="true">{item.choice !== null ? OPTION_LETTERS[item.choice] : '·'}</small>
              </button>
            </li>
          ))}
        </ol>
        {confirming && (
          <p className="inline-alert" role="alert">Còn {open} câu chưa chọn, các câu này sẽ tính là sai. Bấm “Nộp bài” lần nữa để nộp.</p>
        )}
        <div className="button-row answer-sheet-actions">
          <button className="button button-primary" type="button" onClick={() => void submit()} disabled={submitting}>{submitting ? 'Đang chấm…' : confirming ? 'Vẫn nộp bài' : 'Nộp bài'}</button>
        </div>
        <p className="practice-hint">Phím tắt: a–d hoặc 1–4 để chọn · R để nghe lại · ← → để chuyển câu</p>
        {test.audio_credit && <p className="audio-credit">Giọng đọc: {test.audio_credit}</p>}
      </section>
    </div>
  );
}
