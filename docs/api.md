# HTTP API contract

This is the contract between `backend/` (FastAPI) and `frontend/` (React).
Both sides must follow it exactly. Change this file first when the API changes.

- Base path: `/api`. Everything else is served by the SPA (history fallback to `index.html`).
- Bodies are JSON (`Content-Type: application/json`). Timestamps are ISO 8601 UTC strings
  with a `Z` or `+00:00` suffix.
- Errors use FastAPI's shape: `{"detail": "Vietnamese, user-facing message"}`. Validation
  errors (422) use FastAPI's default list shape; the frontend shows a generic message for them.
- Learners are anonymous: each browser is identified by an HttpOnly cookie, see
  [Anonymous learners](#anonymous-learners). The admin statistics page has its own separate
  login, see [Admin](#admin).
- **CSRF guard:** every `POST`/`PUT`/`PATCH`/`DELETE` request to `/api/*` must send the header
  `X-Requested-With: jp-practice`. Requests without it get `403 {"detail": "..."}`.
  The frontend API client always sends it.

## Shared objects

```jsonc
// LessonProgress — aggregate over the lesson's active items for the current browser
{
  "seen_items": 37,        // items with seen_count > 0
  "weak_items": 6,         // items with weakness > 0
  "mastered_items": 12,    // items with weakness == 0 and streak >= 3
  "total_answers": 180,    // sum of seen_count
  "correct_answers": 151,  // sum of correct_count
  "accuracy": 0.839        // correct_answers / total_answers, or null when total_answers == 0
}

// LessonSummary
{
  "slug": "hiragana",
  "position": 1,
  "title": "Hiragana",
  "description": "...",
  "item_count": 196,             // active items only
  "progress": LessonProgress,
  "active_session_id": "uuid"   // the browser's newest status=active session for this lesson, or null
}

// ItemProgress
{
  "seen_count": 4, "correct_count": 3, "wrong_count": 1,
  "weakness": 1, "streak": 2,
  "last_seen_at": "2026-10-30T04:00:00Z"   // or null
}

// Question — readings and romaji are NOT revealed until answered
{
  "position": 0,              // 0-based index within the session
  "prompt": "がっこう",
  "kind": "word",             // "char" | "word" | "phrase" | "number"
  "meaning": "trường học",    // null for chars; numbers have null
  "is_focus": true,           // chosen because the learner often gets it wrong
  "answered": false,
  "result": null              // QuestionResult once answered
}

// QuestionResult
{
  "answer": "gakko",
  "is_correct": false,
  "expected_romaji": ["gakkou"],      // canonical romaji per reading, display order
  "expected_readings": ["がっこう"]    // kana readings, same order
}

// SessionDetail
{
  "id": "0d4c…",                       // UUID string
  "lesson": { "slug": "hiragana-extended", "title": "Hiragana mở rộng" },
  "status": "active",                 // "active" | "completed" | "abandoned"
  "total": 20,
  "answered_count": 3,
  "correct_count": 2,
  "focus_count": 5,
  "created_at": "…",
  "completed_at": null,
  "questions": [Question, …]          // ordered by position
}
```

## Health and config

| Method | Path | Response |
|---|---|---|
| GET | `/api/health` | `200 {"status": "ok"}` |
| GET | `/api/config` | `200 {"registration_open": false, "registration_code_required": false, "session_size": 20, "focus_size": 5}` |

`registration_open` and `registration_code_required` are always `false` while learner accounts
are disabled; they remain for backward compatibility.

## Anonymous learners

The learner cookie is named `jp_learner`: an opaque random token. Only its SHA-256 hash is
stored (`anonymous_identities`), linked to a browser-specific user row that owns progress and
sessions. Attributes: `HttpOnly`, `SameSite=Lax`, `Path=/`, `Max-Age` = 1 year. `Secure` is
set when `request.url.scheme == "https"`. Behind ngrok or cloudflared, uvicorn's own
proxy-header handling (`--proxy-headers --forwarded-allow-ips`) turns `X-Forwarded-Proto` /
`X-Forwarded-For` into the request scheme and client address. The app does not parse
forwarding headers itself.

| Method | Path | Body | Success | Errors |
|---|---|---|---|---|
| POST | `/api/learner/init` | none | `200 {"status": "ok"}`; sets `jp_learner` when it is missing or unknown | `403` missing CSRF header |

Rules:

- Every lesson and session endpoint below accepts a missing, unknown or forged cookie: it
  creates a fresh identity and sets a new cookie. The SPA calls `/api/learner/init` once
  before its first parallel requests so that they share one identity.
- Progress belongs to the browser. Clearing cookies, a private window or another device starts
  with empty progress. Another browser's session IDs return `404`.
- Activity after at least 30 minutes of inactivity records one visit event (coarse timestamp
  and identity ID only; no IP address or user agent). `last_seen_at` is stored to the minute.
- The legacy learner account endpoints `POST /api/auth/register`, `POST /api/auth/login`,
  `POST /api/auth/logout` and `GET /api/auth/me` return `410 {"detail": "..."}` regardless
  of the old `JP_ALLOW_REGISTRATION` setting.

## Admin

The admin statistics login is independent of learners. The username and Argon2 password hash
come only from the `JP_ADMIN_USERNAME` and `JP_ADMIN_PASSWORD_HASH` environment variables; no
credential is stored in the database or sent to the frontend. The admin cookie is named
`jp_admin` (opaque token, SHA-256 hash stored in `admin_sessions`) with `HttpOnly`,
`SameSite=Strict`, `Path=/api/admin`, `Max-Age` = 12 hours, and `Secure` on HTTPS.

| Method | Path | Body | Success | Errors |
|---|---|---|---|---|
| POST | `/api/admin/login` | `{"username", "password"}` (1–64 / 1–128 characters) | `200 {"status": "ok"}` + cookie | `401` wrong credentials, `429` too many failures, `503` admin not configured, `422` |
| POST | `/api/admin/logout` | none | `204`; deletes the session and clears the cookie | — |
| GET | `/api/admin/overview` | — | `200 AdminOverview` | `401` missing/expired session or admin not configured |

```jsonc
// AdminOverview — aggregate counts only; never usernames, cookies, IPs or answers
{
  "visitors_total": 1234,        // anonymous browser identities ever created
  "active_learners_7d": 56,      // identities with activity in the last 7 days
  "active_sessions_15m": 3,      // sessions created or answered in the last 15 minutes
  "questions_in_sessions": 4000, // sum of questions in all practice sessions
  "answers_submitted": 3210,     // sum of answered questions, including "Không biết"
  "visits_by_day": [             // exactly 30 UTC days, oldest first, zero-filled
    { "date": "2026-10-01", "visits": 0 }, …, { "date": "2026-10-30", "visits": 42 }
  ]
}
```

Rules:

- After 5 failed logins from one client address within 5 minutes, login returns `429` until
  the window passes, whatever username is submitted. The limiter key is a hash of
  `request.client.host`; it is kept in memory only.
- Username comparison is constant-time and the password is always verified against the hash.
- Each overview request deletes visit events older than 90 days.

## Lessons

| Method | Path | Success | Errors |
|---|---|---|---|
| GET | `/api/lessons` | `200 {"lessons": [LessonSummary, …]}`, ordered by `position` | — |
| GET | `/api/lessons/{slug}` | `200 {"lesson": LessonSummary, "items": [LessonItem, …]}` | `404` |
| DELETE | `/api/lessons/{slug}/progress` | `204`: deletes this browser's ItemProgress for that lesson and abandons its active sessions | `404` |

```jsonc
// LessonItem (content order)
{
  "key": "w-gakkou", "prompt": "がっこう", "kind": "word", "meaning": "trường học",
  "tags": ["sokuon", "chouon"],
  "readings": ["がっこう"], "romaji": ["gakkou"],
  "progress": ItemProgress            // or null when never practised
}
```

## Practice sessions

| Method | Path | Body | Success | Errors |
|---|---|---|---|---|
| POST | `/api/sessions` | `{"lesson_slug": "hiragana"}` | `201 SessionDetail` | `404` unknown lesson |
| GET | `/api/sessions` | query `lesson_slug`?, `limit`? (1–100, default 20) | `200 {"sessions": [SessionListItem, …]}`, newest first | `422` |
| GET | `/api/sessions/{id}` | — | `200 SessionDetail` | `404` (also when another browser owns it) |
| POST | `/api/sessions/{id}/answers` | `{"position": 0, "answer": "gakkou"}` | `200 AnswerResult` | `404`, `409` session not active or question already answered, `422` bad position or empty answer |
| GET | `/api/sessions/{id}/summary` | — | `200 SessionSummary` | `404` |

Creating a session marks the browser's other `active` sessions **for the same lesson** as
`abandoned`. `answer` is 1–200 characters after trimming. The "Không biết" (give up) button
sends `"?"`, which is always wrong. Questions may be answered in any order. When the last
question is answered, the session becomes `completed` and `completed_at` is set. After a
correct answer the frontend shows the result for about 700 ms and then moves to the next
question (Enter skips the wait). After a wrong answer or a give-up, it keeps the expected
reading visible until the learner presses "Câu tiếp theo" or Enter.

```jsonc
// SessionListItem
{ "id": "…", "lesson_slug": "hiragana", "lesson_title": "Hiragana", "status": "completed",
  "total": 20, "answered_count": 20, "correct_count": 17, "created_at": "…", "completed_at": "…" }

// AnswerResult
{
  "position": 4,
  "is_correct": true,
  "answer": "kitte",
  "expected_romaji": ["kitte"],
  "expected_readings": ["きって"],
  "meaning": "tem thư",
  "progress": ItemProgress,          // the item's progress after this answer
  "session": { "status": "active", "total": 20, "answered_count": 5, "correct_count": 4 }
}

// SessionSummary
{
  "session": SessionDetail,
  "wrong": [                          // wrong answers in this session, by position
    { "position": 2, "prompt": "しゃ", "kind": "char", "meaning": null,
      "answer": "sa", "expected_romaji": ["sha"], "expected_readings": ["しゃ"] }
  ],
  "next_focus": [                     // what the NEXT session will focus on (up to focus_size)
    { "key": "c-sha", "prompt": "しゃ", "kind": "char", "weakness": 2 }
  ]
}
```

## Chapter tests

Lessons 1–5 (hiragana, hiragana-extended, katakana, katakana-extended, greetings) form
chapter 1. Its end-of-chapter test copies the paper "listen and circle" test: 30 questions,
each a recorded kana or word with four written options a–d. Nothing is scored or revealed
until the test is submitted.

| Method | Path | Body | Success | Errors |
|---|---|---|---|---|
| GET | `/api/chapters` | — | `200 {"chapters": [ChapterInfo, …]}` | — |
| POST | `/api/chapters/{chapter}/tests` | — | `201 ChapterTestDetail` (a new test) | `404` unknown chapter, `503` not enough content or audio |
| GET | `/api/tests/{id}` | — | `200 ChapterTestDetail` | `404` (also when another browser owns it) |
| PUT | `/api/tests/{id}/answers` | `{"position": 0, "choice": 2}` | `200 {"position", "choice", "total", "answered_count"}` | `404`, `409` test not active, `422` bad position or `choice` outside 0–3 |
| POST | `/api/tests/{id}/submit` | — | `200 ChapterTestResult` | `404`, `409` already submitted or abandoned |
| GET | `/api/tests/{id}/result` | — | `200 ChapterTestResult` | `404`, `409` not submitted yet |

Starting a test marks the browser's other `active` test for that chapter as `abandoned`.
Each new test draws new items, distractors and option order, and avoids the items of the
browser's previous test of the chapter when the pool allows it. `PUT …/answers` can be
repeated to change a choice until the test is submitted. Unanswered questions count as wrong.

```jsonc
// ChapterInfo
{ "chapter": 1, "title": "Chương 1: Hiragana, Katakana và chào hỏi",
  "lesson_slugs": ["hiragana", "hiragana-extended", "katakana", "katakana-extended", "greetings"],
  "question_count": 30,
  "available": true,                  // false when lessons or audio clips cannot fill every part
  "active_test_id": "…",              // or null
  "attempts": 2, "best_score": 27, "last_score": 25,   // submitted tests only; scores null before
  "audio_credit": "VOICEVOX:四国めたん" }

// ChapterTestDetail (no answer key)
{ "id": "…", "chapter": 1, "title": "…", "status": "active",   // active | completed | abandoned
  "total": 30, "answered_count": 12,
  "correct_count": null,              // set only once completed
  "created_at": "…", "completed_at": null, "audio_credit": "VOICEVOX:四国めたん",
  "questions": [
    { "position": 0, "part": "hiragana-char", "part_label": "Hiragana: chữ đơn",
      "audio_url": "/assets/audio/3f…e1.mp3", "options": ["る", "ろ", "う", "ら"], "choice": 1 }
  ] }

// ChapterTestResult
{ "test": ChapterTestDetail,
  "parts": [ { "part": "hiragana-word", "label": "Hiragana: từ", "correct": 13, "total": 15 } ],
  "questions": [ { /* ChapterTestDetail question fields */
      "answer_index": 0, "is_correct": false, "meaning": "cái kéo" } ] }
```

The five parts, in order: `hiragana-char` (3), `hiragana-word` (15), `katakana-char` (3),
`katakana-youon` (1), `katakana-word` (8).

## Answer checking

The server decides correctness with `app.services.romaji.is_correct(readings, answer)`. Input is
case-, width- and space-insensitive and accepts Hepburn, Kunrei and IME spellings (`shi`/`si`,
`tsu`/`tu`, `ja`/`zya`, `n`/`nn`, `m` before b/p/m), macrons (`tōkyō`), `-` for ー, and
`ou`/`oo` for おう. The frontend never decides correctness.
