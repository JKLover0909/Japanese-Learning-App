import { Link } from 'react-router-dom';
import type { LessonSummary } from '../api/types';
import { ProgressMeter } from './ProgressMeter';

const lessonMarks: Record<string, string> = {
  hiragana: 'あ',
  'hiragana-extended': 'が',
  katakana: 'カ',
  'katakana-extended': 'ファ',
  greetings: 'こんにちは',
  numbers: '百',
};

function formatAccuracy(value: number | null): string {
  return value === null ? '—' : `${Math.round(value * 100)}%`;
}

export function LessonCard({ lesson }: { lesson: LessonSummary }) {
  const progress = lesson.progress;
  const progressPercent = lesson.item_count > 0 ? Math.round((progress.seen_items / lesson.item_count) * 100) : 0;
  return (
    <article className="lesson-card">
      <div className="lesson-card-top">
        <span className="lesson-index">BÀI {String(lesson.position).padStart(2, '0')}</span>
        <span className="lesson-mark" lang="ja" aria-hidden="true">{lessonMarks[lesson.slug] ?? 'あ'}</span>
      </div>
      <div className="lesson-card-copy">
        <h2>{lesson.title}</h2>
        <p>{lesson.description}</p>
      </div>
      <div className="lesson-meta-row">
        <span>{lesson.item_count} mục học</span>
        <span className="meta-separator" aria-hidden="true">·</span>
        <span>Độ chính xác <strong>{formatAccuracy(progress.accuracy)}</strong></span>
      </div>
      <div className="lesson-progress">
        <ProgressMeter label="Đã gặp" value={progress.seen_items} total={lesson.item_count} />
        <ProgressMeter label="Đã thuộc" value={progress.mastered_items} total={lesson.item_count} tone="success" />
      </div>
      <div className="lesson-card-bottom">
        <span className={`weak-count${progress.weak_items > 0 ? ' has-weak' : ''}`}>
          <span className="weak-dot" aria-hidden="true" />
          {progress.weak_items > 0 ? `${progress.weak_items} mục cần ôn` : 'Chưa có mục yếu'}
        </span>
        <div className="lesson-actions">
          <Link className="button button-quiet button-small" to={`/lessons/${encodeURIComponent(lesson.slug)}`}>Chi tiết</Link>
          <Link className="button button-primary button-small" to={lesson.active_session_id ? `/practice/${encodeURIComponent(lesson.active_session_id)}` : `/lessons/${encodeURIComponent(lesson.slug)}?start=1`}>
            {lesson.active_session_id ? 'Tiếp tục' : 'Luyện tập'}
          </Link>
        </div>
      </div>
      <span className="sr-only">Đã gặp {progressPercent}% nội dung.</span>
    </article>
  );
}
