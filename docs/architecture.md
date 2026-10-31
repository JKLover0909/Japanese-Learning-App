# Architecture

## Overview

```
Browser (phone / desktop)
   │  HTTPS (ngrok or Cloudflare tunnel) or http://localhost:8010
   ▼
FastAPI app (uvicorn, single process) ── serves /api/* and the built SPA (frontend/dist)
   │  SQLAlchemy 2.0
   ▼
SQLite (WAL mode) at data/app.db ── schema managed by Alembic
```

One origin serves both the API and the SPA, so one tunnel exposes the whole app and the
browser needs no CORS. In development, Vite (port 5173) proxies `/api` to the backend on
port 8010.

## Repository layout

```
backend/
  app/
    main.py            create_app(): middleware, routers, lifespan (migrate + content sync), SPA
    config.py          Settings (pydantic-settings, env prefix JP_)
    db.py              engine, session factory, get_db dependency, SQLite pragmas
    models.py          SQLAlchemy ORM models
    security.py        password hashing (argon2), opaque tokens, cookie names
    api/               routers: learner.py, admin.py, lessons.py, sessions.py, chapter_tests.py,
                       auth.py (disabled);
                       deps.py (anonymous learner cookie), schemas.py
    services/
      romaji.py        kana → romaji and lenient answer checking (pure functions)
      selection.py     choose the questions for a practice session (pure, RNG injected)
      progress.py      update ItemProgress after an answer (pure rules + DB helper)
      content_sync.py  upsert validated lesson JSON into the DB
      rate_limit.py    in-memory admin login failure limiter
      listening.py     kana sound keys and distractors for listening questions (pure)
      chapter_test.py  chapter definitions and 30-question test generation (pure, RNG injected)
      audio.py         AudioLibrary: prompt → recorded clip URL, from content/audio.json
    content/
      schema.py        pydantic models for lesson JSON
      validation.py    content rules per lesson; load_lessons() raises on any problem
      lessons/*.json   the six lessons (source of truth for content)
      audio.json       manifest of VOICEVOX clips (prompt → file), credit line
  alembic/             migrations (render_as_batch for SQLite)
  scripts/validate_content.py
  scripts/set_admin_password.py   prompt for the admin password, store its hash in .env
  scripts/generate_audio.py       record test audio with a local VOICEVOX engine
  tests/
frontend/              Vite + React + TypeScript SPA; public/assets/audio/*.mp3 test clips
docs/                  this documentation
scripts/               dev / serve / tunnel helpers
Dockerfile, docker-compose.yml
```

## Data model

| Table | Purpose | Key columns |
|---|---|---|
| `users` | owner of progress and sessions; one row per anonymous browser (`anon-…`, login disabled) plus any legacy accounts | `username` (unique), `password_hash`, `display_name` |
| `anonymous_identities` | browser cookie → user | `token_hash` (unique SHA-256 of `jp_learner`), `user_id` (unique), `created_at`, `last_seen_at` (minute precision) |
| `visits` | coarse visit events for admin statistics, kept 90 days | `identity_id`, `visited_at` |
| `admin_sessions` | admin login sessions | `token_hash` (unique SHA-256 of `jp_admin`), `expires_at` |
| `auth_sessions` | legacy learner login sessions; no longer created | `token_hash`, `user_id`, `expires_at`, `last_used_at` |
| `lessons` | lesson metadata synced from JSON | `slug` (unique), `position`, `title`, `description`, `content_hash` |
| `items` | questions synced from JSON | `lesson_id`, `key` (unique per lesson), `prompt`, `kind`, `meaning`, `readings` (JSON), `tags` (JSON), `position`, `is_active` |
| `item_progress` | per-learner memory of each item | PK (`user_id`, `item_id`), `seen_count`, `correct_count`, `wrong_count`, `weakness`, `streak`, `last_seen_at`, `last_wrong_at` |
| `practice_sessions` | one 20-question round | `id` (UUID), `user_id`, `lesson_id`, `status`, `total`, `answered_count`, `correct_count`, `focus_count`, `created_at`, `completed_at` |
| `session_questions` | the questions in a round | `session_id`, `position` (unique per session), `item_id`, `is_focus`, `answer`, `is_correct`, `answered_at` |
| `chapter_tests` | one end-of-chapter listening test | `id` (UUID), `user_id`, `chapter`, `status`, `total`, `answered_count`, `correct_count`, `created_at`, `completed_at` |
| `chapter_test_questions` | its 30 questions | `test_id`, `position` (unique per test), `part`, `item_id`, `options` (JSON), `answer_index`, `choice`, `is_correct`, `answered_at` |

**Content sync.** On startup the app validates every lesson file (`load_lessons`). If any file
is invalid, startup fails. It then upserts lessons and items **by key**. Items whose key
disappears from the content get `is_active = false`, which keeps the learner's history. Item
keys must therefore never be renamed.

**Lesson split.** Lesson 5 used to be `greetings-numbers`. It is now `greetings` (position 5,
phrases) and `numbers` (position 6, prompts 1–100). On the first sync after upgrading,
`_move_legacy_items` re-points the old item rows to the new lessons by key instead of
creating new rows, so `item_progress` and past `session_questions` keep their `item_id`. The
old lesson row is then deactivated (hidden from the lesson list) but not deleted, so old
session summaries still load.

**Anonymous learners.** `deps.get_anonymous_user` reads the `jp_learner` cookie. A missing or
unknown cookie creates a new `users` row, an `anonymous_identities` row and a first `visits`
event, then sets a fresh cookie. A known cookie bumps `last_seen_at` (at most once a minute,
with a compare-and-set update so concurrent requests do not double-count). Activity after at
least 30 minutes of inactivity records another visit. The rest of the code still filters by
`user_id`, so progress and history stay isolated per browser.

**Admin statistics.** `api/admin.py` has its own login, checked against
`JP_ADMIN_USERNAME` / `JP_ADMIN_PASSWORD_HASH`, and its own cookie scoped to `/api/admin`.
`/api/admin/overview` returns only aggregate counts (see [API](api.md#admin)). The admin is
never a learner, and learner cookies grant no admin access.

## Learning rules

**Progress update** after each answer (`services/progress.py`):

| Outcome | Changes |
|---|---|
| any | `seen_count += 1`, `last_seen_at = now` |
| correct | `correct_count += 1`, `streak += 1`, `weakness = max(0, weakness - 1)` |
| wrong | `wrong_count += 1`, `streak = 0`, `weakness = min(10, weakness + 2)`, `last_wrong_at = now` |

An item is **weak** while `weakness > 0`. One mistake therefore needs two correct answers to
clear. An item is **mastered** when `weakness == 0 and streak >= 3`.

**Session selection** (`services/selection.py`, defaults `SESSION_SIZE = 20`, `FOCUS_SIZE = 5`):

1. Candidates are the lesson's active items.
2. **Focus:** the weak items ordered by `weakness` desc, then `last_wrong_at` desc. Take up
   to `FOCUS_SIZE`.
3. **General:** the other items ordered by `seen_count` asc, then `last_seen_at` asc (never
   seen first), with ties broken randomly. Draw `SESSION_SIZE - len(focus)` items at random
   from the first `max(3 × needed, 45)` of that order. Rarely seen items rotate in, but rounds
   still vary.
4. Shuffle the combined list, set `is_focus` on focus items, and number the positions from 0.
   If a lesson has fewer than `SESSION_SIZE` items, the session uses all of them.

The selector is a pure function over `(items, progress_by_item_id, rng)`, so it is
deterministic under a seeded `random.Random`.

## Chapter listening test

Chapter 1 groups lessons 1–5 (`services/chapter_test.py`, `CHAPTERS`). Its test copies the
paper test used in class: the learner hears a clip and circles one of four written options.

| Part | Questions | Drawn from |
|---|---|---|
| Hiragana: chữ đơn | 3 | 2 basic + 1 voiced single kana |
| Hiragana: từ | 15 | 5 basic + 10 extended hiragana words |
| Katakana: chữ đơn | 3 | basic single katakana |
| Katakana: âm ghép | 1 | a contracted sound (キャ, シュ…) |
| Katakana: từ | 8 | 3 basic + 5 extended katakana words |

**Generation** (`generate_test(candidates, has_audio, rng, avoid)`) is pure. Each section
draws distinct prompts, preferring items not in `avoid` (the previous attempt). It shuffles
within each part and places the answer at a random index.

- **Single kana:** distractors come from look-alike shape groups (る → う, ら, ろ, つ), then
  the same row.
- **Words:** `services/listening.py` makes plausible misspellings by changing a vowel or a
  consonant, a contracted sound, a long vowel, っ or ん.
- **Sound keys:** every option must have a different sound key, so two options never sound
  alike. The key treats お/う and え/い lengthening and を/お, ぢ/じ, づ/ず as equal.
- **Excluded prompts:** any containing を, ぢ, づ, ゔ or ゎ, and a standalone ん.

**Audio.** `scripts/generate_audio.py` records each test prompt once with a local VOICEVOX
engine (voice 四国めたん) into `frontend/public/assets/audio/<hash>.mp3`. It also writes the
prompt → file map to `app/content/audio.json`. Vite copies the clips into `dist/`, and the SPA
route serves them same-origin with long-lived caching. The API only exposes
`audio_url`, never the prompt text, while a test is active. A prompt without a clip is not
asked; if a part cannot be filled, the chapter reports `available: false` and starting a test
returns `503`. The UI shows the credit 「VOICEVOX:四国めたん」 required by the voice's terms.

**Scoring.** Choices are stored as they are made and can change while the test is `active`.
Submitting first flips the test to `completed` with a conditional update (a concurrent
second submit gets `409`), then scores every question from the stored choices.

## Security

- Learner and admin tokens are 32 random bytes from `secrets`; only their SHA-256 hash is
  stored. The admin password exists only as an argon2id hash (`argon2-cffi`) in the
  environment; it is never stored in the database or sent to the frontend. Admin login is
  closed (`503`) while the hash or username is unset.
- `jp_learner` is `HttpOnly`, `SameSite=Lax`, 1 year. `jp_admin` is `HttpOnly`,
  `SameSite=Strict`, `Path=/api/admin`, 12 hours. Both are `Secure` on HTTPS. State-changing
  API calls need the `X-Requested-With: jp-practice` header (a CSRF guard, because cross-site
  forms cannot set custom headers). API responses send `Cache-Control: no-store`.
- Admin login failures are rate limited per client address (5 per 5 minutes), whatever
  username is submitted. Learner account registration and login are disabled (`410`).
- Analytics are aggregate only. No IP address, user agent or answer text is stored for
  statistics; visit timestamps are minute-precision and pruned after 90 days. Anyone can
  create many anonymous identities, so visitor numbers are estimates, not unique people.
- Every session and progress query filters by the current learner's user ID. Another
  browser's session returns 404.
- Responses carry `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin`,
  `X-Frame-Options: DENY` and a strict CSP:
  `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:;
  connect-src 'self'; font-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'`.
  The SPA therefore loads no external fonts, CDNs or inline scripts.
- Proxy headers are handled by uvicorn (`--proxy-headers --forwarded-allow-ips`), not by the
  app. The forwarded IP list is `127.0.0.1` for a local ngrok/cloudflared and the compose
  network in Docker.

## Configuration (environment, prefix `JP_`)

| Variable | Default | Meaning |
|---|---|---|
| `JP_DATABASE_URL` | `sqlite:///<repo>/data/app.db` | SQLAlchemy URL |
| `JP_ADMIN_USERNAME` | empty | admin statistics username; admin login is closed while empty |
| `JP_ADMIN_PASSWORD_HASH` | empty | argon2id hash from `backend/scripts/set_admin_password.py`; never the password |
| `JP_COOKIE_SECURE` | `auto` | `auto` (from request scheme), `true` or `false` |
| `JP_CONTENT_DIR` | `backend/app/content/lessons` | lesson JSON directory |
| `JP_FRONTEND_DIST` | `<repo>/frontend/dist` | built SPA to serve; skipped when missing |
| `JP_AUTO_MIGRATE` | `true` | run `alembic upgrade head` on startup |
| `JP_SESSION_SIZE` / `JP_FOCUS_SIZE` | `20` / `5` | practice round sizes |
