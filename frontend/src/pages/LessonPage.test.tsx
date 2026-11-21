import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '../api/client';
import type { LessonItem, LessonSummary } from '../api/types';
import { LessonPage } from './LessonPage';

vi.mock('../api/client', async (importOriginal: () => Promise<{ api: typeof api }>) => {
  const actual = await importOriginal();
  return {
    ...actual,
    api: { ...actual.api, getLesson: vi.fn(), createSession: vi.fn(), resetLessonProgress: vi.fn() },
  };
});

const mockedApi = vi.mocked(api);

const hiraganaRows = [
  ['か', 'き', 'く', 'け', 'こ'], ['さ', 'し', 'す', 'せ', 'そ'],
  ['た', 'ち', 'つ', 'て', 'と'], ['な', 'に', 'ぬ', 'ね', 'の'],
  ['は', 'ひ', 'ふ', 'へ', 'ほ'], ['ま', 'み', 'む', 'め', 'も'],
  ['や', '', 'ゆ', '', 'よ'], ['ら', 'り', 'る', 'れ', 'ろ'],
  ['わ', '', '', '', 'を'], ['ん'],
];
const vowels = ['あ', 'い', 'う', 'え', 'お'];
const allHiragana = [...vowels, ...hiraganaRows.flat()]
  .filter(Boolean)
  .map((prompt) => [prompt, prompt.charCodeAt(0) + 0x60] as const);

function item(prompt: string, kind: LessonItem['kind'] = 'char', progress: LessonItem['progress'] = null): LessonItem {
  return {
    key: `key-${prompt}`, prompt, kind, meaning: kind === 'word' ? 'meaning' : null,
    tags: [], readings: [prompt], romaji: [prompt], progress,
  };
}

function lesson(slug: string): LessonSummary {
  return {
    slug, position: 1, title: slug, description: 'description', item_count: allHiragana.length + 1,
    progress: { seen_items: 0, weak_items: 0, mastered_items: 0, total_answers: 0, correct_answers: 0, accuracy: null },
    active_session_id: null,
  };
}

function renderLesson(slug: string) {
  return render(
    <MemoryRouter initialEntries={[`/lessons/${slug}`]}>
      <Routes><Route path="/lessons/:slug" element={<LessonPage />} /></Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => vi.clearAllMocks());

describe('LessonPage kana bank', () => {
  it.each(['hiragana', 'katakana'])('shows the basic %s characters in a five-vowel matrix', async (slug) => {
    const prompts = allHiragana.map(([hiragana, codepoint]) =>
      slug === 'katakana' ? String.fromCharCode(codepoint) : hiragana,
    );
    mockedApi.getLesson.mockResolvedValue({
      lesson: lesson(slug),
      items: [...prompts.map((prompt) => item(prompt)), item(slug === 'hiragana' ? 'あさ' : 'アサ', 'word')],
    });
    renderLesson(slug);

    const matrix = await screen.findByRole('table', { name: 'Bảng gojūon: hàng nguyên âm và các hàng phụ âm của kana cơ bản' });
    expect(within(matrix).getAllByRole('rowheader').map((header) => header.textContent)).toEqual(['母音', 'K', 'S', 'T', 'N', 'H', 'M', 'Y', 'R', 'W', slug === 'katakana' ? 'ン' : 'ん']);
    expect(within(matrix).getAllByRole('columnheader').map((header) => header.textContent)).toEqual([
      '行', ...['a', 'i', 'u', 'e', 'o'].map((vowel, index) => `${vowel}${slug === 'katakana' ? String.fromCharCode(vowels[index]!.charCodeAt(0) + 0x60) : vowels[index]}`),
    ]);
    for (const prompt of prompts) expect(within(matrix).getByText(prompt, { selector: '.item-prompt' })).toBeInTheDocument();
    expect(document.querySelector('.item-grid')?.textContent).toContain(prompts[0] === 'あ' ? 'あさ' : 'アサ');
    expect(screen.getByText('Hiển thị 47 / 47 mục')).toBeInTheDocument();

    const yRow = within(matrix).getByRole('row', { name: /や行/ });
    expect(within(yRow).getAllByRole('cell')).toHaveLength(5);
    expect(within(yRow).getAllByRole('cell')[1]).toBeEmptyDOMElement();
    expect(within(yRow).getAllByRole('cell')[3]).toBeEmptyDOMElement();
  });

  it('filters matrix characters and vocabulary without changing the other lesson grid', async () => {
    const progress: NonNullable<LessonItem['progress']> = {
      seen_count: 1, correct_count: 0, wrong_count: 1, weakness: 2, streak: 0, last_seen_at: null,
    };
    mockedApi.getLesson.mockResolvedValue({
      lesson: lesson('hiragana'),
      items: [item('あ', 'char', progress), item('い'), item('あさ', 'word'), item('いえ', 'word', progress)],
    });
    renderLesson('hiragana');
    const matrix = await screen.findByRole('table');
    expect(screen.getByText('Hiển thị 4 / 4 mục')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Cần ôn' }));
    expect(screen.getByText('Hiển thị 2 / 4 mục')).toBeInTheDocument();
    expect(within(matrix).getByText('あ', { selector: '.item-prompt' })).toBeInTheDocument();
    expect(within(matrix).queryByText('い', { selector: '.item-prompt' })).not.toBeInTheDocument();
    expect(document.querySelector('.item-grid')?.textContent).toContain('いえ');
    expect(screen.queryByText('あさ')).not.toBeInTheDocument();

    cleanup();
    mockedApi.getLesson.mockResolvedValue({ lesson: lesson('hiragana-extended'), items: [item('が')] });
    renderLesson('hiragana-extended');
    expect((await screen.findAllByText('が')).length).toBeGreaterThan(0);
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
    expect(document.querySelectorAll('.item-grid .item-card')).toHaveLength(1);
  });
});
