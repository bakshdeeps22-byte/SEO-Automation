import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

class Config:
    """Application configuration."""
    
    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY', 'nurosparx-seo-automation-2026-secret-key')
    
    # Database
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{BASE_DIR / 'instance' / 'seo_automation.db'}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Data directory
    DATA_DIR = BASE_DIR / 'data'
    UPLOAD_DIR = BASE_DIR / 'data' / 'uploads'
    
    # Default dataset
    DEFAULT_DATASET = os.environ.get(
        'DEFAULT_DATASET',
        str(BASE_DIR / 'data' / 'NuroSparx-SEO-Automation-Data-Pack.xlsx')
    )
    
    # Google OAuth
    GOOGLE_OAUTH_CREDENTIALS = BASE_DIR / 'config' / 'google_oauth_credentials.json'
    _oauth_env = os.environ.get('GOOGLE_OAUTH_CREDENTIALS_JSON')
    if _oauth_env and not GOOGLE_OAUTH_CREDENTIALS.exists():
        try:
            GOOGLE_OAUTH_CREDENTIALS.parent.mkdir(parents=True, exist_ok=True)
            with open(GOOGLE_OAUTH_CREDENTIALS, 'w') as _f:
                _f.write(_oauth_env)
        except Exception:
            pass
    GOOGLE_TOKEN_PATH = BASE_DIR / 'config' / 'google_token.json'
    GOOGLE_SCOPES = [
        'https://www.googleapis.com/auth/webmasters.readonly',
        'https://www.googleapis.com/auth/analytics.readonly',
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/documents',
    ]
    
    # DataforSEO
    DATAFORSEO_LOGIN = os.environ.get('DATAFORSEO_LOGIN', 'bakshdeeps.22@gmail.com')
    DATAFORSEO_PASSWORD = os.environ.get('DATAFORSEO_PASSWORD', '')
    
    # Scheduler - Monday 10 AM IST (4:30 AM UTC)
    SCHEDULER_TIMEZONE = 'Asia/Kolkata'
    SCHEDULER_DAY_OF_WEEK = 'mon'
    SCHEDULER_HOUR = 10
    SCHEDULER_MINUTE = 0
    
    # Admin defaults
    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'nurosparx2026')
    
    # Max upload size (50MB)
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024
