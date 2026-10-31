import { useCallback, useEffect, useMemo, useState } from 'react';
import type { LessonItem } from '../api/types';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { api, errorMessage } from '../api/client';
import type { LessonSummary } from '../api/types';
import { LoadError } from '../components/LoadError';
import { PageStatus } from '../components/PageStatus';

const filters = [
  ['all', 'Tất cả'],
  ['weak', 'Cần ôn'],
  ['unseen', 'Chưa gặp'],
  ['mastered', 'Đã thuộc'],
] as const;
type Filter = (typeof filters)[number][0];

function accuracy(item: LessonItem): string {
  const p = item.progress;
  if (!p || p.seen_count === 0) return '—';
  return `${Math.round((p.correct_count / p.seen_count) * 100)}%`;
}

export function LessonPage() {
  const { slug = '' } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const [lesson, setLesson] = useState<LessonSummary | null>(null);
  const [items, setItems] = useState<LessonItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [filter, setFilter] = useState<Filter>('all');
  const [resetting, setResetting] = useState(false);

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError('');
    try {
      const result = await api.getLesson(slug, signal);
      setLesson(result.lesson);
      setItems(result.items);
    } catch (caught) {
      if (signal?.aborted) return;
      setError(errorMessage(caught));
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, [slug]);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  useEffect(() => {
    if (loading || !lesson || searchParams.get('start') !== '1') return;
    setSearchParams({}, { replace: true });
    void startPractice();
    // The URL query is consumed once after lesson metadata loads.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading, lesson, searchParams, setSearchParams]);

  const filteredItems = useMemo(() => items.filter((item) => {
    const progress = item.progress;
    if (filter === 'weak') return (progress?.weakness ?? 0) > 0;
    if (filter === 'unseen') return !progress || progress.seen_count === 0;
    if (filter === 'mastered') return !!progress && progress.weakness === 0 && progress.streak >= 3;
    return true;
  }), [filter, items]);

  async function startPractice() {
    if (!lesson) return;
    try {
      const session = await api.createSession(lesson.slug);
      navigate(`/practice/${encodeURIComponent(session.id)}`);
    } catch (caught) {
      setError(errorMessage(caught));
    }
  }

  async function resetProgress() {
    if (!lesson || resetting) return;
    if (!window.confirm(`Xóa toàn bộ tiến độ bài “${lesson.title}”? Các lượt học đang mở cũng sẽ bị dừng. Thao tác này không thể hoàn tác.`)) return;
    setResetting(true);
    setError('');
    try {
      await api.resetLessonProgress(lesson.slug);
      await load();
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setResetting(false);
    }
  }

  if (loading) return <PageStatus label="Đang tải bài học…" />;
  if (error && !lesson) return <LoadError message={error} onRetry={() => void load()} />;
  if (!lesson) return <LoadError message="Không tìm thấy bài học." />;

  return (
    <div className="page-stack">
      <nav className="breadcrumb" aria-label="Đường dẫn">
        <Link to="/">Bài học</Link><span aria-hidden="true">/</span><span aria-current="page">{lesson.title}</span>
      </nav>
      <section className="lesson-detail-hero">
        <div className="lesson-detail-copy">
          <p className="eyebrow">BÀI {String(lesson.position).padStart(2, '0')}</p>
          <h1>{lesson.title}</h1>
          <p>{lesson.description}</p>
          <div className="button-row">
            <button className="button button-primary" type="button" onClick={() => void startPractice()}>Luyện tập <span aria-hidden="true">→</span></button>
            <button className="button button-quiet" type="button" onClick={() => void resetProgress()} disabled={resetting}>
              {resetting ? 'Đang xóa…' : 'Đặt lại tiến độ'}
            </button>
          </div>
        </div>
        <div className="lesson-detail-stat" aria-label={`${lesson.progress.seen_items} trên ${lesson.item_count} mục đã gặp`}>
          <span className="stat-number">{lesson.progress.seen_items}</span>
          <span className="stat-divider">/</span>
          <span className="stat-total">{lesson.item_count}</span>
          <span className="stat-caption">mục đã gặp</span>
        </div>
      </section>
      {error && <div className="inline-alert" role="alert">{error}</div>}
      <section className="section-block" aria-labelledby="items-heading">
        <div className="section-heading section-heading-wrap">
          <div><p className="eyebrow">KHO TỪ VỰNG</p><h2 id="items-heading">Các mục trong bài</h2></div>
          <div className="filter-tabs" role="group" aria-label="Lọc mục học">
            {filters.map(([key, label]) => <button key={key} type="button" className={`filter-tab${filter === key ? ' is-active' : ''}`} aria-pressed={filter === key} onClick={() => setFilter(key)}>{label}</button>)}
          </div>
        </div>
        <p className="results-note">Hiển thị {filteredItems.length} / {items.length} mục</p>
        {filteredItems.length === 0 ? <div className="state-card"><p>Không có mục nào trong bộ lọc này.</p></div> : (
          <div className="item-grid">
            {filteredItems.map((item) => {
              const progress = item.progress;
              const weak = (progress?.weakness ?? 0) > 0;
              const mastered = !!progress && progress.weakness === 0 && progress.streak >= 3;
              return (
                <article className={`item-card${weak ? ' item-card-weak' : ''}`} key={item.key}>
                  <div className="item-card-heading">
                    <span className="item-prompt" lang="ja">{item.prompt}</span>
                    <span className={`item-status${weak ? ' status-weak' : mastered ? ' status-mastered' : ''}`}>
                      {weak ? 'Cần ôn' : mastered ? 'Đã thuộc' : progress?.seen_count ? 'Đang học' : 'Mới'}
                    </span>
                  </div>
                  <div className="item-romaji">{item.romaji.join(' · ')}</div>
                  {item.meaning && <p className="item-meaning">{item.meaning}</p>}
                  <div className="item-stats">
                    <span>{progress?.seen_count ?? 0} lần gặp</span>
                    <span>Chính xác {accuracy(item)}</span>
                    <span>{progress?.weakness ?? 0} điểm cần ôn</span>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
