import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import type { ChapterInfo } from '../api/types';
import { api, errorMessage } from '../api/client';

export function ChapterTestCard({ chapter }: { chapter: ChapterInfo }) {
  const navigate = useNavigate();
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState('');

  async function start() {
    if (starting) return;
    setStarting(true);
    setError('');
    try {
      const test = await api.createChapterTest(chapter.chapter);
      navigate(`/tests/${encodeURIComponent(test.id)}`);
    } catch (caught) {
      setError(errorMessage(caught));
      setStarting(false);
    }
  }

  const activeId = chapter.active_test_id;
  return (
    <article className="chapter-test-card">
      <div className="chapter-test-mark" lang="ja" aria-hidden="true">聞</div>
      <div className="chapter-test-copy">
        <p className="eyebrow">KIỂM TRA CUỐI CHƯƠNG</p>
        <h3>Nghe và chọn đáp án đúng</h3>
        <p>
          {chapter.question_count} câu, mỗi câu 4 lựa chọn a–d. Mỗi lần làm là một đề mới với câu hỏi và đáp án khác.
        </p>
        <p className="chapter-test-stats">
          {chapter.attempts > 0
            ? <>Đã làm {chapter.attempts} lần · Lần gần nhất <strong>{chapter.last_score}/{chapter.question_count}</strong> · Cao nhất <strong>{chapter.best_score}/{chapter.question_count}</strong></>
            : 'Chưa làm lần nào.'}
        </p>
        {error && <p className="form-error" role="alert">{error}</p>}
        {!chapter.available && <p className="chapter-test-note">Bài kiểm tra chưa sẵn sàng: còn thiếu nội dung hoặc âm thanh.</p>}
      </div>
      <div className="chapter-test-actions">
        {activeId && (
          <button className="button button-secondary button-small" type="button" onClick={() => navigate(`/tests/${encodeURIComponent(activeId)}`)}>
            Làm tiếp bài dở
          </button>
        )}
        <button className="button button-primary button-small" type="button" disabled={!chapter.available || starting} onClick={() => void start()}>
          {starting ? 'Đang tạo đề…' : activeId ? 'Làm đề mới' : chapter.attempts > 0 ? 'Làm lại đề mới' : 'Bắt đầu kiểm tra'}
        </button>
      </div>
    </article>
  );
}
