import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import type { SessionSummary } from '../api/types';
import { api, errorMessage } from '../api/client';
import { LoadError } from '../components/LoadError';
import { PageStatus } from '../components/PageStatus';

export function SummaryPage() {
  const { id = '' } = useParams();
  const navigate = useNavigate();
  const [summary, setSummary] = useState<SessionSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [starting, setStarting] = useState(false);

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError('');
    try {
      const result = await api.getSessionSummary(id, signal);
      setSummary(result);
    } catch (caught) {
      if (signal?.aborted) return;
      setError(errorMessage(caught));
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  async function startAgain() {
    if (!summary || starting) return;
    setStarting(true);
    try {
      const session = await api.createSession(summary.session.lesson.slug);
      navigate(`/practice/${encodeURIComponent(session.id)}`);
    } catch (caught) {
      setError(errorMessage(caught));
      setStarting(false);
    }
  }

  if (loading) return <PageStatus label="Đang tổng hợp kết quả…" />;
  if (error && !summary) return <LoadError message={error} onRetry={() => void load()} />;
  if (!summary) return <LoadError message="Không tìm thấy kết quả lượt học." />;

  const { session, wrong, next_focus: nextFocus } = summary;
  const accuracy = session.total ? Math.round((session.correct_count / session.total) * 100) : 0;

  return (
    <div className="page-stack summary-page">
      <section className="summary-hero">
        <div className="summary-confetti" aria-hidden="true">＊</div>
        <p className="eyebrow">HOÀN THÀNH MỘT CHẶNG</p>
        <h1>Làm tốt lắm<span className="welcome-period">.</span></h1>
        <p className="summary-subtitle">{session.lesson.title} · {new Date(session.created_at).toLocaleDateString('vi-VN', { day: 'numeric', month: 'long', year: 'numeric' })}</p>
        <div className="score-display">
          <span className="score-large">{session.correct_count}</span><span className="score-divider">/</span><span className="score-denominator">{session.total}</span>
          <span className="score-caption">câu trả lời đúng</span>
        </div>
        <div className="summary-stats">
          <div><strong>{accuracy}%</strong><span>Chính xác</span></div>
          <div><strong>{wrong.length}</strong><span>Câu cần ôn</span></div>
          <div><strong>{session.focus_count}</strong><span>Câu ôn lại</span></div>
        </div>
        <div className="button-row summary-actions">
          <button className="button button-primary" type="button" disabled={starting} onClick={() => void startAgain()}>{starting ? 'Đang tạo lượt mới…' : 'Luyện tiếp'} <span aria-hidden="true">→</span></button>
          <Link className="button button-secondary" to="/">Về trang chính</Link>
        </div>
      </section>

      <section className="section-block" aria-labelledby="wrong-heading">
        <div className="section-heading"><div><p className="eyebrow">NHÌN LẠI MỘT CHÚT</p><h2 id="wrong-heading">Câu trả lời cần ôn <span className="heading-count">{wrong.length}</span></h2></div></div>
        {wrong.length === 0 ? <div className="state-card state-card-positive"><span className="state-icon" aria-hidden="true">✓</span><p>Không có câu nào sai. Bạn làm rất tốt!</p></div> : (
          <div className="wrong-list">
            {wrong.map((item) => <article className="wrong-card" key={item.position}>
              <span className="wrong-prompt" lang="ja">{item.prompt}</span>
              <div className="wrong-details">
                {item.meaning && <span className="wrong-meaning">{item.meaning}</span>}
                <span className="wrong-answer">Bạn trả lời: <strong>{item.answer === '?' ? 'Không biết' : item.answer}</strong></span>
                <span className="wrong-correct">Đáp án: <strong>{item.expected_romaji.join(' · ')}</strong> <span lang="ja">{item.expected_readings.join(' · ')}</span></span>
              </div>
            </article>)}
          </div>
        )}
      </section>

      <section className="section-block focus-section" aria-labelledby="next-focus-heading">
        <div className="section-heading"><div><p className="eyebrow">GỢI Ý CHO LẦN TỚI</p><h2 id="next-focus-heading">Lần tới sẽ tập trung <span className="heading-count">{nextFocus.length}</span></h2></div></div>
        {nextFocus.length === 0 ? <div className="state-card"><p>Chưa có mục nào cần ưu tiên. Hãy tiếp tục luyện tập để xây dựng trí nhớ nhé.</p></div> : (
          <div className="focus-chip-list">{nextFocus.map((item) => <div className="focus-chip" key={item.key}><span className="focus-chip-prompt" lang="ja">{item.prompt}</span><span className="focus-chip-weak">{item.weakness} điểm cần ôn</span></div>)}</div>
        )}
      </section>
    </div>
  );
}
