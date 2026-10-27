"""
Automated tests for the Course Portal application.
Tests are organised by user story (US-1 … US-7).
"""

import io
import os
import sys
import zipfile
from datetime import datetime, timezone, timedelta

import pytest

# Ensure the app module is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db, User, Submission, PeerReview, Feedback, PeerAssignment, seed_data
from werkzeug.security import generate_password_hash

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TEST_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_portal.db')
TEST_UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_uploads')


@pytest.fixture
def client():
    """Flask test client with isolated test DB and upload folder."""
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{TEST_DB_PATH}'
    app.config['UPLOAD_FOLDER'] = TEST_UPLOAD_FOLDER
    app.config['WTF_CSRF_ENABLED'] = False  # disable CSRF for easier form posts
    app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

    with app.test_client() as client:
        with app.app_context():
            os.makedirs(TEST_UPLOAD_FOLDER, exist_ok=True)
            db.create_all()
            seed_data()
            yield client
            db.session.remove()
            db.drop_all()

    # Cleanup test artefacts
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
    if os.path.exists(TEST_UPLOAD_FOLDER):
        for f in os.listdir(TEST_UPLOAD_FOLDER):
            os.remove(os.path.join(TEST_UPLOAD_FOLDER, f))
        os.rmdir(TEST_UPLOAD_FOLDER)


@pytest.fixture
def lecturer(client):
    """Return the seeded lecturer user."""
    with app.app_context():
        return User.query.filter_by(username='lecturer').first()


@pytest.fixture
def students(client):
    """Return the seeded student users."""
    with app.app_context():
        return User.query.filter_by(role='student').all()


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def login(client, username, password='demo123'):
    return client.post('/login', data={'username': username, 'password': password}, follow_redirects=True)


def logout(client):
    return client.get('/logout', follow_redirects=True)


def make_file(filename='slides.pdf', content=b'%PDF-1.4 test content', size=None):
    """Build a FileStorage-like object for multipart uploads."""
    data = content if size is None else (content * (size // len(content) + 1))[:size]
    return (io.BytesIO(data), filename)


# =============================================================================
# US-1: Upload Lecture Slides
# =============================================================================

class TestUS1_UploadLectureSlides:
    """Acceptance criteria for US-1."""

    def test_student_can_access_upload_page(self, client):
        login(client, 'student1')
        resp = client.get('/upload')
        assert resp.status_code == 200

    def test_lecturer_cannot_access_upload_page(self, client):
        login(client, 'lecturer')
        resp = client.get('/upload')
        assert resp.status_code == 403

    def test_upload_pdf_succeeds(self, client):
        login(client, 'student1')
        file = make_file('slides.pdf')
        resp = client.post('/upload', data={'file': file}, content_type='multipart/form-data', follow_redirects=True)
        assert resp.status_code == 200
        assert b'uploaded successfully' in resp.data

    def test_upload_pptx_succeeds(self, client):
        login(client, 'student1')
        file = make_file('slides.pptx', b'PK\x03\x04 pptx content')
        resp = client.post('/upload', data={'file': file}, content_type='multipart/form-data', follow_redirects=True)
        assert resp.status_code == 200
        assert b'uploaded successfully' in resp.data

    def test_upload_ppt_succeeds(self, client):
        login(client, 'student1')
        file = make_file('slides.ppt', b'\xd0\xcf\x11\xe0 ppt content')
        resp = client.post('/upload', data={'file': file}, content_type='multipart/form-data', follow_redirects=True)
        assert resp.status_code == 200
        assert b'uploaded successfully' in resp.data

    def test_upload_invalid_type_rejected(self, client):
        login(client, 'student1')
        file = make_file('slides.exe', b'exe content')
        resp = client.post('/upload', data={'file': file}, content_type='multipart/form-data', follow_redirects=True)
        assert b'Invalid file type' in resp.data

    def test_upload_empty_filename_rejected(self, client):
        login(client, 'student1')
        file = (io.BytesIO(b''), '')
        resp = client.post('/upload', data={'file': file}, content_type='multipart/form-data', follow_redirects=True)
        assert b'No file selected' in resp.data

    def test_dashboard_shows_submission_details(self, client):
        login(client, 'student1')
        file = make_file('slides.pdf')
        client.post('/upload', data={'file': file}, content_type='multipart/form-data', follow_redirects=True)

        resp = client.get('/dashboard')
        assert resp.status_code == 200
        assert b'slides.pdf' in resp.data
        assert b'Submitted' in resp.data
        # Timestamp should be present (we just uploaded)
        html = resp.data.decode()
        assert datetime.now().strftime('%Y-%m-%d') in html

    def test_upload_form_has_accept_attribute(self, client):
        login(client, 'student1')
        resp = client.get('/upload')
        assert b'accept=".pdf,.pptx,.ppt"' in resp.data


# =============================================================================
# US-2: Upload Peer Review
# =============================================================================

class TestUS2_UploadPeerReview:
    """Acceptance criteria for US-2."""

    def test_student_sees_peer_assignment_on_dashboard(self, client):
        login(client, 'student2')
        resp = client.get('/dashboard')
        assert resp.status_code == 200
        # student2 is assigned to review student1's dummy submission
        assert b'Upload Peer Review' in resp.data or b'View / Update Review' in resp.data

    def test_student_can_upload_peer_review(self, client):
        login(client, 'student2')
        # student2 is assigned to submission_id=1 (dummy submission)
        file = make_file('review.pdf')
        resp = client.post('/peer-review/1', data={'file': file}, content_type='multipart/form-data', follow_redirects=True)
        assert resp.status_code == 200
        assert b'uploaded successfully' in resp.data

    def test_peer_review_linked_to_submission(self, client):
        login(client, 'student2')
        file = make_file('review.pdf')
        client.post('/peer-review/1', data={'file': file}, content_type='multipart/form-data', follow_redirects=True)

        with app.app_context():
            # student2 has id=3 (lecturer=1, student1=2, student2=3, student3=4)
            review = PeerReview.query.filter_by(reviewer_id=3, submission_id=1).first()
            assert review is not None
            assert review.original_filename == 'review.pdf'

    def test_deadline_blocks_upload(self, client):
        with app.app_context():
            pa = PeerAssignment.query.filter_by(reviewer_id=2, submission_id=1).first()
            pa.deadline = datetime(2000, 1, 1, tzinfo=timezone.utc)
            db.session.commit()

        login(client, 'student2')
        file = make_file('review.pdf')
        resp = client.post('/peer-review/1', data={'file': file}, content_type='multipart/form-data', follow_redirects=True)
        assert b'deadline has passed' in resp.data

    def test_lecturer_sees_peer_review_on_detail_page(self, client):
        login(client, 'student2')
        file = make_file('review.pdf')
        client.post('/peer-review/1', data={'file': file}, content_type='multipart/form-data', follow_redirects=True)

        logout(client)
        login(client, 'lecturer')
        resp = client.get('/submission/1')
        assert resp.status_code == 200
        assert b'Peer Reviews' in resp.data
        assert b'review.pdf' in resp.data
        assert b'student2' in resp.data or b'Bob Jones' in resp.data

    def test_student_cannot_review_unassigned_submission(self, client):
        login(client, 'student2')
        # Try to access a non-existent assignment (submission 999)
        resp = client.get('/peer-review/999')
        assert resp.status_code == 404


# =============================================================================
# US-3: View Submissions (Lecturer)
# =============================================================================

class TestUS3_ViewSubmissions:
    """Acceptance criteria for US-3."""

    def test_lecturer_dashboard_lists_submissions(self, client):
        login(client, 'lecturer')
        resp = client.get('/dashboard')
        assert resp.status_code == 200
        # The seeded dummy submission should appear
        assert b'dummy.pdf' in resp.data
        assert b'Dr. Jane Doe' in resp.data or b'Alice Smith' in resp.data

    def test_lecturer_dashboard_shows_peer_review_count(self, client):
        login(client, 'lecturer')
        resp = client.get('/dashboard')
        assert resp.status_code == 200
        # dummy submission has 0 peer reviews initially
        html = resp.data.decode()
        assert '0' in html  # peer review count column

    def test_lecturer_can_view_submission_detail(self, client):
        login(client, 'lecturer')
        resp = client.get('/submission/1')
        assert resp.status_code == 200
        assert b'dummy.pdf' in resp.data
        assert b'Peer Reviews' in resp.data
        assert b'Lecturer Feedback' in resp.data

    def test_student_cannot_view_other_student_submission(self, client):
        login(client, 'student2')
        resp = client.get('/submission/1')
        # student1 owns submission 1, student2 should be blocked
        assert resp.status_code == 403

    def test_student_can_view_own_submission(self, client):
        login(client, 'student1')
        resp = client.get('/submission/1')
        assert resp.status_code == 200

    def test_mobile_responsive_classes_present(self, client):
        login(client, 'lecturer')
        resp = client.get('/dashboard')
        html = resp.data.decode()
        # Bootstrap responsive classes should be present
        assert 'table-responsive' in html or 'd-md-none' in html
        assert 'card' in html


# =============================================================================
# US-4: Download Submissions
# =============================================================================

class TestUS4_DownloadSubmissions:
    """Acceptance criteria for US-4."""

    def test_lecturer_can_download_submission(self, client):
        login(client, 'lecturer')
        resp = client.get('/download/submission/1')
        assert resp.status_code == 200
        assert resp.headers.get('Content-Disposition', '').startswith('attachment')
        assert 'dummy.pdf' in resp.headers.get('Content-Disposition', '')

    def test_student_can_download_own_submission(self, client):
        login(client, 'student1')
        resp = client.get('/download/submission/1')
        assert resp.status_code == 200

    def test_student_cannot_download_other_submission(self, client):
        # First create a submission for student1
        with app.app_context():
            sub = Submission(student_id=1, filename='s1.pdf', original_filename='s1.pdf')
            db.session.add(sub)
            db.session.commit()

        login(client, 'student2')
        resp = client.get(f'/download/submission/{sub.id}')
        assert resp.status_code == 403

    def test_batch_download_generates_zip(self, client):
        login(client, 'lecturer')
        resp = client.post('/download-batch', data={'submission_ids': ['1']}, follow_redirects=True)
        assert resp.status_code == 200
        # Should be a ZIP file
        assert resp.headers.get('Content-Disposition', '').startswith('attachment')
        assert '.zip' in resp.headers.get('Content-Disposition', '')

    def test_batch_download_requires_selection(self, client):
        login(client, 'lecturer')
        resp = client.post('/download-batch', data={}, follow_redirects=True)
        assert b'No submissions selected' in resp.data

    def test_student_cannot_batch_download(self, client):
        login(client, 'student1')
        resp = client.post('/download-batch', data={'submission_ids': ['1']})
        assert resp.status_code == 403


# =============================================================================
# US-5: Leave Feedback on Submission
# =============================================================================

class TestUS5_LeaveFeedback:
    """Acceptance criteria for US-5."""

    def test_lecturer_can_add_feedback(self, client):
        login(client, 'lecturer')
        resp = client.post('/feedback/1', data={'content': 'Great work!'}, follow_redirects=True)
        assert resp.status_code == 200
        assert b'Feedback saved' in resp.data

    def test_feedback_appears_on_detail_page(self, client):
        login(client, 'lecturer')
        client.post('/feedback/1', data={'content': 'Great work!'}, follow_redirects=True)

        resp = client.get('/submission/1')
        assert b'Great work!' in resp.data

    def test_student_sees_feedback_on_own_submission(self, client):
        login(client, 'lecturer')
        client.post('/feedback/1', data={'content': 'Well done!'}, follow_redirects=True)

        logout(client)
        login(client, 'student1')
        resp = client.get('/submission/1')
        assert b'Well done!' in resp.data

    def test_lecturer_can_edit_feedback(self, client):
        login(client, 'lecturer')
        client.post('/feedback/1', data={'content': 'Initial feedback'}, follow_redirects=True)

        with app.app_context():
            fb = Feedback.query.filter_by(submission_id=1).first()
            resp = client.post(f'/feedback/{fb.id}/edit', data={'content': 'Updated feedback'}, follow_redirects=True)
            assert resp.status_code == 200
            assert b'Feedback updated' in resp.data

    def test_lecturer_can_delete_feedback(self, client):
        login(client, 'lecturer')
        client.post('/feedback/1', data={'content': 'To be deleted'}, follow_redirects=True)

        with app.app_context():
            fb = Feedback.query.filter_by(submission_id=1).first()
            resp = client.post(f'/feedback/{fb.id}/delete', follow_redirects=True)
            assert resp.status_code == 200
            assert b'Feedback deleted' in resp.data

    def test_student_cannot_add_feedback(self, client):
        login(client, 'student1')
        resp = client.post('/feedback/1', data={'content': 'Student feedback'})
        assert resp.status_code == 403

    def test_empty_feedback_rejected(self, client):
        login(client, 'lecturer')
        resp = client.post('/feedback/1', data={'content': ''}, follow_redirects=True)
        assert b'Feedback cannot be empty' in resp.data


# =============================================================================
# US-6: Access Portal on a Phone
# =============================================================================

class TestUS6_MobileAccess:
    """Acceptance criteria for US-6."""

    def test_viewport_meta_tag_present(self, client):
        resp = client.get('/login')
        assert b'<meta name="viewport"' in resp.data
        assert b'width=device-width, initial-scale=1' in resp.data

    def test_touch_target_css_class_exists(self, client):
        login(client, 'student1')
        resp = client.get('/dashboard')
        html = resp.data.decode()
        # The touch-btn class is used for minimum touch target sizing
        assert 'touch-btn' in html

    def test_responsive_grid_classes_present(self, client):
        login(client, 'student1')
        resp = client.get('/dashboard')
        html = resp.data.decode()
        assert 'col-12' in html or 'col-md-' in html or 'col-lg-' in html

    def test_navbar_has_toggler_for_mobile(self, client):
        resp = client.get('/login')
        assert b'navbar-toggler' in resp.data
        assert b'navbar-collapse' in resp.data

    def test_upload_page_responsive(self, client):
        login(client, 'student1')
        resp = client.get('/upload')
        html = resp.data.decode()
        assert 'col-12' in html and 'col-md-' in html

    def test_submission_list_has_card_view_for_mobile(self, client):
        login(client, 'lecturer')
        resp = client.get('/dashboard')
        html = resp.data.decode()
        assert 'd-md-none' in html  # card view shown only on mobile
        assert 'table-responsive' in html or 'd-none d-md-block' in html  # table hidden on mobile


# =============================================================================
# US-7: Fast Upload Performance
# =============================================================================

class TestUS7_UploadPerformance:
    """Acceptance criteria for US-7."""

    def test_client_side_validation_script_present(self, client):
        login(client, 'student1')
        resp = client.get('/upload')
        html = resp.data.decode()
        assert 'main.js' in html

    def test_progress_bar_markup_present(self, client):
        login(client, 'student1')
        resp = client.get('/upload')
        html = resp.data.decode()
        assert 'progress' in html
        assert 'progress-bar' in html
        assert 'progressWrapper' in html

    def test_xhr_timeout_set_to_30s(self, client):
        resp = client.get('/static/js/main.js')
        js = resp.data.decode()
        assert 'xhr.timeout = 30000' in js

    def test_client_side_file_type_validation(self, client):
        resp = client.get('/static/js/main.js')
        js = resp.data.decode()
        assert 'ALLOWED_EXTS' in js
        assert "'pdf'" in js
        assert "'pptx'" in js
        assert "'ppt'" in js

    def test_client_side_file_size_validation(self, client):
        resp = client.get('/static/js/main.js')
        js = resp.data.decode()
        assert 'MAX_SIZE' in js
        assert '50 * 1024 * 1024' in js

    def test_upload_form_has_file_accept_attribute(self, client):
        login(client, 'student1')
        resp = client.get('/upload')
        assert b'accept=".pdf,.pptx,.ppt"' in resp.data

    def test_peer_review_has_same_progress_markup(self, client):
        login(client, 'student2')
        resp = client.get('/peer-review/1')
        html = resp.data.decode()
        assert 'progress' in html
        assert 'progress-bar' in html


# =============================================================================
# Auth & General
# =============================================================================

class TestAuth:
    """Basic authentication flows."""

    def test_login_page_loads(self, client):
        resp = client.get('/login')
        assert resp.status_code == 200
        assert b'Login' in resp.data or b'Username' in resp.data

    def test_valid_login_redirects_to_dashboard(self, client):
        resp = login(client, 'student1')
        assert resp.status_code == 200
        assert b'Dashboard' in resp.data or b'My Submissions' in resp.data

    def test_invalid_login_shows_error(self, client):
        resp = client.post('/login', data={'username': 'student1', 'password': 'wrong'}, follow_redirects=True)
        assert b'Invalid username or password' in resp.data

    def test_logout_redirects_to_login(self, client):
        login(client, 'student1')
        resp = logout(client)
        assert resp.status_code == 200
        # Should be on login page or show login link
        assert b'Login' in resp.data or b'logged out' in resp.data

    def test_unauthenticated_user_redirected_from_dashboard(self, client):
        resp = client.get('/dashboard', follow_redirects=True)
        assert b'Please log in' in resp.data or b'Login' in resp.data
