"""Authentication module with Flask-Login."""

from flask_login import LoginManager
from models import db, User

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'


def init_auth(app):
    """Initialize authentication."""
    login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def create_admin_user(username, password):
    """Create the admin user if it doesn't exist."""
    existing = User.query.filter_by(username=username).first()
    if not existing:
        user = User(username=username, role='admin')
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return user
    return existing
