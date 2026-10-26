# Implementation Plan — Course Portal

## Overview
Build a responsive Flask web portal where students upload lecture slides and peer reviews, and lecturers view, download, and leave feedback on submissions.

## Tech Stack
- **Backend:** Python 3, Flask, Flask-Login, Flask-WTF, Werkzeug
- **Database:** SQLite (via `flask_sqlalchemy`)
- **Frontend:** Bootstrap 5, vanilla JavaScript
- **File Storage:** Local filesystem (`uploads/` directory)

## Database Schema

### `users`
| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | |
| username | String(80) unique | |
| email | String(120) unique | |
| password_hash | String(256) | Werkzeug generate_password_hash |
| role | String(20) | `lecturer` or `student` |
| display_name | String(120) | Full name shown in UI |

### `submissions`
| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | |
| student_id | FK → users.id | |
| filename | String(255) | Stored filename (UUID) |
| original_filename | String(255) | Original upload name |
| upload_timestamp | DateTime | UTC, auto-set |
| status | String(20) | `Submitted` |

### `peer_reviews`
| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | |
| reviewer_id | FK → users.id | Student who wrote review |
| submission_id | FK → submissions.id | Which slide deck is reviewed |
| filename | String(255) | Stored filename (UUID) |
| original_filename | String(255) | Original upload name |
| upload_timestamp | DateTime | UTC, auto-set |

### `feedback`
| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | |
| submission_id | FK → submissions.id | |
| lecturer_id | FK → users.id | |
| content | Text | |
| created_at | DateTime | |
| updated_at | DateTime | |

### `peer_assignments`
| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | |
| reviewer_id | FK → users.id | |
| submission_id | FK → submissions.id | |
| deadline | DateTime | Peer review deadline |

## File Structure
```
app.py              — Application factory, routes, models
config.py           — Configuration (secret key, upload limits, etc.)
requirements.txt    — Python dependencies
README.md           — Setup & run instructions
PLAN.md             — This file
static/
  css/
    style.css       — Custom responsive overrides
  js/
    main.js         — Client-side validation, progress bar, mobile helpers
templates/
  base.html         — Bootstrap layout with responsive nav
  login.html        — Login form
  dashboard.html    — Student / lecturer dashboard
  upload.html       — Slide upload form
  peer_review.html  — Peer review upload form
  submission_detail.html — Detail view with preview, feedback, peer reviews
  submissions_list.html  — Lecturer sortable list
uploads/            — Created at runtime; stores all files
```

## Route Plan

| Route | Method | Role | Purpose |
|-------|--------|------|---------|
| `/login` | GET/POST | any | Authentication |
| `/logout` | GET | any | Log out |
| `/dashboard` | GET | any | Role-based landing page |
| `/upload` | GET/POST | student | Upload lecture slides |
| `/peer-review/<id>` | GET/POST | student | Upload peer review for assigned submission |
| `/submissions` | GET | lecturer | List all submissions |
| `/submission/<id>` | GET | any | Detail view (lecturer sees all, student sees own + feedback) |
| `/download/<type>/<id>` | GET | any | Download file (`type` = submission or review) |
| `/download-batch` | POST | lecturer | ZIP download of selected submissions |
| `/feedback/<submission_id>` | POST | lecturer | Add/edit feedback |
| `/delete-feedback/<id>` | POST | lecturer | Delete feedback |

## Responsive / Mobile Strategy
- Bootstrap 5 grid + utility classes
- Custom `style.css` for touch targets (min 44×44 px) and table-to-card reflow
- Viewport meta tag: `width=device-width, initial-scale=1`
- File input styled as large button for easy touch
- Feedback textarea scrollable, save button stays visible below keyboard

## Client-Side Optimisations (US-7)
- JavaScript validates file type (`accept` + manual check) and size before `fetch()`
- `XMLHttpRequest` with `progress` event for animated progress bar
- Upload timeout set to 30 s; meaningful error messages on failure

## Demo Data (seed on first run)
- **Lecturer:** `lecturer` / `demo123` — Dr. Jane Doe
- **Students:**
  - `student1` / `demo123` — Alice Smith
  - `student2` / `demo123` — Bob Jones
  - `student3` / `demo123` — Carol White
- Pre-created peer assignments so peer-review flow works immediately.

## Implementation Order
1. `config.py` + `requirements.txt`
2. `app.py` — models, auth, routes
3. Templates + `static/css/style.css` + `static/js/main.js`
4. Seed demo data
5. Test all user stories manually
6. Write `README.md`
