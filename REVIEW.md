# Code Review — Course Portal (Flask)

**Reviewer:** AI code reviewer (pre-merge review)
**Reviewed at:** commit `d29e897` (HEAD of `main`, working tree clean)
**Scope:** Full application — `app.py`, `config.py`, all 7 templates, `static/js/main.js`, `static/css/style.css`, `test_app.py` (52 tests), documentation (`PROMPT.md`, `README.md`, `PLAN.md`, `WORKLOG.md`, `WORKLOG_TEST.md`)
**Method:** Static review of all source files, cross-checked against the user stories and acceptance criteria in `PROMPT.md`, plus empirical verification (running the test suite, inspecting the database, checking engine rebinding and git tracking). No code was changed.

---

## Executive Summary

**Verdict: Request changes — do not merge as-is.**

The application is a solid teaching demo with good bones: clean route structure, role checks on every route, UUID-based file storage that is safe against path traversal, Jinja auto-escaping, a working deadline lockout, and a 52-test suite that covers all seven user stories. However, it has **4 High-severity findings** that must be addressed before merge:

1. **Running the test suite destroys the development database** (proven empirically — the local `portal.db` is now empty because of it).
2. **The inline PDF preview (US-3) is broken** — the iframe points at a download route that forces `Content-Disposition: attachment`.
3. **Five of seven mutating routes have no CSRF protection**, despite `PLAN.md` explicitly promising Flask-WTF CSRF on all forms.
4. **The seeded demo submission points at a file that does not exist**, so the README's demo flow 404s out of the box.

Additionally, two acceptance criteria are not met at all (US-3 "sortable list", US-6 touch-target size for small buttons), and the peer-review workflow (US-2) is functionally defeated because reviewers cannot open the deck they are assigned to review.

---

## Findings

| # | Severity | Location | Finding |
|---|----------|----------|---------|
| 1 | 🔴 High | `test_app.py:26-60`, `app.py:449-450` | Test suite is not isolated; running pytest wipes the development database |
| 2 | 🔴 High | `app.py:368`, `templates/submission_detail.html:18` | Inline PDF preview broken — download route forces `as_attachment=True` |
| 3 | 🔴 High | `app.py:186, 223, 311, 330, 373` | No CSRF protection on upload, peer review, edit/delete feedback, batch download |
| 4 | 🔴 High | `app.py:429-430` | Seeded demo submission references missing `dummy.pdf` → 404 on download/preview |
| 5 | 🟠 Medium | `templates/submissions_list.html` | US-3 "sortable list" not implemented — no sorting controls anywhere |
| 6 | 🟠 Medium | `app.py:283-284, 354-355` | Peer reviewers cannot view/download the submission they must review |
| 7 | 🟠 Medium | `static/css/style.css:22-24` | `.btn-sm` override to 36px violates US-6's ≥44×44px touch targets |
| 8 | 🟠 Medium | `app.py:391` | Batch ZIP uses `original_filename` as `arcname` — duplicate names overwrite each other |
| 9 | 🟠 Medium | `app.py:453` | `app.run(debug=True, host='0.0.0.0')` — Werkzeug debugger exposed on all interfaces |
| 10 | 🟡 Low | `config.py:5`, `app.py:202` | Flask's global 413 handler fires before the custom size check → raw HTML error page |
| 11 | 🟡 Low | `app.py:223-268` | `peer_review` route lacks the explicit size check that `upload()` has |
| 12 | 🟡 Low | `static/js/main.js:75` | `document.write(xhr.responseText)` — deprecated, breaks SPA-style UX |
| 13 | 🟡 Low | `main.js:5`, `app.py:128-133` | Dead code (`ALLOWED_TYPES`), `uuid.` trailing-dot edge case, `secure_filename` can return empty string |
| 14 | 🟡 Low | `app.py:278, 353, 357, 361` | Legacy `Query.get()`/`get_or_404()` — source of the 20 test warnings |
| 15 | 🟡 Low | `app.py:50-59, 449-450` | Hand-rolled `UserMixin` methods; module-level `create_all()`/seed at import time |
| 16 | 🟡 Low | `config.py:7-8`, `PLAN.md` | Default secret key; Windows-only SQLite URI; PLAN.md route drift |
| 17 | 🟡 Low | `test_app.py:246, 272-273, 416, 433-434, 461-475` | Weak test assertions that test implementation text, not behavior |

---

## Detailed Findings

### 🔴 High 1 — Test suite is not isolated; pytest wipes the development database

**Where:** `test_app.py:26-60` (the `client` fixture), root cause `app.py:449-450`.

`app.py` runs `db.create_all()` and `seed_data()` at **module level, at import time** (`app.py:449-450`). The test fixture then tries to redirect the database:

```python
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{TEST_DB_PATH}'   # test_app.py:32
```

But with Flask-SQLAlchemy 3.1.1, the engine is created and **cached per app instance on first use**. Changing the config after the app has already used the DB does **not** rebind the engine. This was verified empirically: after setting the config override, `db.engine.url` inside `app.app_context()` still pointed at `portal.db`.

**Consequences, all reproduced during this review:**
- The 52 tests run against the **real development database** (`portal.db`), not `test_portal.db`.
- The fixture teardown calls `db.drop_all()` (`test_app.py:48`) — which drops the tables of the **development** DB.
- Running `python -m pytest test_app.py -q` (52 passed, 20 warnings — matching the claim in `WORKLOG_TEST.md`) left the local `portal.db` with **zero tables**. Its file hash changed during the run, confirming the write.
- Isolation is *mixed*, not just broken: `UPLOAD_FOLDER` **is** read at call time, so uploads go to `test_uploads/` while DB rows land in `portal.db`. The fixture also creates `dummy.pdf` in `test_uploads/` (`test_app.py:49-51`) — which is exactly why the tests pass despite the missing `uploads/dummy.pdf` in dev (see High 4).

**Fix direction:** create the app via an app factory (or at minimum move `create_all()`/seed out of module level), and in tests either use a fresh app per test or call `db.engine.dispose()` after changing the URI. An in-memory SQLite (`sqlite:///:memory:`) would also speed the suite up.

### 🔴 High 2 — Inline PDF preview is broken (US-3 acceptance failure)

**Where:** `templates/submission_detail.html:18`, `app.py:368`.

The detail template embeds the PDF in an iframe pointing at the download route:

```html
<iframe src="{{ url_for('download', sub_id=submission.id) }}" ...>
```

But the download route serves the file with `send_from_directory(..., as_attachment=True)` (`app.py:368`). Browsers treat an `attachment` response as a download, not a renderable document — they will **not** display it inside an iframe. The result is a broken/blank preview pane for every PDF, which fails US-3's "preview the file inline in a detailed view" acceptance criterion.

**Fix direction:** add an `?inline=true` variant (or a separate preview route) that serves with `as_attachment=False`, and point the iframe at that.

### 🔴 High 3 — CSRF protection missing on five of seven mutating routes

**Where:** `app.py:186` (upload), `app.py:223` (peer_review), `app.py:311` (edit_feedback), `app.py:330` (delete_feedback), `app.py:373` (download_batch).

Only `login` (`app.py:145`) and `add_feedback` (`app.py:291`) use Flask-WTF forms with CSRF tokens. The other five mutating endpoints read raw `request.form`/`request.files` with no token check, and the corresponding templates (`submission_detail.html` edit/delete feedback forms, `peer_review.html` upload form, `submissions_list.html` batch form) render plain `<form>` tags with no `hidden_tag()`. `PLAN.md` explicitly promised "Flask-WTF for form handling and CSRF protection on all forms" — this was not delivered.

A malicious page could trigger a cross-site POST to `/submission/<id>/delete-feedback/<fid>` or `/upload` in a logged-in lecturer's/student's browser. The test suite masks this because the fixture sets `WTF_CSRF_ENABLED = False` (`test_app.py:35`) and the unprotected routes never needed a token anyway.

**Fix direction:** wrap all remaining forms in Flask-WTF form classes (or add manual CSRF tokens) and assert their presence in tests.

### 🔴 High 4 — Seeded demo submission references a file that does not exist

**Where:** `app.py:429-430`.

`seed_data()` creates a submission for `student1` pointing at `dummy.pdf`, but no such file ships in `uploads/` (the directory is gitignored, and `WORKLOG.md` admits it was never created). Fresh out of the box, the README's demo flow — log in, open the dashboard, click the seeded submission, download or preview it — returns **404**. First impression of the demo is broken.

**Fix direction:** generate a small valid PDF at seed time (e.g., write a minimal one-page PDF via a helper), or ship the file.

### 🟠 Medium 5 — "Sortable list" (US-3) is not implemented

**Where:** `templates/submissions_list.html` (and the dashboard route `app.py:174/177`).

US-3 asks for a "sortable list of submissions". There are no sorting controls anywhere — a grep for `sort` across all templates returns zero matches. The lecturer's dashboard is fixed to `upload_timestamp` descending (`app.py:174`); no column headers are clickable, no query parameter is accepted. The acceptance criterion is simply unmet.

### 🟠 Medium 6 — Peer reviewers cannot open the deck they must review

**Where:** `app.py:283-284` (submission_detail), `app.py:354-355` (download), `templates/peer_review.html`.

US-2's acceptance criteria are literally satisfied (reviewer sees assignment, uploads feedback, gets confirmation), but the workflow is functionally defeated: `submission_detail` returns 403 for any student who is not the owner, `download` likewise 403s non-owner students, and `peer_review.html` shows only the submission's **filename** as text. A reviewer can therefore never actually look at the presentation they are grading. Either the review is expected to happen offline (not stated anywhere), or this is a design gap that makes US-2's feature unusable in practice.

**Fix direction:** allow students with an active `PeerAssignment` for that submission to view/download it.

### 🟠 Medium 7 — Small buttons violate the 44×44px touch-target requirement (US-6)

**Where:** `static/css/style.css:22-24`.

US-6 requires touch targets of at least 44×44px. The base rule sets buttons to `min-height/min-width: 44px` (`style.css:18-19`), but a `.btn-sm` override immediately reduces it to 36px (`style.css:22-24`). `.btn-sm` is used for the Download/Edit/Delete/View action buttons — precisely the controls a user taps on mobile. The acceptance criterion fails for these buttons.

### 🟠 Medium 8 — Batch ZIP: duplicate original filenames collide

**Where:** `app.py:391`.

```python
zf.write(file_path, arcname=sub.original_filename)
```

Two students who both upload `presentation.pdf` produce two rows with the same `original_filename`; in the ZIP, the second entry overwrites (or duplicates, depending on the tool) the first. The lecturer silently loses a submission in the batch download. Use `arcname=f"{student}_{sub.original_filename}"` or include the UUID.

### 🟠 Medium 9 — Debug server exposed on all interfaces

**Where:** `app.py:453`.

```python
app.run(debug=True, host='0.0.0.0', port=5000)
```

The Werkzeug debugger console allows **arbitrary code execution** from the browser if an exception page is reached (the console is protected only by a PIN that can be brute-forced/leaked). Combined with `host='0.0.0.0'`, this is exposed to the whole network. Fine for a local demo; unacceptable if this is ever run as written on a shared network — which a classroom demo explicitly is. Gate it behind an env var (`debug=os.environ.get('FLASK_DEBUG') == '1'`) and default `host` to `127.0.0.1`.

### 🟡 Low 10 — Oversized uploads produce a raw 413 HTML page

**Where:** `config.py:5` (`MAX_CONTENT_LENGTH`), `app.py:202`.

Flask rejects bodies over `MAX_CONTENT_LENGTH` with a plain 413 HTML error **before** the route code runs, so the friendly `request.content_length` check at `app.py:202` is unreachable for oversized files. US-7's "meaningful error message" is only met client-side (main.js) and for the edge case where `content_length` is absent. Register a `@app.errorhandler(413)` returning the flash-styled page.

### 🟡 Low 11 — `peer_review` upload lacks the explicit size check

**Where:** `app.py:223-268`.

`upload()` has an explicit `content_length` check with a flash message; `peer_review()` does not — it relies solely on the global 413 (see Low 10), so reviewers who exceed the limit get the raw error page instead of the friendly message. Inconsistent UX for the same mistake.

### 🟡 Low 12 — `document.write()` on upload success

**Where:** `static/js/main.js:75`.

`document.write(xhr.responseText)` replaces the entire document after the XHR completes. It's deprecated, blows away the page (and the browser console), and leaves the URL at `/upload` while showing dashboard content. A `window.location` redirect to the dashboard (the server already redirects on success) would be cleaner. Note: the 30s timeout (`xhr.timeout = 30000`, main.js:59) and the specific error/timeout messages (main.js:78-95) do satisfy US-7's client-side criteria.

### 🟡 Low 13 — Filename edge cases and dead code

- `main.js:5` — `ALLOWED_TYPES` (a MIME list) is dead code; the extension list `ALLOWED_EXTS` (line 6) is what's actually checked (line 11).
- `app.py:128-133` — `save_upload` builds `f"{uuid}.{ext}"`; an extensionless filename (blocked by `allowed_file`, but only because of the extension whitelist) would produce a trailing dot. Defensive, but fragile.
- `secure_filename()` returns an **empty string** for filenames made entirely of non-ASCII characters (e.g., `представление.pdf` → the ASCII part is empty). `original_filename` would then be empty, breaking the ZIP arcname and the display name. A fallback (`or stored_name`) is advisable.

### 🟡 Low 14 — Legacy `Query.get()` API (the 20 test warnings)

**Where:** e.g., `app.py:278, 353, 357, 361`.

`Submission.query.get(...)` / `get_or_404(...)` are legacy APIs in SQLAlchemy 2.x — these are the 20 `LegacyAPIWarning`s the test run reports. Replace with `db.session.get(Submission, id)` / `db.get_or_404(...)` (the code already uses the modern form in `load_user`, `app.py:140`).

### 🟡 Low 15 — Hand-rolled mixin methods and import-time side effects

**Where:** `app.py:50-59`, `app.py:449-450`.

- The `User` model hand-rolls `is_authenticated`/`is_active`/`is_anonymous`/`get_id` instead of inheriting `flask_login.UserMixin` — works, but reimplements framework behavior.
- `db.create_all()` + `seed_data()` at module level (also the root cause of High 1) means **importing** `app` mutates the filesystem and database. Any tooling that imports the module (linters with import plugins, scripts, the test suite) triggers it.

### 🟡 Low 16 — Configuration and documentation drift

- `config.py:7` — `SECRET_KEY` defaults to `'dev-secret-key-change-in-production'`; session forgery is trivial if deployed as-is.
- `config.py:8` — `os.path.join` produces backslashes, so the SQLite URI is Windows-only; on Linux the app would fail to open the DB.
- `PLAN.md` lists a `/submissions` route; the implementation uses `/dashboard` for both roles. Minor, but the plan and code disagree.

### 🟡 Low 17 — Test-quality issues

**Where:** `test_app.py:246, 272-273, 416, 433-434, 461-475`.

- `assert '0' in html` (`test_app.py:246`) — passes if *any* zero appears anywhere in the page (timestamps, IDs, CSS).
- Or-chains like `assert ('...' in html) or ('...' in html)` (`test_app.py:272-273, 416, 433-434`) — can pass on the wrong branch, hiding regressions.
- Tests assert on **JavaScript source text**, not behavior: `assert 'xhr.timeout = 30000' in js`, `assert 'ALLOWED_EXTS' in js`, `assert '50 * 1024 * 1024' in js` (`test_app.py:461-475`). Renaming a variable or reformatting a constant breaks the test without any behavior change — and conversely, a behavior regression that keeps the text intact passes. These are change-detector tests.
- The suite disables CSRF (`test_app.py:35`) and therefore never exercises token validation (see High 3).

---

## User-Story Compliance Assessment

| Story | Verdict | Notes |
|-------|---------|-------|
| **US-1** Upload (PDF/PPTX/PPT, ≤50 MB, progress bar, confirmation) | ⚠️ Pass with caveats | Upload, whitelist, size cap, progress bar with % and MB, and confirmation all work. Caveats: no CSRF (High 3), raw 413 page for oversized files (Low 10), `document.write` on success (Low 12). Note: the AC "50 MB in 10 s @ 10 Mbps" is physically impossible (a 50 MB file needs ≥40 s at 10 Mbps) — a requirements error, not an app defect. |
| **US-2** Peer review (see assignment, upload feedback, confirmation) | ⚠️ Pass literally, fail in spirit | All three ACs pass, but the reviewer can never open the deck being reviewed (Medium 6) — the feature's purpose is defeated. No CSRF on the review upload (High 3). |
| **US-3** Lecturer dashboard (detail view, inline preview, sortable list) | ❌ Fail | Inline preview broken (High 2); sortable list not implemented at all (Medium 5). Detail view itself works. |
| **US-4** Secure storage (random names, original preserved, download with original name) | ✅ Pass | UUID storage, `original_filename` preserved, downloads use the original name, path traversal is not possible (UUID names + `send_from_directory`). Edge cases in Low 13. |
| **US-5** Feedback (text feedback on submissions) | ⚠️ Pass with caveats | Add/edit/delete feedback all work with flash confirmations. Edit/delete lack CSRF (High 3); edit/delete buttons are 36px (Medium 7). |
| **US-6** Mobile responsive (no horizontal scroll, ≥44px targets) | ⚠️ Partial | Card layout for mobile submission lists is genuinely good; no horizontal scrolling observed. But `.btn-sm` buttons are 36px (Medium 7) — the AC fails for exactly the buttons users tap most. |
| **US-7** Performance (20 MB in 10 s, 30 s timeout, meaningful errors) | ⚠️ Pass with caveats | 30 s XHR timeout and specific client-side error/timeout messages are implemented (main.js:59, 78-95). Server-side oversized-upload error is a raw 413 page (Low 10). US-1's 50 MB/10 s figure remains impossible regardless. |

---

## Security Summary

| Area | Status |
|------|--------|
| Path traversal | ✅ Safe — UUID filenames, `send_from_directory` |
| XSS | ✅ Safe — Jinja auto-escaping throughout |
| AuthN/AuthZ | ✅ Route guards + role checks on every route; 403s verified |
| CSRF | ❌ Missing on 5 of 7 mutating routes (High 3) |
| Secret key | ⚠️ Hardcoded dev default (Low 16) |
| Debug server | ❌ `debug=True` on `0.0.0.0` — debugger RCE exposure (Medium 9) |
| Password storage | ✅ `generate_password_hash`/`check_password_hash` (Werkzeug) |

---

## Test Suite Assessment

- **52 tests, 20 warnings, ~26 s** — reproduces the `WORKLOG_TEST.md` claim exactly.
- Coverage spans all 7 user stories, including auth, permissions (403s), deadline lockout, and JS source checks.
- **Critical flaw:** the suite is not isolated and destroys the development DB (High 1) — proven during this review; the local `portal.db` was wiped by the verification run.
- **Quality flaw:** several assertions test implementation text rather than behavior (Low 17), and CSRF is disabled globally in tests, so the biggest security gap is untested.

---

## Positives Worth Keeping

- **Path-traversal-safe file handling** — UUID storage names + `send_from_directory` + extension whitelist is the right pattern.
- **Consistent authorization** — every route checks `login_required` and the correct role; ownership checks on detail/download; deadline lockout works (`app.py:228-231`).
- **Genuinely responsive submissions list** — table on ≥md, cards on mobile (`d-md-none`), no horizontal scroll.
- **Thoughtful upload UX** — client-side validation before the request, XHR progress bar with percentage and MB counters, specific timeout/error messages.
- **Sensible model design** — `Submission`/`PeerAssignment`/`Feedback` with FKs; seed data with a guard against double-seeding.
- **Honest worklogs** — `WORKLOG.md`/`WORKLOG_TEST.md` accurately describe known gaps (dummy.pdf) and the test results.

---

## Merge Recommendation

**Request changes.** Minimum set to clear before merge:

1. Fix test isolation (High 1) — this is actively destructive to developers' environments.
2. Fix the inline preview (High 2) — it's a named acceptance criterion.
3. Add CSRF to the five unprotected routes (High 3) — it was promised in `PLAN.md`.
4. Seed a real `dummy.pdf` (High 4) — the demo's first click currently 404s.

Strongly recommended in the same pass: the peer-review visibility fix (Medium 6), the 44px touch targets (Medium 7), and gating `debug=True` (Medium 9). The remaining Medium/Low items can be follow-ups.

*Review prepared without modifying any application code. The `portal.db` wiped during empirical verification was an empty (already table-less) file; a pre-review backup exists at `%TEMP%\portal_backup.db`.*
