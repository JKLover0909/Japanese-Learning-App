import { act, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '../api/client';
import type { ChapterTestDetail, ChapterTestQuestion } from '../api/types';
import { ChapterTestPage, NEXT_QUESTION_DELAY_MS } from './ChapterTestPage';

vi.mock('../api/client', async (importOriginal: () => Promise<{ api: typeof api }>) => {
  const actual = await importOriginal();
  return {
    ...actual,
    api: {
      ...actual.api,
      getChapterTest: vi.fn(),
      answerChapterTest: vi.fn(),
      submitChapterTest: vi.fn(),
    },
  };
});

const mockedApi = vi.mocked(api);

const questions: ChapterTestQuestion[] = [
  { position: 0, part: 'hiragana-char', part_label: 'Chữ hiragana', audio_url: '/assets/audio/a.mp3', options: ['る', 'ろ', 'う', 'ら'], choice: null },
  { position: 1, part: 'hiragana-word', part_label: 'Từ hiragana', audio_url: '/assets/audio/b.mp3', options: ['はさみ', 'はすみ', 'ほさみ', 'はさめ'], choice: null },
  { position: 2, part: 'katakana-word', part_label: 'Từ katakana', audio_url: '/assets/audio/c.mp3', options: ['タクシー', 'タクシ', 'ダクシー', 'タケシー'], choice: null },
];

const test: ChapterTestDetail = {
  id: 'test-1', chapter: 1, title: 'Chương 1: Bảng chữ cái', status: 'active',
  total: 3, answered_count: 0, correct_count: null,
  created_at: '2026-10-30T04:00:00Z', completed_at: null,
  audio_credit: 'VOICEVOX:四国めたん',
  example: { audio_url: '/assets/audio/a.mp3', options: ['あ', 'い', 'う', 'え'], answer_index: 0 },
  questions,
};

function renderTest() {
  return render(
    <MemoryRouter initialEntries={['/tests/test-1']}>
      <Routes>
        <Route path="/tests/:testId" element={<ChapterTestPage />} />
        <Route path="/tests/:testId/result" element={<div>Trang kết quả</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

async function settle() {
  for (let i = 0; i < 5; i += 1) {
    await act(async () => {
      await Promise.resolve();
    });
  }
}

async function startScoredTest() {
  await settle();
  fireEvent.click(screen.getByRole('button', { name: 'Bắt đầu bài kiểm tra →' }));
  await settle();
}

function wait(ms: number) {
  act(() => {
    vi.advanceTimersByTime(ms);
  });
}

function option(name: string) {
  return screen.getByRole('radio', { name: new RegExp(name) });
}

let play: ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.clearAllMocks();
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] });
  play = vi.fn().mockResolvedValue(undefined);
  vi.spyOn(HTMLMediaElement.prototype, 'play').mockImplementation(play);
  vi.spyOn(HTMLMediaElement.prototype, 'pause').mockImplementation(() => undefined);
  mockedApi.getChapterTest.mockResolvedValue(test);
  mockedApi.answerChapterTest.mockImplementation((_id, position, choice) => Promise.resolve({
    position, choice, total: 3, answered_count: 1,
  }));
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe('ChapterTestPage', () => {
  it('plays the question and circles an option without revealing the answer', async () => {
    renderTest();
    await settle();
    expect(play).toHaveBeenCalled();
    expect(screen.getByText('CÂU MẪU · NGHE VÀ CHỌN ĐÁP ÁN')).toBeInTheDocument();
    expect(screen.getByText('Câu mẫu · không tính điểm')).toBeInTheDocument();
    expect(screen.getByText('Bài chính có 3 câu và được chấm điểm riêng.')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('radio', { name: /あ/ }));
    expect(screen.getByRole('status')).toHaveTextContent('Chính xác!');
    expect(mockedApi.answerChapterTest).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Bắt đầu bài kiểm tra →' }));
    expect(screen.getByText('1', { selector: 'strong' })).toBeInTheDocument();
    expect(screen.getByText('Chữ hiragana')).toBeInTheDocument();
    expect(screen.getByText('Giọng đọc: VOICEVOX:四国めたん')).toBeInTheDocument();

    fireEvent.click(option('ろ'));
    await settle();
    expect(mockedApi.answerChapterTest).toHaveBeenCalledWith('test-1', 0, 1);
    expect(option('ろ')).toHaveAttribute('aria-checked', 'true');
    expect(screen.getByText('1/3 đã chọn')).toBeInTheDocument();
    expect(screen.queryByText(/đáp án:|chính xác|sai rồi/i)).not.toBeInTheDocument();

    wait(NEXT_QUESTION_DELAY_MS);
    expect(option('はさみ')).toBeInTheDocument();
  });

  it('reveals the sample answer after an incorrect choice without saving it', async () => {
    renderTest();
    await settle();
    fireEvent.click(screen.getByRole('radio', { name: /い/ }));
    expect(screen.getByRole('status')).toHaveTextContent('Chưa đúng. Đáp án là あ.');
    expect(mockedApi.answerChapterTest).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('radio', { name: /あ/ }));
    expect(screen.getByRole('status')).toHaveTextContent('Chính xác!');
    expect(mockedApi.answerChapterTest).not.toHaveBeenCalled();
  });

  it('shows the sample before resuming saved scored answers', async () => {
    mockedApi.getChapterTest.mockResolvedValue({
      ...test,
      answered_count: 1,
      questions: [{ ...questions[0]!, choice: 1 }, ...questions.slice(1)],
    });
    renderTest();
    await settle();
    expect(screen.getByText('CÂU MẪU · NGHE VÀ CHỌN ĐÁP ÁN')).toBeInTheDocument();
    expect(screen.getByText('Câu mẫu · không tính điểm')).toBeInTheDocument();
    expect(mockedApi.answerChapterTest).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Bắt đầu bài kiểm tra →' }));
    expect(screen.getByText('2', { selector: 'strong' })).toBeInTheDocument();
    expect(screen.getByText('1/3 đã chọn')).toBeInTheDocument();
    expect(option('はさみ')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Câu 1, đã chọn b' })).toBeInTheDocument();
    expect(mockedApi.answerChapterTest).not.toHaveBeenCalled();
  });

  it('lets the learner change a circled option without moving on', async () => {
    renderTest();
    await startScoredTest();
    fireEvent.click(option('ろ'));
    await settle();
    fireEvent.click(screen.getByRole('button', { name: 'Câu 1, đã chọn b' }));
    fireEvent.click(option('ら'));
    await settle();
    wait(NEXT_QUESTION_DELAY_MS);
    expect(mockedApi.answerChapterTest).toHaveBeenLastCalledWith('test-1', 0, 3);
    expect(option('ら')).toHaveAttribute('aria-checked', 'true');
    expect(option('ろ')).toHaveAttribute('aria-checked', 'false');
  });

  it('chooses with the keyboard', async () => {
    renderTest();
    await startScoredTest();
    fireEvent.keyDown(window, { key: 'c' });
    await settle();
    expect(mockedApi.answerChapterTest).toHaveBeenCalledWith('test-1', 0, 2);
    wait(NEXT_QUESTION_DELAY_MS);
    fireEvent.keyDown(window, { key: '4' });
    await settle();
    expect(mockedApi.answerChapterTest).toHaveBeenLastCalledWith('test-1', 1, 3);
  });

  it('asks for confirmation before submitting with open questions', async () => {
    mockedApi.submitChapterTest.mockResolvedValue({ test: { ...test, status: 'completed' }, parts: [], questions: [] });
    renderTest();
    await startScoredTest();
    const [submit] = screen.getAllByRole('button', { name: 'Nộp bài' });
    fireEvent.click(submit!);
    expect(screen.getByRole('alert')).toHaveTextContent('Còn 3 câu chưa chọn');
    expect(mockedApi.submitChapterTest).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'Vẫn nộp bài' }));
    await settle();
    expect(mockedApi.submitChapterTest).toHaveBeenCalledWith('test-1');
    expect(screen.getByText('Trang kết quả')).toBeInTheDocument();
  });

  it('offers a play button when the browser blocks autoplay', async () => {
    play.mockRejectedValue(new DOMException('blocked', 'NotAllowedError'));
    renderTest();
    await settle();
    expect(screen.getByRole('button', { name: 'Nghe câu mẫu' })).toHaveTextContent('Bấm để nghe');
    fireEvent.click(screen.getByRole('button', { name: 'Bắt đầu bài kiểm tra →' }));
    await settle();
    expect(screen.getByRole('button', { name: 'Nghe câu hỏi' })).toHaveTextContent('Bấm để nghe');
  });

  it('restores the previous choice when saving fails', async () => {
    mockedApi.answerChapterTest.mockRejectedValue(new Error('Mất kết nối'));
    renderTest();
    await startScoredTest();
    fireEvent.click(option('う'));
    await settle();
    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(option('う')).toHaveAttribute('aria-checked', 'false');
    expect(screen.getByText('0/3 đã chọn')).toBeInTheDocument();
  });
});
