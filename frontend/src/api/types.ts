// Types mirroring docs/api.md. Keep this file in sync with that contract.

/** ISO 8601 UTC timestamp, e.g. "2026-10-30T04:00:00Z". */
export type IsoDateTime = string;

export type ItemKind = 'char' | 'word' | 'phrase' | 'number';

export type SessionStatus = 'active' | 'completed' | 'abandoned';

export interface AppConfig {
  registration_open: boolean;
  registration_code_required: boolean;
  session_size: number;
  focus_size: number;
}

export interface HealthResponse {
  status: 'ok';
}

/** Aggregate over the lesson's active items for the current user. */
export interface LessonProgress {
  seen_items: number;
  weak_items: number;
  mastered_items: number;
  total_answers: number;
  correct_answers: number;
  /** correct_answers / total_answers, or null when total_answers == 0. */
  accuracy: number | null;
}

export interface LessonSummary {
  slug: string;
  position: number;
  title: string;
  description: string;
  item_count: number;
  progress: LessonProgress;
  active_session_id: string | null;
}

export interface ItemProgress {
  seen_count: number;
  correct_count: number;
  wrong_count: number;
  weakness: number;
  streak: number;
  last_seen_at: IsoDateTime | null;
}

export interface LessonItem {
  key: string;
  prompt: string;
  kind: ItemKind;
  meaning: string | null;
  tags: string[];
  readings: string[];
  romaji: string[];
  progress: ItemProgress | null;
}

export interface QuestionResult {
  answer: string;
  is_correct: boolean;
  expected_romaji: string[];
  expected_readings: string[];
}

/** Readings and romaji are not revealed until the question is answered. */
export interface Question {
  position: number;
  prompt: string;
  kind: ItemKind;
  meaning: string | null;
  is_focus: boolean;
  answered: boolean;
  result: QuestionResult | null;
}

export interface LessonRef {
  slug: string;
  title: string;
}

export interface SessionDetail {
  id: string;
  lesson: LessonRef;
  status: SessionStatus;
  total: number;
  answered_count: number;
  correct_count: number;
  focus_count: number;
  created_at: IsoDateTime;
  completed_at: IsoDateTime | null;
  questions: Question[];
}

export interface SessionListItem {
  id: string;
  lesson_slug: string;
  lesson_title: string;
  status: SessionStatus;
  total: number;
  answered_count: number;
  correct_count: number;
  created_at: IsoDateTime;
  completed_at: IsoDateTime | null;
}

export interface SessionCounts {
  status: SessionStatus;
  total: number;
  answered_count: number;
  correct_count: number;
}

export interface AnswerResult {
  position: number;
  is_correct: boolean;
  answer: string;
  expected_romaji: string[];
  expected_readings: string[];
  meaning: string | null;
  progress: ItemProgress;
  session: SessionCounts;
}

export interface WrongAnswer {
  position: number;
  prompt: string;
  kind: ItemKind;
  meaning: string | null;
  answer: string;
  expected_romaji: string[];
  expected_readings: string[];
}

export interface FocusItem {
  key: string;
  prompt: string;
  kind: ItemKind;
  weakness: number;
}

export interface SessionSummary {
  session: SessionDetail;
  wrong: WrongAnswer[];
  next_focus: FocusItem[];
}

// End-of-chapter listening tests

export type TestStatus = 'active' | 'completed' | 'abandoned';

export interface ChapterInfo {
  chapter: number;
  title: string;
  lesson_slugs: string[];
  question_count: number;
  /** False while lessons or recorded audio cannot fill a whole test. */
  available: boolean;
  active_test_id: string | null;
  /** Submitted tests. */
  attempts: number;
  best_score: number | null;
  last_score: number | null;
  audio_credit: string;
}

export interface ChapterTestQuestion {
  position: number;
  part: string;
  part_label: string;
  audio_url: string | null;
  options: string[];
  /** The circled option; the right answer stays hidden until the test is submitted. */
  choice: number | null;
}

export interface ChapterTestDetail {
  id: string;
  chapter: number;
  title: string;
  status: TestStatus;
  total: number;
  answered_count: number;
  /** null until submitted. */
  correct_count: number | null;
  created_at: string;
  completed_at: string | null;
  audio_credit: string;
  questions: ChapterTestQuestion[];
}

export interface ChapterTestAnswer {
  position: number;
  choice: number;
  total: number;
  answered_count: number;
}

export interface ChapterTestPartScore {
  part: string;
  label: string;
  correct: number;
  total: number;
}

export interface ChapterTestResultQuestion {
  position: number;
  part: string;
  part_label: string;
  audio_url: string | null;
  options: string[];
  choice: number | null;
  answer_index: number;
  is_correct: boolean;
  meaning: string | null;
}

export interface ChapterTestResult {
  test: ChapterTestDetail;
  parts: ChapterTestPartScore[];
  questions: ChapterTestResultQuestion[];
}

export interface ChaptersResponse {
  chapters: ChapterInfo[];
}

// Request bodies

export interface AdminLoginRequest {
  username: string;
  password: string;
}

export interface AnswerRequest {
  position: number;
  answer: string;
}

// Response envelopes

export interface StatusResponse {
  status: 'ok';
}

/** Aggregate counts only; the API never returns per-learner records. */
export interface AdminOverview {
  /** Browsers that have ever received a learner cookie. */
  visitors_total: number;
  active_learners_7d: number;
  active_sessions_15m: number;
  questions_in_sessions: number;
  answers_submitted: number;
  /** 30 consecutive UTC days, oldest first, zero-filled. */
  visits_by_day: { date: string; visits: number }[];
}

export interface LessonsResponse {
  lessons: LessonSummary[];
}

export interface LessonDetailResponse {
  lesson: LessonSummary;
  items: LessonItem[];
}

export interface SessionsResponse {
  sessions: SessionListItem[];
}

export interface ListSessionsParams {
  lesson_slug?: string;
  /** 1–100, default 20 on the server. */
  limit?: number;
}
