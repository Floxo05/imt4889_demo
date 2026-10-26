import os
import uuid
import zipfile
from datetime import datetime, timezone
from io import BytesIO

from flask import (
    Flask, render_template, request, redirect, url_for, flash,
    send_from_directory, abort, jsonify
)
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from wtforms import StringField, PasswordField, TextAreaField, SelectField
from wtforms.validators import DataRequired

import config

app = Flask(__name__)
app.config.from_object(config)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='student')
    display_name = db.Column(db.String(120), nullable=False)

    submissions = db.relationship('Submission', backref='student', lazy=True)
    reviews = db.relationship('PeerReview', backref='reviewer', lazy=True)
    feedbacks = db.relationship('Feedback', backref='lecturer', lazy=True)

    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)


class Submission(db.Model):
    __tablename__ = 'submissions'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    upload_timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    status = db.Column(db.String(20), default='Submitted')

    peer_reviews = db.relationship('PeerReview', backref='submission', lazy=True, cascade='all, delete-orphan')
    feedbacks = db.relationship('Feedback', backref='submission', lazy=True, cascade='all, delete-orphan')
    assignments = db.relationship('PeerAssignment', backref='submission', lazy=True, cascade='all, delete-orphan')


class PeerReview(db.Model):
    __tablename__ = 'peer_reviews'
    id = db.Column(db.Integer, primary_key=True)
    reviewer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    submission_id = db.Column(db.Integer, db.ForeignKey('submissions.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    upload_timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class Feedback(db.Model):
    __tablename__ = 'feedback'
    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey('submissions.id'), nullable=False)
    lecturer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class PeerAssignment(db.Model):
    __tablename__ = 'peer_assignments'
    id = db.Column(db.Integer, primary_key=True)
    reviewer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    submission_id = db.Column(db.Integer, db.ForeignKey('submissions.id'), nullable=False)
    deadline = db.Column(db.DateTime, nullable=False)

    reviewer = db.relationship('User', backref='assignments')


# ---------------------------------------------------------------------------
# Forms
# ---------------------------------------------------------------------------

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])


class FeedbackForm(FlaskForm):
    content = TextAreaField('Feedback', validators=[DataRequired()])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


def save_upload(file_obj):
    ext = file_obj.filename.rsplit('.', 1)[1].lower() if '.' in file_obj.filename else ''
    stored_name = f"{uuid.uuid4().hex}.{ext}"
    path = os.path.join(app.config['UPLOAD_FOLDER'], stored_name)
    file_obj.save(path)
    return stored_name, secure_filename(file_obj.filename)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ---------------------------------------------------------------------------
# Routes — Auth
# ---------------------------------------------------------------------------

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and check_password_hash(user.password_hash, form.password.data):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid username or password.', 'danger')
    return render_template('login.html', form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


# ---------------------------------------------------------------------------
# Routes — Dashboard
# ---------------------------------------------------------------------------

@app.route('/')
@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'lecturer':
        submissions = Submission.query.order_by(Submission.upload_timestamp.desc()).all()
        return render_template('submissions_list.html', submissions=submissions)
    else:
        my_submissions = Submission.query.filter_by(student_id=current_user.id).order_by(Submission.upload_timestamp.desc()).all()
        assignments = PeerAssignment.query.filter_by(reviewer_id=current_user.id).all()
        return render_template('dashboard.html', submissions=my_submissions, assignments=assignments)


# ---------------------------------------------------------------------------
# Routes — Student Upload
# ---------------------------------------------------------------------------

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if current_user.role != 'student':
        abort(403)
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part.', 'danger')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('No file selected.', 'danger')
            return redirect(request.url)
        if not allowed_file(file.filename):
            flash('Invalid file type. Only PDF, PPTX, and PPT are allowed.', 'danger')
            return redirect(request.url)
        if request.content_length and request.content_length > app.config['MAX_CONTENT_LENGTH']:
            flash('File too large. Maximum size is 50 MB.', 'danger')
            return redirect(request.url)
        stored_name, orig_name = save_upload(file)
        sub = Submission(
            student_id=current_user.id,
            filename=stored_name,
            original_filename=orig_name,
            status='Submitted'
        )
        db.session.add(sub)
        db.session.commit()
        flash('File uploaded successfully!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('upload.html')


# ---------------------------------------------------------------------------
# Routes — Peer Review
# ---------------------------------------------------------------------------

@app.route('/peer-review/<int:submission_id>', methods=['GET', 'POST'])
@login_required
def peer_review(submission_id):
    if current_user.role != 'student':
        abort(403)
    assignment = PeerAssignment.query.filter_by(reviewer_id=current_user.id, submission_id=submission_id).first_or_404()
    existing = PeerReview.query.filter_by(reviewer_id=current_user.id, submission_id=submission_id).first()
    deadline_passed = datetime.now(timezone.utc) > assignment.deadline

    if request.method == 'POST':
        if deadline_passed:
            flash('The peer review deadline has passed.', 'warning')
            return redirect(url_for('dashboard'))
        if 'file' not in request.files:
            flash('No file part.', 'danger')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('No file selected.', 'danger')
            return redirect(request.url)
        if not allowed_file(file.filename):
            flash('Invalid file type. Only PDF, PPTX, and PPT are allowed.', 'danger')
            return redirect(request.url)
        stored_name, orig_name = save_upload(file)
        if existing:
            # Overwrite previous review file
            old_path = os.path.join(app.config['UPLOAD_FOLDER'], existing.filename)
            if os.path.exists(old_path):
                os.remove(old_path)
            existing.filename = stored_name
            existing.original_filename = orig_name
            existing.upload_timestamp = datetime.now(timezone.utc)
        else:
            review = PeerReview(
                reviewer_id=current_user.id,
                submission_id=submission_id,
                filename=stored_name,
                original_filename=orig_name
            )
            db.session.add(review)
        db.session.commit()
        flash('Peer review uploaded successfully!', 'success')
        return redirect(url_for('dashboard'))

    target_sub = Submission.query.get_or_404(submission_id)
    return render_template('peer_review.html', assignment=assignment, submission=target_sub, existing=existing, deadline_passed=deadline_passed)


# ---------------------------------------------------------------------------
# Routes — Submission Detail
# ---------------------------------------------------------------------------

@app.route('/submission/<int:submission_id>')
@login_required
def submission_detail(submission_id):
    sub = Submission.query.get_or_404(submission_id)
    if current_user.role == 'student' and sub.student_id != current_user.id:
        abort(403)
    reviews = PeerReview.query.filter_by(submission_id=submission_id).all()
    feedback_list = Feedback.query.filter_by(submission_id=submission_id).order_by(Feedback.created_at.desc()).all()
    feedback_form = FeedbackForm()
    return render_template('submission_detail.html', submission=sub, reviews=reviews, feedback_list=feedback_list, feedback_form=feedback_form)


# ---------------------------------------------------------------------------
# Routes — Feedback
# ---------------------------------------------------------------------------

@app.route('/feedback/<int:submission_id>', methods=['POST'])
@login_required
def add_feedback(submission_id):
    if current_user.role != 'lecturer':
        abort(403)
    form = FeedbackForm()
    if form.validate_on_submit():
        fb = Feedback(
            submission_id=submission_id,
            lecturer_id=current_user.id,
            content=form.content.data
        )
        db.session.add(fb)
        db.session.commit()
        flash('Feedback saved.', 'success')
    else:
        flash('Feedback cannot be empty.', 'danger')
    return redirect(url_for('submission_detail', submission_id=submission_id))


@app.route('/feedback/<int:feedback_id>/edit', methods=['POST'])
@login_required
def edit_feedback(feedback_id):
    if current_user.role != 'lecturer':
        abort(403)
    fb = Feedback.query.get_or_404(feedback_id)
    if fb.lecturer_id != current_user.id:
        abort(403)
    new_content = request.form.get('content', '').strip()
    if not new_content:
        flash('Feedback cannot be empty.', 'danger')
        return redirect(url_for('submission_detail', submission_id=fb.submission_id))
    fb.content = new_content
    fb.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    flash('Feedback updated.', 'success')
    return redirect(url_for('submission_detail', submission_id=fb.submission_id))


@app.route('/feedback/<int:feedback_id>/delete', methods=['POST'])
@login_required
def delete_feedback(feedback_id):
    if current_user.role != 'lecturer':
        abort(403)
    fb = Feedback.query.get_or_404(feedback_id)
    if fb.lecturer_id != current_user.id:
        abort(403)
    sub_id = fb.submission_id
    db.session.delete(fb)
    db.session.commit()
    flash('Feedback deleted.', 'info')
    return redirect(url_for('submission_detail', submission_id=sub_id))


# ---------------------------------------------------------------------------
# Routes — Download
# ---------------------------------------------------------------------------

@app.route('/download/<string:doc_type>/<int:doc_id>')
@login_required
def download(doc_type, doc_id):
    if doc_type == 'submission':
        doc = Submission.query.get_or_404(doc_id)
        if current_user.role == 'student' and doc.student_id != current_user.id:
            abort(403)
    elif doc_type == 'review':
        doc = PeerReview.query.get_or_404(doc_id)
        if current_user.role == 'student' and doc.reviewer_id != current_user.id:
            # Allow if the student is the submission owner viewing received reviews
            sub = Submission.query.get(doc.submission_id)
            if sub.student_id != current_user.id:
                abort(403)
    else:
        abort(404)
    return send_from_directory(
        app.config['UPLOAD_FOLDER'],
        doc.filename,
        as_attachment=True,
        download_name=doc.original_filename
    )


@app.route('/download-batch', methods=['POST'])
@login_required
def download_batch():
    if current_user.role != 'lecturer':
        abort(403)
    ids = request.form.getlist('submission_ids')
    if not ids:
        flash('No submissions selected.', 'warning')
        return redirect(url_for('dashboard'))
    submissions = Submission.query.filter(Submission.id.in_(ids)).all()
    if not submissions:
        flash('No valid submissions found.', 'warning')
        return redirect(url_for('dashboard'))
    memory_file = BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for sub in submissions:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], sub.filename)
            if os.path.exists(file_path):
                zf.write(file_path, arcname=sub.original_filename)
    memory_file.seek(0)
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    return send_from_directory(
        directory='',
        path='',
        as_attachment=True,
        download_name=f'submissions_{timestamp}.zip'
    )


# ---------------------------------------------------------------------------
# Seed demo data
# ---------------------------------------------------------------------------

def seed_data():
    if User.query.first():
        return
    lecturer = User(
        username='lecturer',
        email='lecturer@uni.edu',
        password_hash=generate_password_hash('demo123'),
        role='lecturer',
        display_name='Dr. Jane Doe'
    )
    students = [
        User(username='student1', email='alice@uni.edu', password_hash=generate_password_hash('demo123'), role='student', display_name='Alice Smith'),
        User(username='student2', email='bob@uni.edu', password_hash=generate_password_hash('demo123'), role='student', display_name='Bob Jones'),
        User(username='student3', email='carol@uni.edu', password_hash=generate_password_hash('demo123'), role='student', display_name='Carol White'),
    ]
    db.session.add(lecturer)
    for s in students:
        db.session.add(s)
    db.session.commit()

    # Create a dummy submission for student1 so peer assignments can be made
    dummy_sub = Submission(
        student_id=students[0].id,
        filename='dummy.pdf',
        original_filename='dummy.pdf',
        status='Submitted'
    )
    db.session.add(dummy_sub)
    db.session.commit()

    # Peer assignments: each student reviews student1's submission
    far_future = datetime(2099, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
    for s in students[1:]:
        pa = PeerAssignment(reviewer_id=s.id, submission_id=dummy_sub.id, deadline=far_future)
        db.session.add(pa)
    db.session.commit()


# ---------------------------------------------------------------------------
# App launch
# ---------------------------------------------------------------------------

with app.app_context():
    db.create_all()
    seed_data()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
