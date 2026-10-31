import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import type { SessionListItem } from '../api/types';
import { api, errorMessage } from '../api/client';
import { LoadError } from '../components/LoadError';
import { PageStatus } from '../components/PageStatus';

function dateLabel(value: string): string {
  return new Date(value).toLocaleString('vi-VN', {
    day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit',
  });
}

export function HistoryPage() {
  const [sessions, setSessions] = useState<SessionListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError('');
    try {
      const result = await api.listSessions({ limit: 100 }, signal);
      setSessions(result.sessions);
    } catch (caught) {
      if (signal?.aborted) return;
      setError(errorMessage(caught));
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  if (loading) return <PageStatus label="Đang tải lịch sử…" />;
  if (error) return <LoadError message={error} onRetry={() => void load()} />;

  return (
    <div className="page-stack">
      <section className="page-heading-block">
        <p className="eyebrow">DẤU CHÂN HỌC TẬP</p>
        <h1>Lịch sử luyện tập</h1>
        <p>Mỗi lượt học đều là một bước tiến nhỏ.</p>
      </section>
      <section className="section-block" aria-labelledby="history-heading">
        <div className="section-heading"><div><p className="eyebrow">GẦN ĐÂY</p><h2 id="history-heading">Các lượt học <span className="heading-count">{sessions.length}</span></h2></div></div>
        {sessions.length === 0 ? (
          <div className="state-card empty-history"><span className="state-icon" aria-hidden="true">あ</span><h3>Chưa có lượt luyện tập</h3><p>Khi bạn hoàn thành một lượt học, lịch sử sẽ xuất hiện ở đây.</p><Link className="button button-primary" to="/">Chọn bài học <span aria-hidden="true">→</span></Link></div>
        ) : (
          <div className="history-list">
            {sessions.map((session) => {
              const completed = session.status === 'completed';
              const destination = completed ? `/sessions/${encodeURIComponent(session.id)}/summary` : `/practice/${encodeURIComponent(session.id)}`;
              return <article className="history-card" key={session.id}>
                <div className={`history-status-mark${completed ? ' history-done' : ''}`} aria-hidden="true">{completed ? '✓' : '↻'}</div>
                <div className="history-info"><h3><Link to={destination}>{session.lesson_title}</Link></h3><p>{dateLabel(session.created_at)}</p></div>
                <div className="history-result"><strong>{session.correct_count}<span> / {session.total}</span></strong><span>{completed ? 'câu đúng' : `đã trả lời ${session.answered_count}`}</span></div>
                <Link className="button button-quiet button-small history-action" to={destination}>{completed ? 'Xem lại' : 'Tiếp tục'} <span aria-hidden="true">→</span></Link>
              </article>;
            })}
          </div>
        )}
      </section>
    </div>
  );
}
