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

type KanaRow = {
  label: string;
  kana: readonly [string?, string?, string?, string?, string?];
};

const VOWEL_ROW: KanaRow = { label: '母音', kana: ['あ', 'い', 'う', 'え', 'お'] };

const KANA_ROWS: readonly KanaRow[] = [
  { label: 'K', kana: ['か', 'き', 'く', 'け', 'こ'] },
  { label: 'S', kana: ['さ', 'し', 'す', 'せ', 'そ'] },
  { label: 'T', kana: ['た', 'ち', 'つ', 'て', 'と'] },
  { label: 'N', kana: ['な', 'に', 'ぬ', 'ね', 'の'] },
  { label: 'H', kana: ['は', 'ひ', 'ふ', 'へ', 'ほ'] },
  { label: 'M', kana: ['ま', 'み', 'む', 'め', 'も'] },
  { label: 'Y', kana: ['や', undefined, 'ゆ', undefined, 'よ'] },
  { label: 'R', kana: ['ら', 'り', 'る', 'れ', 'ろ'] },
  { label: 'W', kana: ['わ', undefined, undefined, undefined, 'を'] },
  { label: 'ん', kana: [undefined, undefined, 'ん', undefined, undefined] },
];

function toKatakanaRow({ label, kana }: KanaRow): KanaRow {
  const convert = (character?: string) => character?.replace(/[ぁ-ゖ]/u, (hiragana) =>
    String.fromCharCode(hiragana.charCodeAt(0) + 0x60),
  );
  return {
    label: label === 'ん' ? 'ン' : label,
    kana: [convert(kana[0]), convert(kana[1]), convert(kana[2]), convert(kana[3]), convert(kana[4])],
  };
}

const KATAKANA_ROWS: readonly KanaRow[] = KANA_ROWS.map(toKatakanaRow);
const KATAKANA_VOWEL_ROW = toKatakanaRow(VOWEL_ROW);
const VOWELS = ['a', 'i', 'u', 'e', 'o'] as const;
const ROW_LABELS: Record<string, string> = { K: 'か行', S: 'さ行', T: 'た行', N: 'な行', H: 'は行', M: 'ま行', Y: 'や行', R: 'ら行', W: 'わ行', 'ん': 'ん' };

function accuracy(item: LessonItem): string {
  const p = item.progress;
  if (!p || p.seen_count === 0) return '—';
  return `${Math.round((p.correct_count / p.seen_count) * 100)}%`;
}

function ItemCard({ item, compact = false }: { item: LessonItem; compact?: boolean }) {
  const progress = item.progress;
  const weak = (progress?.weakness ?? 0) > 0;
  const mastered = !!progress && progress.weakness === 0 && progress.streak >= 3;
  return (
    <article className={`item-card${weak ? ' item-card-weak' : ''}${compact ? ' kana-card' : ''}`}>
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
  const kanaLesson = lesson?.slug === 'hiragana' || lesson?.slug === 'katakana';
  const kanaRows = lesson?.slug === 'katakana'
    ? [KATAKANA_VOWEL_ROW, ...KATAKANA_ROWS]
    : [VOWEL_ROW, ...KANA_ROWS];
  const kanaItems = kanaLesson ? filteredItems.filter((item) => item.kind === 'char') : [];
  const kanaByPrompt = new Map(kanaItems.map((item) => [item.prompt, item]));
  const mappedPrompts = new Set(kanaRows.flatMap((row) => row.kana.filter((prompt): prompt is string => !!prompt)));
  const vocabularyItems = kanaLesson
    ? filteredItems.filter((item) => item.kind !== 'char' || !mappedPrompts.has(item.prompt))
    : filteredItems;

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
          <>
            {kanaLesson && kanaItems.length > 0 && (
              <div className="kana-table-scroll" role="region" aria-label="Bảng kana cơ bản" tabIndex={0}>
                <table className="kana-table">
                  <caption className="sr-only">Bảng gojūon: hàng nguyên âm và các hàng phụ âm của kana cơ bản</caption>
                  <thead>
                    <tr>
                      <th scope="col" className="kana-row-heading" aria-label="Hàng">行</th>
                      {VOWELS.map((vowel, column) => <th scope="col" key={vowel}>{vowel}{lesson.slug === 'katakana' && <span className="kana-column-symbol" lang="ja">{KATAKANA_VOWEL_ROW.kana[column]}</span>}{lesson.slug === 'hiragana' && <span className="kana-column-symbol" lang="ja">{VOWEL_ROW.kana[column]}</span>}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {kanaRows.map((row) => (
                      <tr key={row.label}>
                        <th scope="row" className="kana-row-heading" aria-label={ROW_LABELS[row.label] ?? row.label}>{row.label}</th>
                        {row.kana.map((prompt, column) => {
                          const item = prompt ? kanaByPrompt.get(prompt) : undefined;
                          return (
                            <td key={`${row.label}-${column}`} className={!prompt ? 'kana-empty' : undefined}>
                              {item && <ItemCard item={item} compact />}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {vocabularyItems.length > 0 && (
              <div className="item-grid">
                {vocabularyItems.map((item) => <ItemCard item={item} key={item.key} />)}
              </div>
            )}
          </>
        )}
      </section>
    </div>
  );
}
