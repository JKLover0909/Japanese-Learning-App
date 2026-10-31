import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import type { ChapterTestResult } from '../api/types';
import { api, errorMessage } from '../api/client';
import { LoadError } from '../components/LoadError';
import { PageStatus } from '../components/PageStatus';
import { OPTION_LETTERS } from './ChapterTestPage';

function verdict(correct: number, total: number): string {
  const ratio = total ? correct / total : 0;
  if (ratio >= 0.9) return 'Xuất sắc';
  if (ratio >= 0.7) return 'Làm tốt lắm';
  if (ratio >= 0.5) return 'Khá rồi đấy';
  return 'Cố lên nhé';
}

export function ChapterTestResultPage() {
  const { testId = '' } = useParams();
  const navigate = useNavigate();
  const [result, setResult] = useState<ChapterTestResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [starting, setStarting] = useState(false);
  const [showAll, setShowAll] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError('');
    try {
      setResult(await api.getChapterTestResult(testId, signal));
    } catch (caught) {
      if (signal?.aborted) return;
      setError(errorMessage(caught));
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, [testId]);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => {
      controller.abort();
      audioRef.current?.pause();
    };
  }, [load]);

  function play(url: string | null) {
    if (!url) return;
    audioRef.current?.pause();
    const audio = new Audio(url);
    audioRef.current = audio;
    void audio.play().catch(() => undefined);
  }

  async function startAgain() {
    if (!result || starting) return;
    setStarting(true);
    try {
      const test = await api.createChapterTest(result.test.chapter);
      navigate(`/tests/${encodeURIComponent(test.id)}`);
    } catch (caught) {
      setError(errorMessage(caught));
      setStarting(false);
    }
  }

  if (loading) return <PageStatus label="Đang chấm bài…" />;
  if (error && !result) return <LoadError message={error} onRetry={() => void load()} />;
  if (!result) return <LoadError message="Không tìm thấy kết quả bài kiểm tra." />;

  const { test, parts, questions } = result;
  const correct = test.correct_count ?? 0;
  const wrong = questions.filter((question) => !question.is_correct);
  const listed = showAll ? questions : wrong;

  return (
    <div className="page-stack summary-page">
      <section className="summary-hero">
        <div className="summary-confetti" aria-hidden="true">＊</div>
        <p className="eyebrow">KẾT QUẢ KIỂM TRA CUỐI CHƯƠNG</p>
        <h1>{verdict(correct, test.total)}<span className="welcome-period">.</span></h1>
        <p className="summary-subtitle">{test.title} · {new Date(test.completed_at ?? test.created_at).toLocaleDateString('vi-VN', { day: 'numeric', month: 'long', year: 'numeric' })}</p>
        <div className="score-display">
          <span className="score-large">{correct}</span><span className="score-divider">/</span><span className="score-denominator">{test.total}</span>
          <span className="score-caption">câu đúng</span>
        </div>
        <ul className="part-scores" aria-label="Điểm theo phần">
          {parts.map((part) => (
            <li key={part.part}><span>{part.label}</span><strong>{part.correct}/{part.total}</strong></li>
          ))}
        </ul>
        {error && <p className="form-error" role="alert">{error}</p>}
        <div className="button-row summary-actions">
          <button className="button button-primary" type="button" disabled={starting} onClick={() => void startAgain()}>{starting ? 'Đang tạo đề mới…' : 'Làm đề mới'} <span aria-hidden="true">→</span></button>
          <Link className="button button-secondary" to="/">Về trang chính</Link>
        </div>
      </section>

      <section className="section-block" aria-labelledby="review-heading">
        <div className="section-heading">
          <div><p className="eyebrow">NHÌN LẠI</p><h2 id="review-heading">{showAll ? 'Tất cả các câu' : 'Các câu chọn sai'}</h2></div>
          <button className="button button-quiet button-small" type="button" onClick={() => setShowAll((value) => !value)}>
            {showAll ? 'Chỉ xem câu sai' : 'Xem cả 30 câu'}
          </button>
        </div>
        {listed.length === 0 ? (
          <div className="state-card state-card-positive"><h3>Không sai câu nào!</h3><p>Bạn đã nghe đúng toàn bộ đề này.</p></div>
        ) : (
          <ol className="review-list">
            {listed.map((question) => (
              <li key={question.position} className={`review-card${question.is_correct ? ' is-correct' : ' is-wrong'}`}>
                <div className="review-head">
                  <span className="review-number">Câu {question.position + 1}</span>
                  <span className="review-part">{question.part_label}</span>
                  <button className="button button-quiet button-small" type="button" onClick={() => play(question.audio_url)} disabled={!question.audio_url}>
                    <span aria-hidden="true">▶</span> Nghe lại
                  </button>
                </div>
                <ul className="review-options">
                  {question.options.map((option, optionIndex) => {
                    const isAnswer = optionIndex === question.answer_index;
                    const isChoice = optionIndex === question.choice;
                    const state = isAnswer ? ' is-answer' : isChoice ? ' is-choice' : '';
                    return (
                      <li key={optionIndex} className={`review-option${state}`}>
                        <span className="option-letter" aria-hidden="true">{OPTION_LETTERS[optionIndex]}</span>
                        <span lang="ja">{option}</span>
                        {isAnswer && <span className="review-tag">Đáp án</span>}
                        {isChoice && !isAnswer && <span className="review-tag">Bạn chọn</span>}
                      </li>
                    );
                  })}
                </ul>
                {question.choice === null && <p className="review-note">Bạn chưa chọn câu này.</p>}
                {question.meaning && <p className="review-note">Nghĩa: {question.meaning}</p>}
              </li>
            ))}
          </ol>
        )}
        {test.audio_credit && <p className="audio-credit">Giọng đọc: {test.audio_credit}</p>}
      </section>
    </div>
  );
}
