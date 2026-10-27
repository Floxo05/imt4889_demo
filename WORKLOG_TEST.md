# Worklog: Automated Tests for Course Portal

## Date
2026-10-27

## Goal
Write and run automated tests for the Flask-based Course Portal application, covering all 7 user stories from PROMPT.md.

## Approach
1. Analyse the application code (`app.py`, templates, JS) and the user stories.
2. Install `pytest` as the test runner.
3. Create `test_app.py` with test classes organised by user story (US-1 … US-7) plus a general auth class.
4. Use Flask's `test_client` with an isolated test database and upload folder.
5. Run tests iteratively, fix test bugs and application bugs, then re-run until green.

## Test Structure

| Test Class | User Story | # Tests | Key Areas |
|------------|-----------|---------|-----------|
| `TestUS1_UploadLectureSlides` | US-1 | 9 | File type validation, size limits, dashboard display, form markup |
| `TestUS2_UploadPeerReview` | US-2 | 6 | Linked assignments, deadline blocking, lecturer visibility |
| `TestUS3_ViewSubmissions` | US-3 | 6 | Lecturer list, detail view, student access control, responsive classes |
| `TestUS4_DownloadSubmissions` | US-4 | 6 | Individual download, batch ZIP, filename preservation, access control |
| `TestUS5_LeaveFeedback` | US-5 | 7 | Add/edit/delete feedback, student visibility, empty rejection |
| `TestUS6_MobileAccess` | US-6 | 6 | Viewport meta tag, touch targets, responsive grid, navbar toggler |
| `TestUS7_UploadPerformance` | US-7 | 7 | Client-side validation script, progress bar, XHR timeout, file accept attr |
| `TestAuth` | General | 5 | Login/logout, valid/invalid credentials, unauthenticated redirect |

**Total: 52 tests**

## Issues Found & Fixed

### 1. Test fixture: missing upload directory
- **Symptom:** `FileNotFoundError` on every file upload test.
- **Fix:** Added `os.makedirs(TEST_UPLOAD_FOLDER, exist_ok=True)` in the `client` fixture.

### 2. Test fixture: missing seeded file on disk
- **Symptom:** Download tests returned 404 because `dummy.pdf` existed in the DB but not on disk.
- **Fix:** Created a real `dummy.pdf` file in `TEST_UPLOAD_FOLDER` during fixture setup.

### 3. Application bug: naive vs aware datetime comparison
- **Symptom:** `TypeError: can't compare offset-naive and offset-aware datetimes` in `peer_review()`.
- **Fix:** Changed `datetime.now(timezone.utc) > assignment.deadline` to `datetime.now(timezone.utc).replace(tzinfo=None) > assignment.deadline` in `app.py:230`.

### 4. Application bug: broken batch download
- **Symptom:** `send_from_directory(directory='', path='')` caused errors.
- **Fix:** Replaced with `send_file(memory_file, as_attachment=True, download_name=..., mimetype='application/zip')` in `app.py`.

### 5. Test bug: wrong user IDs in assertions
- **Symptom:** Peer-review lookup by `reviewer_id=2` failed because seeded IDs are lecturer=1, student1=2, student2=3, student3=4.
- **Fix:** Updated assertions to use `reviewer_id=3` for student2.

### 6. Test bug: SQLAlchemy detached instance errors
- **Symptom:** Accessing `sub.id` or `fb.id` outside the `app.app_context()` block raised `DetachedInstanceError`.
- **Fix:** Captured IDs inside the context block into local Python variables before using them in client requests.

### 7. Test bug: Flask app context nesting
- **Symptom:** `AssertionError: Popped wrong app context` when mixing `app.app_context()` with `client.post()` inside the same block.
- **Fix:** Separated DB queries (inside `app.app_context()`) from HTTP requests (outside the context).

### 8. Test bug: responsive class assertion too strict
- **Symptom:** Lecturer dashboard uses `table-responsive` / `d-md-none` instead of Bootstrap grid columns.
- **Fix:** Broadened assertion to accept `table-responsive` or `d-md-none` as valid responsive patterns.

## Final Results

```
====================== 52 passed, 20 warnings in 27.40s ======================
```

All 52 tests pass. The 20 warnings are SQLAlchemy 2.0 legacy warnings (`Query.get()`), which do not affect functionality.

## Files Created / Modified

- **Created:** `test_app.py` — 52 automated tests
- **Modified:** `app.py` — 2 bug fixes (datetime comparison, batch download)
