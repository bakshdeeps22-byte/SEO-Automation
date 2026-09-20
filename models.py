"""SQLAlchemy database models for the SEO Automation Webapp."""

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone
import json

db = SQLAlchemy()


class User(UserMixin, db.Model):
    """User for authentication, access control, and project assignment."""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(30), default='viewer')  # superadmin | manager | viewer
    assigned_projects = db.Column(db.Text, default='["all"]')  # JSON list of dataset IDs or ["all"]
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    @property
    def is_superadmin(self):
        return self.role in ('superadmin', 'admin')
    
    @property
    def is_admin(self):
        return self.role in ('superadmin', 'admin')
    
    @property
    def is_manager(self):
        return self.role in ('superadmin', 'admin', 'manager')
    
    def get_assigned_projects_list(self):
        try:
            return json.loads(self.assigned_projects) if self.assigned_projects else ['all']
        except Exception:
            return ['all']
    
    def set_assigned_projects_list(self, project_ids):
        self.assigned_projects = json.dumps(project_ids)
    
    def has_project_access(self, dataset_id):
        if self.is_superadmin:
            return True
        projects = self.get_assigned_projects_list()
        if 'all' in projects:
            return True
        return dataset_id in projects or str(dataset_id) in [str(p) for p in projects]


class Dataset(db.Model):
    """Uploaded Excel dataset or API project workspace metadata."""
    __tablename__ = 'datasets'
    
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    client_name = db.Column(db.String(120), default='NuroSparx')
    project_type = db.Column(db.String(30), default='dataset')  # dataset | api
    website_url = db.Column(db.String(512), nullable=True)
    gsc_site_url = db.Column(db.String(512), nullable=True)
    ga_property_id = db.Column(db.String(100), nullable=True)
    upload_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    is_active = db.Column(db.Boolean, default=True)
    file_path = db.Column(db.String(512), nullable=False)
    sheet_names = db.Column(db.Text)  # JSON list of sheet names
    row_counts = db.Column(db.Text)   # JSON dict of sheet→row count
    
    def get_sheet_names(self):
        return json.loads(self.sheet_names) if self.sheet_names else []
    
    def get_row_counts(self):
        return json.loads(self.row_counts) if self.row_counts else {}


class CrawlIssue(db.Model):
    """Job 1 — Technical crawl issue findings."""
    __tablename__ = 'crawl_issues'
    
    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey('job_runs.id'), nullable=False)
    run_date = db.Column(db.DateTime, nullable=False)
    url = db.Column(db.String(1024), nullable=False)
    template = db.Column(db.String(50))
    issue = db.Column(db.String(255), nullable=False)
    severity = db.Column(db.String(20), nullable=False)  # Critical, High, Medium, Low
    priority_score = db.Column(db.Float, default=0)
    why_it_matters = db.Column(db.Text)
    recommended_action = db.Column(db.Text)
    owner = db.Column(db.String(100), default='SEO Team')
    detected_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    status = db.Column(db.String(20), default='open')  # open, in_progress, resolved


class RankingAnomaly(db.Model):
    """Job 2 — GSC ranking anomaly detections."""
    __tablename__ = 'ranking_anomalies'
    
    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey('job_runs.id'), nullable=False)
    run_date = db.Column(db.DateTime, nullable=False)
    query = db.Column(db.String(512), nullable=False)
    is_branded = db.Column(db.Boolean, default=False)
    clicks_current = db.Column(db.Integer, default=0)
    clicks_previous = db.Column(db.Integer, default=0)
    clicks_change_pct = db.Column(db.Float, default=0)
    impressions_current = db.Column(db.Integer, default=0)
    impressions_previous = db.Column(db.Integer, default=0)
    impressions_change_pct = db.Column(db.Float, default=0)
    position_current = db.Column(db.Float, default=0)
    position_previous = db.Column(db.Float, default=0)
    position_change = db.Column(db.Float, default=0)
    alert_level = db.Column(db.String(20), default='none')  # HIGH, MEDIUM, WATCH, IMPROVED, none
    alert_reason = db.Column(db.Text)


class ProductQAIssue(db.Model):
    """Job 3 — Product SEO QA issues with AI suggestions."""
    __tablename__ = 'product_qa_issues'
    
    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey('job_runs.id'), nullable=False)
    run_date = db.Column(db.DateTime, nullable=False)
    url = db.Column(db.String(1024), nullable=False)
    product_name = db.Column(db.String(255))
    template = db.Column(db.String(50))
    issue_type = db.Column(db.String(100), nullable=False)
    current_value = db.Column(db.Text)
    suggested_value = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    approved_by = db.Column(db.String(80))
    approved_at = db.Column(db.DateTime)
    ai_confidence = db.Column(db.Float, default=0.0)
    notes = db.Column(db.Text)


class RedirectCheck(db.Model):
    """Job 4 — Redirect/migration regression check results."""
    __tablename__ = 'redirect_checks'
    
    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey('job_runs.id'), nullable=False)
    run_date = db.Column(db.DateTime, nullable=False)
    old_url = db.Column(db.String(1024), nullable=False)
    expected_url = db.Column(db.String(1024))
    expected_status = db.Column(db.Integer, default=301)
    actual_status = db.Column(db.Integer)
    actual_final_url = db.Column(db.String(1024))
    redirect_hops = db.Column(db.Integer, default=0)
    pass_fail = db.Column(db.String(20), nullable=False)  # PASS, CRITICAL, WARNING
    failure_reason = db.Column(db.Text)


class JobRun(db.Model):
    """Execution log for each job run."""
    __tablename__ = 'job_runs'
    
    id = db.Column(db.Integer, primary_key=True)
    job_name = db.Column(db.String(100), nullable=False)
    job_number = db.Column(db.Integer, nullable=False)
    run_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    status = db.Column(db.String(20), default='running')  # running, completed, failed
    summary = db.Column(db.Text)
    issues_found = db.Column(db.Integer, default=0)
    critical_count = db.Column(db.Integer, default=0)
    duration_seconds = db.Column(db.Float, default=0)
    triggered_by = db.Column(db.String(50), default='manual')  # manual, scheduled
    dataset_id = db.Column(db.Integer, db.ForeignKey('datasets.id'), nullable=True)
    
    # Relationships
    crawl_issues = db.relationship('CrawlIssue', backref='job_run', lazy=True)
    ranking_anomalies = db.relationship('RankingAnomaly', backref='job_run', lazy=True)
    product_qa_issues = db.relationship('ProductQAIssue', backref='job_run', lazy=True)
    redirect_checks = db.relationship('RedirectCheck', backref='job_run', lazy=True)
    dataset = db.relationship('Dataset', backref='job_runs')


class SharedReport(db.Model):
    """Shareable report links for clients."""
    __tablename__ = 'shared_reports'
    
    id = db.Column(db.Integer, primary_key=True)
    report_type = db.Column(db.String(30), default='job')  # 'dashboard' | 'job'
    client_name = db.Column(db.String(120), default='NuroSparx')
    job_number = db.Column(db.Integer, nullable=True, default=0)
    run_id = db.Column(db.Integer, db.ForeignKey('job_runs.id'), nullable=True)
    dataset_id = db.Column(db.Integer, db.ForeignKey('datasets.id'), nullable=True)
    share_token = db.Column(db.String(64), unique=True, nullable=False)
    title = db.Column(db.String(255))
    created_by = db.Column(db.String(80))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
    view_count = db.Column(db.Integer, default=0)
    
    job_run = db.relationship('JobRun', backref='shared_reports')
    dataset = db.relationship('Dataset', backref='shared_reports')

    @property
    def is_dashboard(self):
        return self.report_type == 'dashboard' or not self.job_number


class APIConfig(db.Model):
    """Stored API configuration and connection status."""
    __tablename__ = 'api_configs'
    
    id = db.Column(db.Integer, primary_key=True)
    service_name = db.Column(db.String(50), unique=True, nullable=False)
    config_json = db.Column(db.Text)  # JSON config
    is_connected = db.Column(db.Boolean, default=False)
    last_verified = db.Column(db.DateTime)
    last_error = db.Column(db.Text)
    
    def get_config(self):
        return json.loads(self.config_json) if self.config_json else {}
    
    def set_config(self, config_dict):
        self.config_json = json.dumps(config_dict)


class WeeklySession(db.Model):
    """Weekly organic session data for trend charts."""
    __tablename__ = 'weekly_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    week_starting = db.Column(db.String(10), nullable=False)
    organic_sessions = db.Column(db.Integer, default=0)
    dataset_id = db.Column(db.Integer, db.ForeignKey('datasets.id'))


class TrafficData(db.Model):
    """Landing page traffic comparison data."""
    __tablename__ = 'traffic_data'
    
    id = db.Column(db.Integer, primary_key=True)
    landing_page = db.Column(db.String(512), nullable=False)
    template = db.Column(db.String(50))
    sessions_previous = db.Column(db.Integer, default=0)
    sessions_current = db.Column(db.Integer, default=0)
    change_pct = db.Column(db.Float, default=0)
    dataset_id = db.Column(db.Integer, db.ForeignKey('datasets.id'))


class PendingTask(db.Model):
    """Actionable SEO tasks generated from approved issue categories."""
    __tablename__ = 'pending_tasks'

    id = db.Column(db.Integer, primary_key=True)
    dataset_id = db.Column(db.Integer, db.ForeignKey('datasets.id'), nullable=True)
    client_name = db.Column(db.String(120), default='NuroSparx')
    job_number = db.Column(db.Integer, nullable=False)
    run_id = db.Column(db.Integer, db.ForeignKey('job_runs.id'), nullable=True)
    category = db.Column(db.String(255), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    item_count = db.Column(db.Integer, default=0)
    severity = db.Column(db.String(20), default='High')  # Critical, High, Medium, Low
    approval_status = db.Column(db.String(30), default='approved')  # approved, disapproved, unreviewed
    status = db.Column(db.String(30), default='pending')  # pending (To Do), completed, verified
    approved_by = db.Column(db.String(80))
    approved_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    completed_by = db.Column(db.String(80))
    completed_at = db.Column(db.DateTime)
    developer_notes = db.Column(db.Text)
    verified_at = db.Column(db.DateTime)
    verification_method = db.Column(db.String(50))
    verification_details = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    dataset = db.relationship('Dataset', backref='pending_tasks')
    job_run = db.relationship('JobRun', backref='pending_tasks')

