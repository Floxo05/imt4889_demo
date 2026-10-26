import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB
ALLOWED_EXTENSIONS = {'pdf', 'pptx', 'ppt'}
SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(BASE_DIR, 'portal.db')
SQLALCHEMY_TRACK_MODIFICATIONS = False
