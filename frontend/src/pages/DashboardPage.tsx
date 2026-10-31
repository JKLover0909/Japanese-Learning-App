import { useCallback, useEffect, useState } from 'react';
import type { ChapterInfo, LessonSummary } from '../api/types';
import { api, errorMessage } from '../api/client';
import { ChapterTestCard } from '../components/ChapterTestCard';
import { LessonCard } from '../components/LessonCard';
import { LoadError } from '../components/LoadError';
import { PageStatus } from '../components/PageStatus';

export function DashboardPage() {
  const [lessons, setLessons] = useState<LessonSummary[]>([]);
  const [chapters, setChapters] = useState<ChapterInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async (signal?: AbortSignal) => {
    setError('');
    setLoading(true);
    try {
      const [lessonResult, chapterResult] = await Promise.all([
        api.listLessons(signal),
        api.listChapters(signal),
      ]);
      setLessons(lessonResult.lessons);
      setChapters(chapterResult.chapters);
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

  if (loading) return <PageStatus label="Đang mở bài học…" />;
  const inChapter = new Set(chapters.flatMap((chapter) => chapter.lesson_slugs));
  const otherLessons = lessons.filter((lesson) => !inChapter.has(lesson.slug));
  return (
    <div className="page-stack">
      <section className="welcome-banner">
        <div className="welcome-copy">
          <p className="eyebrow">GÓC HỌC CỦA BẠN</p>
          <h1>Chào bạn<span className="welcome-period">.</span></h1>
          <p>Một chút mỗi ngày, kana sẽ dần trở nên thân thuộc.</p>
        </div>
        <div className="welcome-stamp" lang="ja" aria-label="Học từ từ, chắc chắn">ゆっくり<br /><span>確実に</span></div>
        <span className="banner-decoration banner-decoration-one" aria-hidden="true" />
        <span className="banner-decoration banner-decoration-two" aria-hidden="true" />
      </section>

      {error ? <LoadError message={error} onRetry={() => void load()} /> : lessons.length === 0 ? (
        <div className="state-card"><p>Chưa có bài học nào. Hãy kiểm tra lại sau nhé.</p></div>
      ) : (
        <>
          {chapters.map((chapter) => {
            const chapterLessons = lessons.filter((lesson) => chapter.lesson_slugs.includes(lesson.slug));
            const headingId = `chapter-${chapter.chapter}-heading`;
            return (
              <section key={chapter.chapter} className="section-block" aria-labelledby={headingId}>
                <div className="section-heading">
                  <div><p className="eyebrow">CHƯƠNG {chapter.chapter}</p><h2 id={headingId}>{chapter.title.replace(/^Chương \d+:\s*/, '')}</h2></div>
                  <span className="section-count">{chapterLessons.length} bài + kiểm tra</span>
                </div>
                <div className="lesson-grid">{chapterLessons.map((lesson) => <LessonCard key={lesson.slug} lesson={lesson} />)}</div>
                <ChapterTestCard chapter={chapter} />
              </section>
            );
          })}
          {otherLessons.length > 0 && (
            <section className="section-block" aria-labelledby="lessons-heading">
              <div className="section-heading">
                <div><p className="eyebrow">LỘ TRÌNH</p><h2 id="lessons-heading">{chapters.length > 0 ? 'Bài học khác' : 'Bài học của bạn'}</h2></div>
                <span className="section-count">{otherLessons.length} bài</span>
              </div>
              <div className="lesson-grid">{otherLessons.map((lesson) => <LessonCard key={lesson.slug} lesson={lesson} />)}</div>
            </section>
          )}
        </>
      )}
    </div>
  );
}
