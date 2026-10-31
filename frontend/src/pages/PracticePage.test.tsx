import { act, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError, api } from '../api/client';
import type { AnswerResult, Question, SessionDetail } from '../api/types';
import { PracticePage } from './PracticePage';

vi.mock('../api/client', async (importOriginal: () => Promise<{ api: typeof api }>) => {
  const actual = await importOriginal();
  return {
    ...actual,
    api: {
      ...actual.api,
      getSession: vi.fn(),
      submitAnswer: vi.fn(),
    },
  };
});

const mockedApi = vi.mocked(api);

const questions: Question[] = [
  { position: 0, prompt: 'あ', kind: 'char', meaning: null, is_focus: true, answered: false, result: null },
  { position: 1, prompt: 'い', kind: 'char', meaning: null, is_focus: false, answered: false, result: null },
];

const session: SessionDetail = {
  id: 'session-1', lesson: { slug: 'hiragana', title: 'Hiragana' }, status: 'active',
  total: 2, answered_count: 0, correct_count: 0, focus_count: 1,
  created_at: '2026-10-30T04:00:00Z', completed_at: null, questions,
};

const answerResult: AnswerResult = {
  position: 0, is_correct: true, answer: 'a', expected_romaji: ['a'], expected_readings: ['あ'],
  meaning: null,
  progress: { seen_count: 1, correct_count: 1, wrong_count: 0, weakness: 0, streak: 1, last_seen_at: '2026-10-30T04:00:00Z' },
  session: { status: 'active', total: 2, answered_count: 1, correct_count: 1 },
};

function renderPractice() {
  return render(
    <MemoryRouter initialEntries={['/practice/session-1']}>
      <Routes>
        <Route path="/practice/:sessionId" element={<PracticePage />} />
        <Route path="/sessions/:id/summary" element={<div>Trang tổng kết</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

// Testing Library's findBy/waitFor poll with setTimeout, which is faked here, so flush promises directly.
async function settle() {
  for (let i = 0; i < 5; i += 1) {
    await act(async () => {
      await Promise.resolve();
    });
  }
}

async function typeAndCheck(value: string) {
  await settle();
  fireEvent.change(screen.getByLabelText('Cách đọc romaji'), { target: { value } });
  fireEvent.click(screen.getByRole('button', { name: /kiểm tra/i }));
  await settle();
}

function wait(ms: number) {
  act(() => {
    vi.advanceTimersByTime(ms);
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  // Only the auto-advance delay after a correct answer is faked; promises stay real.
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] });
  mockedApi.getSession.mockResolvedValue(session);
  mockedApi.submitAnswer.mockResolvedValue(answerResult);
});

afterEach(() => {
  vi.useRealTimers();
});

describe('PracticePage', () => {
  it('shows feedback, then moves to the next prompt by itself after 700ms', async () => {
    const { container } = renderPractice();
    await settle();
    expect(screen.getByText('あ')).toBeInTheDocument();
    expect(screen.getByText('Ôn lại')).toBeInTheDocument();
    const input = screen.getByLabelText('Cách đọc romaji');
    expect(input).toHaveAttribute('autocomplete', 'off');
    expect(input).toHaveAttribute('autocapitalize', 'off');
    expect(input).toHaveAttribute('spellcheck', 'false');

    await typeAndCheck('a');
    expect(mockedApi.submitAnswer).toHaveBeenCalledWith('session-1', 0, 'a');
    expect(screen.getByText('Chính xác!')).toBeInTheDocument();
    expect(screen.getByRole('progressbar', { name: 'Tiến độ lượt luyện tập' })).toHaveAttribute('aria-valuenow', '1');

    wait(699);
    expect(screen.getByText('Chính xác!')).toBeInTheDocument();
    wait(1);
    expect(screen.getByText('い')).toBeInTheDocument();
    expect(screen.queryByText('Chính xác!')).not.toBeInTheDocument();
    expect(container.querySelector('.answer-feedback')).toBeEmptyDOMElement();
  });

  it('keeps a wrong answer on screen until the next button is pressed', async () => {
    mockedApi.submitAnswer.mockResolvedValue({ ...answerResult, is_correct: false, answer: 'zzz' });
    renderPractice();
    await typeAndCheck('zzz');

    expect(screen.getByText('Chưa đúng rồi')).toBeInTheDocument();
    expect(screen.getByText('あ', { selector: 'span' })).toBeInTheDocument();
    wait(10000);
    expect(screen.getByText('Chưa đúng rồi')).toBeInTheDocument();
    expect(screen.queryByText('い')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /câu tiếp theo/i }));
    expect(screen.getByText('い')).toBeInTheDocument();
    expect(screen.queryByText('Chưa đúng rồi')).not.toBeInTheDocument();
  });

  it('keeps the expected reading after Không biết until Enter is pressed', async () => {
    mockedApi.submitAnswer.mockResolvedValue({ ...answerResult, is_correct: false, answer: '?' });
    renderPractice();
    await settle();
    fireEvent.click(screen.getByRole('button', { name: 'Không biết' }));
    await settle();

    expect(mockedApi.submitAnswer).toHaveBeenCalledWith('session-1', 0, '?');
    expect(screen.getByText('Chưa đúng rồi')).toBeInTheDocument();
    wait(10000);
    expect(screen.getByText('あ', { selector: 'span' })).toBeInTheDocument();

    fireEvent.keyDown(screen.getByLabelText('Cách đọc romaji'), { key: 'Enter', code: 'Enter' });
    expect(screen.getByText('い')).toBeInTheDocument();
  });

  it('lets Enter skip the delay without the pending timer skipping another question', async () => {
    renderPractice();
    await typeAndCheck('a');
    expect(screen.getByText('Chính xác!')).toBeInTheDocument();

    fireEvent.keyDown(screen.getByLabelText('Cách đọc romaji'), { key: 'Enter', code: 'Enter' });
    expect(screen.getByText('い')).toBeInTheDocument();
    wait(2000);
    expect(screen.getByText('い')).toBeInTheDocument();
    expect(screen.queryByText('Trang tổng kết')).not.toBeInTheDocument();
  });

  it('stays on the question when the answer request fails', async () => {
    mockedApi.submitAnswer.mockRejectedValue(new ApiError(500, 'Máy chủ đang bận.'));
    renderPractice();
    await typeAndCheck('a');

    expect(screen.getByRole('alert')).toHaveTextContent('Máy chủ đang bận.');
    wait(2000);
    expect(screen.getByText('あ')).toBeInTheDocument();
    expect(screen.getByLabelText('Cách đọc romaji')).toBeEnabled();
  });

  it('goes to the summary by itself after the last answer', async () => {
    mockedApi.getSession.mockResolvedValue({ ...session, total: 1, questions: [questions[0]!] });
    mockedApi.submitAnswer.mockResolvedValue({ ...answerResult, session: { status: 'completed', total: 1, answered_count: 1, correct_count: 1 } });
    renderPractice();
    await typeAndCheck('a');

    expect(screen.getByRole('button', { name: /xem kết quả/i })).toBeInTheDocument();
    wait(700);
    expect(screen.getByText('Trang tổng kết')).toBeInTheDocument();
  });

  it('waits for the button before the summary when the last answer is wrong', async () => {
    mockedApi.getSession.mockResolvedValue({ ...session, total: 1, questions: [questions[0]!] });
    mockedApi.submitAnswer.mockResolvedValue({
      ...answerResult, is_correct: false, answer: 'zzz',
      session: { status: 'completed', total: 1, answered_count: 1, correct_count: 0 },
    });
    renderPractice();
    await typeAndCheck('zzz');

    wait(10000);
    expect(screen.queryByText('Trang tổng kết')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /xem kết quả/i }));
    expect(screen.getByText('Trang tổng kết')).toBeInTheDocument();
  });

  it('cancels the pending advance when the page unmounts', async () => {
    const setTimeoutSpy = vi.spyOn(window, 'setTimeout');
    const clearTimeoutSpy = vi.spyOn(window, 'clearTimeout');
    const { unmount } = renderPractice();
    await typeAndCheck('a');
    expect(screen.getByText('Chính xác!')).toBeInTheDocument();
    const advanceIndex = setTimeoutSpy.mock.calls.findIndex(([, delay]) => delay === 700);
    expect(advanceIndex).toBeGreaterThanOrEqual(0);

    unmount();
    expect(clearTimeoutSpy).toHaveBeenCalledWith(setTimeoutSpy.mock.results[advanceIndex]!.value);
    setTimeoutSpy.mockRestore();
    clearTimeoutSpy.mockRestore();
  });
});
