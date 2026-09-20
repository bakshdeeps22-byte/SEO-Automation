"""SEO Performance Automation Webapp — Main Flask Application.

A comprehensive SEO monitoring dashboard with 4 automated jobs,
admin-only dataset upload, selective report sharing, and API integrations.
"""

import os
import sys
import json
import uuid
import shutil
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, jsonify, send_from_directory, session, abort, send_file
)
from flask_login import (
    login_user, logout_user, login_required, current_user
)
from werkzeug.utils import secure_filename
import pandas as pd

from models import db, User, Dataset, CrawlIssue, RankingAnomaly, ProductQAIssue
from models import RedirectCheck, JobRun, SharedReport, APIConfig, WeeklySession, TrafficData, PendingTask
from auth import init_auth, create_admin_user
from config.settings import Config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
)
logger = logging.getLogger(__name__)


def create_app(start_scheduler=True):
    """Application factory."""
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Ensure directories exist
    Config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    Config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    
    # Initialize extensions
    db.init_app(app)
    init_auth(app)
    
    with app.app_context():
        db.create_all()
        _migrate_db(app)
        create_admin_user(Config.ADMIN_USERNAME, Config.ADMIN_PASSWORD)
        _ensure_default_dataset(app)
    
    # Register routes
    register_routes(app)
    
    # Start scheduler
    if start_scheduler:
        try:
            from jobs.scheduler import init_scheduler
            init_scheduler(app)
        except Exception as e:
            logger.warning(f"Scheduler init failed: {e}")
    
    return app


def admin_required(f):
    """Decorator requiring admin or superadmin role."""
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated


def superadmin_required(f):
    """Decorator requiring superadmin role."""
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_superadmin:
            abort(403)
        return f(*args, **kwargs)
    return decorated


def manager_required(f):
    """Decorator requiring manager, admin, or superadmin role."""
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_manager:
            abort(403)
        return f(*args, **kwargs)
    return decorated



def _migrate_db(app):
    """Ensure newly added columns exist in SQLite database."""
    try:
        import sqlite3
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        if os.path.exists(db_path):
            con = sqlite3.connect(db_path)
            cur = con.cursor()
            
            # users columns
            u_cols = [c[1] for c in cur.execute('PRAGMA table_info(users)').fetchall()]
            if 'email' not in u_cols:
                cur.execute('ALTER TABLE users ADD COLUMN email VARCHAR(120)')
            if 'assigned_projects' not in u_cols:
                cur.execute("ALTER TABLE users ADD COLUMN assigned_projects TEXT DEFAULT '[\"all\"]'")
            if 'is_active' not in u_cols:
                cur.execute('ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT 1')
            
            # datasets columns
            dataset_cols = [c[1] for c in cur.execute('PRAGMA table_info(datasets)').fetchall()]
            if 'client_name' not in dataset_cols:
                cur.execute("ALTER TABLE datasets ADD COLUMN client_name VARCHAR(120) DEFAULT 'NuroSparx'")
            if 'project_type' not in dataset_cols:
                cur.execute("ALTER TABLE datasets ADD COLUMN project_type VARCHAR(30) DEFAULT 'dataset'")
            if 'website_url' not in dataset_cols:
                cur.execute('ALTER TABLE datasets ADD COLUMN website_url VARCHAR(512)')
            if 'gsc_site_url' not in dataset_cols:
                cur.execute('ALTER TABLE datasets ADD COLUMN gsc_site_url VARCHAR(512)')
            if 'ga_property_id' not in dataset_cols:
                cur.execute('ALTER TABLE datasets ADD COLUMN ga_property_id VARCHAR(100)')
                
            # job_runs columns
            jr_cols = [c[1] for c in cur.execute('PRAGMA table_info(job_runs)').fetchall()]
            if 'dataset_id' not in jr_cols:
                cur.execute('ALTER TABLE job_runs ADD COLUMN dataset_id INTEGER')
                
            # shared_reports columns
            sr_cols = [c[1] for c in cur.execute('PRAGMA table_info(shared_reports)').fetchall()]
            if 'report_type' not in sr_cols:
                cur.execute("ALTER TABLE shared_reports ADD COLUMN report_type VARCHAR(30) DEFAULT 'job'")
            if 'client_name' not in sr_cols:
                cur.execute("ALTER TABLE shared_reports ADD COLUMN client_name VARCHAR(120) DEFAULT 'NuroSparx'")
            if 'dataset_id' not in sr_cols:
                cur.execute("ALTER TABLE shared_reports ADD COLUMN dataset_id INTEGER")
                
            con.commit()
            con.close()
    except Exception as e:
        logger.warning(f"DB auto-migration check: {e}")


def _ensure_default_dataset(app):
    """Load default dataset if none exists."""
    if Dataset.query.count() == 0:
        default_path = Config.DEFAULT_DATASET
        if os.path.exists(default_path):
            dest = str(Config.DATA_DIR / 'NuroSparx-SEO-Automation-Data-Pack.xlsx')
            shutil.copy2(default_path, dest)
            
            # Parse sheet info
            wb = pd.ExcelFile(dest)
            sheet_names = wb.sheet_names
            row_counts = {}
            for name in sheet_names:
                df = pd.read_excel(dest, sheet_name=name)
                row_counts[name] = len(df)
            
            dataset = Dataset(
                filename='NuroSparx-SEO-Automation-Data-Pack.xlsx',
                original_filename='NuroSparx-SEO-Automation-Data-Pack.xlsx',
                client_name='NuroSparx',
                file_path=dest,
                is_active=True,
                sheet_names=json.dumps(sheet_names),
                row_counts=json.dumps(row_counts),
            )
            db.session.add(dataset)
            
            # Load weekly sessions and traffic data
            _load_supporting_data(dest, dataset)
            
            db.session.commit()
            logger.info("Default dataset loaded")
    else:
        # Backfill client_name on existing datasets if missing
        ds = Dataset.query.filter_by(is_active=True).first()
        if ds and not ds.client_name:
            ds.client_name = 'NuroSparx'
            db.session.commit()


def _load_supporting_data(dataset_path, dataset_obj):
    """Load weekly sessions and traffic data into DB."""
    try:
        # Weekly sessions
        df_sessions = pd.read_excel(dataset_path, sheet_name='weekly_sessions')
        for _, row in df_sessions.iterrows():
            ws = WeeklySession(
                week_starting=str(row['week_starting']),
                organic_sessions=int(row['organic_sessions']),
                dataset_id=dataset_obj.id if dataset_obj.id else None,
            )
            db.session.add(ws)
        
        # Traffic data
        df_traffic = pd.read_excel(dataset_path, sheet_name='traffic')
        for _, row in df_traffic.iterrows():
            sessions_prev = int(row.get('organic_sessions_mar_2026', 0))
            sessions_curr = int(row.get('organic_sessions_aug_2026', 0))
            change = ((sessions_curr - sessions_prev) / sessions_prev * 100) if sessions_prev > 0 else 0
            
            td = TrafficData(
                landing_page=str(row['landing_page']),
                template=str(row.get('template', '')),
                sessions_previous=sessions_prev,
                sessions_current=sessions_curr,
                change_pct=round(change, 1),
                dataset_id=dataset_obj.id if dataset_obj.id else None,
            )
            db.session.add(td)
    
    except Exception as e:
        logger.error(f"Failed to load supporting data: {e}")


def _get_active_account():
    """Get the currently selected project/dataset for the active session and user."""
    active_id = session.get('active_dataset_id')
    if active_id:
        ds = Dataset.query.get(active_id)
        if ds:
            if current_user.is_authenticated and not current_user.has_project_access(ds.id):
                pass
            else:
                return ds

    # Fallback to active dataset or first accessible
    if current_user.is_authenticated:
        if current_user.is_superadmin:
            ds = Dataset.query.filter_by(is_active=True).first() or Dataset.query.first()
        else:
            p_ids = current_user.get_assigned_projects_list()
            if 'all' in p_ids:
                ds = Dataset.query.filter_by(is_active=True).first() or Dataset.query.first()
            else:
                int_ids = [int(x) for x in p_ids if str(x).isdigit()]
                ds = Dataset.query.filter(Dataset.id.in_(int_ids), Dataset.is_active == True).first() or \
                     Dataset.query.filter(Dataset.id.in_(int_ids)).first()
        if ds:
            session['active_dataset_id'] = ds.id
            return ds

    return Dataset.query.filter_by(is_active=True).first() or Dataset.query.first()


def _get_active_dataset_path():
    """Get the file path of the active dataset."""
    acc = _get_active_account()
    if acc and acc.file_path and os.path.exists(acc.file_path):
        return acc.file_path
    default_path = Config.DATA_DIR / 'NuroSparx-SEO-Automation-Data-Pack.xlsx'
    if default_path.exists():
        return str(default_path)
    return None


def _get_job_categories_with_tasks(job_num, run_id, dataset_id=None):
    """Retrieve categorized issue groups for a job run along with approval/task status."""
    categories = []
    if not run_id:
        return categories
    try:
        if job_num == 1:
            from jobs.job1_crawl_monitor import get_crawl_summary
            s = get_crawl_summary(run_id)
            if s and s.get('issue_type_counts'):
                for cat, cnt in s['issue_type_counts'].items():
                    sev = 'Critical' if ('4xx' in cat or '5xx' in cat) else ('High' if 'Title' in cat or 'Canonical' in cat else 'Medium')
                    categories.append({'name': cat, 'count': cnt, 'severity': sev, 'job_number': 1, 'run_id': run_id})
        elif job_num == 2:
            from jobs.job2_gsc_monitor import get_gsc_summary
            s = get_gsc_summary(run_id)
            if s and s.get('alert_counts'):
                for lvl, cnt in s['alert_counts'].items():
                    if cnt > 0 and lvl not in ('IMPROVED', 'STABLE'):
                        sev = 'Critical' if lvl == 'HIGH' else ('High' if lvl == 'MEDIUM' else 'Medium')
                        categories.append({'name': f"{lvl} Ranking Anomaly", 'count': cnt, 'severity': sev, 'job_number': 2, 'run_id': run_id})
        elif job_num == 3:
            from jobs.job3_product_qa import get_product_qa_summary
            s = get_product_qa_summary(run_id)
            if s and s.get('issue_type_counts'):
                for cat, cnt in s['issue_type_counts'].items():
                    sev = 'High' if 'Title' in cat else 'Medium'
                    categories.append({'name': cat, 'count': cnt, 'severity': sev, 'job_number': 3, 'run_id': run_id})
        elif job_num == 4:
            from jobs.job4_redirect_monitor import get_redirect_summary
            s = get_redirect_summary(run_id)
            if s and s.get('result_counts'):
                for res, cnt in s['result_counts'].items():
                    if res != 'PASS' and cnt > 0:
                        sev = 'Critical' if res == 'CRITICAL' else 'High'
                        categories.append({'name': f"Redirects {res}", 'count': cnt, 'severity': sev, 'job_number': 4, 'run_id': run_id})
    except Exception as e:
        logger.warning(f"Error fetching categories for job {job_num}, run {run_id}: {e}")

    task_q = PendingTask.query.filter_by(job_number=job_num)
    if dataset_id:
        tasks = task_q.filter((PendingTask.dataset_id == dataset_id) | (PendingTask.dataset_id.is_(None))).all()
    else:
        tasks = task_q.all()

    task_map = {t.category: t for t in tasks}
    for c in categories:
        c['task'] = task_map.get(c['name'])

    return categories


def register_routes(app):
    """Register all Flask routes."""
    
    # ── Login / Logout ──────────────────────────────────────────
    
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        
        if request.method == 'POST':
            username = request.form.get('username', '')
            password = request.form.get('password', '')
            
            user = User.query.filter_by(username=username).first()
            if user and user.check_password(password):
                login_user(user)
                next_page = request.args.get('next')
                return redirect(next_page or url_for('dashboard'))
            
            flash('Invalid username or password', 'error')
        
        return render_template('login.html')
    
    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        return redirect(url_for('login'))

    # ── Context Processor ───────────────────────────────────────

    @app.context_processor
    def inject_account_context():
        if not current_user.is_authenticated:
            return {'current_account': None, 'accessible_accounts': [], 'pending_tasks_count': 0}
        
        if current_user.is_superadmin:
            accessible = Dataset.query.order_by(Dataset.upload_date.desc()).all()
        else:
            p_ids = current_user.get_assigned_projects_list()
            if 'all' in p_ids:
                accessible = Dataset.query.order_by(Dataset.upload_date.desc()).all()
            else:
                int_ids = [int(x) for x in p_ids if str(x).isdigit()]
                accessible = Dataset.query.filter(Dataset.id.in_(int_ids)).order_by(Dataset.upload_date.desc()).all()
        
        current_acc = _get_active_account()
        pending_count = 0
        try:
            if current_acc:
                pending_count = PendingTask.query.filter_by(dataset_id=current_acc.id, status='pending', approval_status='approved').count()
            else:
                pending_count = PendingTask.query.filter_by(status='pending', approval_status='approved').count()
        except Exception:
            pending_count = 0

        return {
            'current_account': current_acc,
            'accessible_accounts': accessible,
            'pending_tasks_count': pending_count,
        }

    # ── Multi-Account Switching & Creation ──────────────────────

    @app.route('/switch-account/<int:dataset_id>', methods=['POST'])
    @login_required
    def switch_account(dataset_id):
        if not current_user.has_project_access(dataset_id):
            flash('Access denied to this project/account.', 'error')
            return redirect(request.referrer or url_for('dashboard'))
        
        dataset = Dataset.query.get_or_404(dataset_id)
        session['active_dataset_id'] = dataset.id
        flash(f'Switched active workspace to: {dataset.client_name or dataset.original_filename}', 'success')
        return redirect(request.form.get('next') or request.referrer or url_for('dashboard'))

    @app.route('/projects/create-api', methods=['POST'])
    @admin_required
    def create_api_project():
        client_name = request.form.get('client_name', '').strip()
        website_url = request.form.get('website_url', '').strip()
        gsc_site_url = request.form.get('gsc_site_url', '').strip()
        ga_property_id = request.form.get('ga_property_id', '').strip()
        
        if not client_name:
            flash('Client / Project name is required.', 'error')
            return redirect(url_for('upload_dataset'))
        
        project = Dataset(
            filename=f"api_{secure_filename(client_name.lower())}",
            original_filename=f"{client_name} (API Live)",
            client_name=client_name,
            file_path='',
            is_active=False,
            project_type='api',
            website_url=website_url,
            gsc_site_url=gsc_site_url,
            ga_property_id=ga_property_id,
            sheet_names='[]',
            row_counts='{}'
        )
        db.session.add(project)
        db.session.commit()
        
        session['active_dataset_id'] = project.id
        flash(f'API Project "{client_name}" created successfully and set as active workspace!', 'success')
        return redirect(url_for('dashboard'))

    # ── Dashboard ───────────────────────────────────────────────
    
    @app.route('/')
    @login_required
    def dashboard():
        active_account = _get_active_account()
        active_acc_id = active_account.id if active_account else None

        # Get latest runs for each job (scoped by active account)
        jobs_data = []
        for job_num in range(1, 5):
            query = JobRun.query.filter_by(job_number=job_num, status='completed')
            if active_acc_id:
                latest = query.filter_by(dataset_id=active_acc_id).order_by(JobRun.run_date.desc()).first()
                if not latest:
                    latest = query.order_by(JobRun.run_date.desc()).first()
            else:
                latest = query.order_by(JobRun.run_date.desc()).first()

            categories = _get_job_categories_with_tasks(job_num, latest.id if latest else None, active_acc_id)
            jobs_data.append({
                'number': job_num,
                'name': _job_names()[job_num],
                'icon': _job_icons()[job_num],
                'latest_run': latest,
                'categories': categories,
            })
        
        # Weekly sessions for chart
        if active_acc_id:
            sessions = WeeklySession.query.filter_by(dataset_id=active_acc_id).order_by(WeeklySession.week_starting).all()
            if not sessions:
                sessions = WeeklySession.query.order_by(WeeklySession.week_starting).all()
            traffic = TrafficData.query.filter_by(dataset_id=active_acc_id).order_by(TrafficData.change_pct).all()
            if not traffic:
                traffic = TrafficData.query.order_by(TrafficData.change_pct).all()
        else:
            sessions = WeeklySession.query.order_by(WeeklySession.week_starting).all()
            traffic = TrafficData.query.order_by(TrafficData.change_pct).all()
        
        # Next scheduled run
        try:
            from jobs.scheduler import get_next_run_time
            next_run = get_next_run_time()
        except:
            next_run = None
        
        # Total stats
        total_issues = sum(j['latest_run'].issues_found for j in jobs_data if j['latest_run'])
        total_critical = sum(j['latest_run'].critical_count for j in jobs_data if j['latest_run'])
        pending_approvals = ProductQAIssue.query.filter_by(status='pending').count()
        
        # Accessible datasets for switcher
        if current_user.is_superadmin:
            datasets = Dataset.query.order_by(Dataset.upload_date.desc()).all()
        else:
            p_ids = current_user.get_assigned_projects_list()
            if 'all' in p_ids:
                datasets = Dataset.query.order_by(Dataset.upload_date.desc()).all()
            else:
                int_ids = [int(x) for x in p_ids if str(x).isdigit()]
                datasets = Dataset.query.filter(Dataset.id.in_(int_ids)).order_by(Dataset.upload_date.desc()).all()

        client_name = active_account.client_name if (active_account and active_account.client_name) else 'NuroSparx'
        
        # Active shared links for this dashboard
        share_query = SharedReport.query.filter_by(report_type='dashboard', is_active=True)
        if active_acc_id:
            active_shares = share_query.filter(
                (SharedReport.dataset_id == active_acc_id) | (SharedReport.dataset_id.is_(None))
            ).order_by(SharedReport.created_at.desc()).all()
        else:
            active_shares = share_query.order_by(SharedReport.created_at.desc()).all()

        return render_template('dashboard.html',
            jobs=jobs_data,
            sessions=sessions,
            traffic=traffic,
            next_run=next_run,
            total_issues=total_issues,
            total_critical=total_critical,
            pending_approvals=pending_approvals,
            active_dataset=active_account,
            datasets=datasets,
            client_name=client_name,
            active_shares=active_shares,
        )
    
    # ── Job Detail Pages ────────────────────────────────────────
    
    @app.route('/job/1')
    @login_required
    def job1_detail():
        from jobs.job1_crawl_monitor import get_crawl_summary
        active_account = _get_active_account()
        run_id = request.args.get('run_id', type=int)

        if not run_id and active_account:
            acc_run = JobRun.query.filter_by(job_number=1, dataset_id=active_account.id, status='completed')\
                .order_by(JobRun.run_date.desc()).first()
            if acc_run:
                run_id = acc_run.id

        summary = get_crawl_summary(run_id)

        if active_account:
            runs = JobRun.query.filter_by(job_number=1, dataset_id=active_account.id, status='completed')\
                .order_by(JobRun.run_date.desc()).limit(20).all()
            if not runs:
                runs = JobRun.query.filter_by(job_number=1, status='completed')\
                    .order_by(JobRun.run_date.desc()).limit(20).all()
            tasks = PendingTask.query.filter_by(job_number=1, dataset_id=active_account.id).all()
        else:
            runs = JobRun.query.filter_by(job_number=1, status='completed')\
                .order_by(JobRun.run_date.desc()).limit(20).all()
            tasks = PendingTask.query.filter_by(job_number=1).all()

        task_map = {t.category: t for t in tasks}
        categories = _get_job_categories_with_tasks(1, summary['run_id'] if summary else run_id, active_account.id if active_account else None)
        return render_template('job1.html', summary=summary, runs=runs, task_map=task_map, categories=categories)
    
    @app.route('/job/2')
    @login_required
    def job2_detail():
        from jobs.job2_gsc_monitor import get_gsc_summary
        active_account = _get_active_account()
        run_id = request.args.get('run_id', type=int)

        if not run_id and active_account:
            acc_run = JobRun.query.filter_by(job_number=2, dataset_id=active_account.id, status='completed')\
                .order_by(JobRun.run_date.desc()).first()
            if acc_run:
                run_id = acc_run.id

        summary = get_gsc_summary(run_id)

        if active_account:
            runs = JobRun.query.filter_by(job_number=2, dataset_id=active_account.id, status='completed')\
                .order_by(JobRun.run_date.desc()).limit(20).all()
            if not runs:
                runs = JobRun.query.filter_by(job_number=2, status='completed')\
                    .order_by(JobRun.run_date.desc()).limit(20).all()
            tasks = PendingTask.query.filter_by(job_number=2, dataset_id=active_account.id).all()
        else:
            runs = JobRun.query.filter_by(job_number=2, status='completed')\
                .order_by(JobRun.run_date.desc()).limit(20).all()
            tasks = PendingTask.query.filter_by(job_number=2).all()

        task_map = {t.category: t for t in tasks}
        categories = _get_job_categories_with_tasks(2, summary['run_id'] if summary else run_id, active_account.id if active_account else None)
        return render_template('job2.html', summary=summary, runs=runs, task_map=task_map, categories=categories)
    
    @app.route('/job/3')
    @login_required
    def job3_detail():
        from jobs.job3_product_qa import get_product_qa_summary
        active_account = _get_active_account()
        run_id = request.args.get('run_id', type=int)

        if not run_id and active_account:
            acc_run = JobRun.query.filter_by(job_number=3, dataset_id=active_account.id, status='completed')\
                .order_by(JobRun.run_date.desc()).first()
            if acc_run:
                run_id = acc_run.id

        summary = get_product_qa_summary(run_id)

        if active_account:
            runs = JobRun.query.filter_by(job_number=3, dataset_id=active_account.id, status='completed')\
                .order_by(JobRun.run_date.desc()).limit(20).all()
            if not runs:
                runs = JobRun.query.filter_by(job_number=3, status='completed')\
                    .order_by(JobRun.run_date.desc()).limit(20).all()
            tasks = PendingTask.query.filter_by(job_number=3, dataset_id=active_account.id).all()
        else:
            runs = JobRun.query.filter_by(job_number=3, status='completed')\
                .order_by(JobRun.run_date.desc()).limit(20).all()
            tasks = PendingTask.query.filter_by(job_number=3).all()

        task_map = {t.category: t for t in tasks}
        categories = _get_job_categories_with_tasks(3, summary['run_id'] if summary else run_id, active_account.id if active_account else None)
        return render_template('job3.html', summary=summary, runs=runs, task_map=task_map, categories=categories)
    
    @app.route('/job/4')
    @login_required
    def job4_detail():
        from jobs.job4_redirect_monitor import get_redirect_summary
        active_account = _get_active_account()
        run_id = request.args.get('run_id', type=int)

        if not run_id and active_account:
            acc_run = JobRun.query.filter_by(job_number=4, dataset_id=active_account.id, status='completed')\
                .order_by(JobRun.run_date.desc()).first()
            if acc_run:
                run_id = acc_run.id

        summary = get_redirect_summary(run_id)

        if active_account:
            runs = JobRun.query.filter_by(job_number=4, dataset_id=active_account.id, status='completed')\
                .order_by(JobRun.run_date.desc()).limit(20).all()
            if not runs:
                runs = JobRun.query.filter_by(job_number=4, status='completed')\
                    .order_by(JobRun.run_date.desc()).limit(20).all()
            tasks = PendingTask.query.filter_by(job_number=4, dataset_id=active_account.id).all()
        else:
            runs = JobRun.query.filter_by(job_number=4, status='completed')\
                .order_by(JobRun.run_date.desc()).limit(20).all()
            tasks = PendingTask.query.filter_by(job_number=4).all()

        task_map = {t.category: t for t in tasks}
        categories = _get_job_categories_with_tasks(4, summary['run_id'] if summary else run_id, active_account.id if active_account else None)
        return render_template('job4.html', summary=summary, runs=runs, task_map=task_map, categories=categories)
    
    # ── Job Triggers ────────────────────────────────────────────
    
    @app.route('/job/<int:job_num>/run', methods=['POST'])
    @admin_required
    def run_job(job_num):
        active_account = _get_active_account()
        dataset_path = _get_active_dataset_path()
        dataset_id = active_account.id if active_account else None

        if not dataset_path:
            flash('No dataset file found for active project. Please upload an Excel dataset.', 'error')
            return redirect(url_for('dashboard'))

        try:
            if job_num == 1:
                from jobs.job1_crawl_monitor import run_crawl_monitor
                run_crawl_monitor(dataset_path, triggered_by='manual', dataset_id=dataset_id)
            elif job_num == 2:
                from jobs.job2_gsc_monitor import run_gsc_monitor
                run_gsc_monitor(dataset_path, triggered_by='manual', dataset_id=dataset_id)
            elif job_num == 3:
                from jobs.job3_product_qa import run_product_qa
                run_product_qa(dataset_path, triggered_by='manual', dataset_id=dataset_id)
            elif job_num == 4:
                from jobs.job4_redirect_monitor import run_redirect_monitor
                run_redirect_monitor(dataset_path, triggered_by='manual', dataset_id=dataset_id)
            else:
                flash('Invalid job number', 'error')
                return redirect(url_for('dashboard'))

            acc_name = active_account.client_name if active_account else "workspace"
            flash(f'{_job_names()[job_num]} completed successfully for {acc_name}!', 'success')
        except Exception as e:
            flash(f'Job failed: {str(e)}', 'error')

        return redirect(url_for(f'job{job_num}_detail'))
    
    @app.route('/run-all', methods=['POST'])
    @admin_required
    def run_all():
        active_account = _get_active_account()
        dataset_path = _get_active_dataset_path()
        dataset_id = active_account.id if active_account else None

        if not dataset_path:
            flash('No dataset file found for active project. Please upload an Excel dataset.', 'error')
            return redirect(url_for('dashboard'))

        from jobs.job1_crawl_monitor import run_crawl_monitor
        from jobs.job2_gsc_monitor import run_gsc_monitor
        from jobs.job3_product_qa import run_product_qa
        from jobs.job4_redirect_monitor import run_redirect_monitor

        results = []
        for name, func in [
            ('Crawl Monitor', run_crawl_monitor),
            ('GSC Monitor', run_gsc_monitor),
            ('Product QA', run_product_qa),
            ('Redirect Monitor', run_redirect_monitor),
        ]:
            try:
                func(dataset_path, triggered_by='manual', dataset_id=dataset_id)
                results.append(f'✅ {name}')
            except Exception as e:
                results.append(f'❌ {name}: {str(e)}')

        flash(' | '.join(results), 'success')
        return redirect(url_for('dashboard'))
    
    # ── Product QA Approval ─────────────────────────────────────
    
    @app.route('/job/3/approve/<int:issue_id>', methods=['POST'])
    @manager_required
    def approve_qa(issue_id):
        issue = ProductQAIssue.query.get_or_404(issue_id)
        action = request.form.get('action', 'approve')
        
        if action == 'approve':
            issue.status = 'approved'
            issue.approved_by = current_user.username
            issue.approved_at = datetime.now(timezone.utc)
            flash(f'Approved fix for {issue.product_name}', 'success')
        elif action == 'reject':
            issue.status = 'rejected'
            issue.notes = request.form.get('notes', '')
            flash(f'Rejected fix for {issue.product_name}', 'info')
        
        db.session.commit()
        return redirect(url_for('job3_detail'))
    
    @app.route('/job/3/bulk-approve', methods=['POST'])
    @manager_required
    def bulk_approve():
        issue_ids = request.form.getlist('issue_ids')
        count = 0
        for iid in issue_ids:
            issue = ProductQAIssue.query.get(int(iid))
            if issue and issue.status == 'pending':
                issue.status = 'approved'
                issue.approved_by = current_user.username
                issue.approved_at = datetime.now(timezone.utc)
                count += 1
        
        db.session.commit()
        flash(f'Approved {count} issues', 'success')
        return redirect(url_for('job3_detail'))
    
    # ── Dataset Upload ──────────────────────────────────────────
    
    @app.route('/upload-dataset', methods=['GET', 'POST'])
    @admin_required
    def upload_dataset():
        if request.method == 'POST':
            if 'file' not in request.files:
                flash('No file selected', 'error')
                return redirect(url_for('upload_dataset'))
            
            file = request.files['file']
            if file.filename == '':
                flash('No file selected', 'error')
                return redirect(url_for('upload_dataset'))
            
            if not file.filename.endswith(('.xlsx', '.xls')):
                flash('Only Excel files (.xlsx, .xls) are accepted', 'error')
                return redirect(url_for('upload_dataset'))
            
            # Save file
            original_name = secure_filename(file.filename)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'{timestamp}_{original_name}'
            filepath = str(Config.UPLOAD_DIR / filename)
            file.save(filepath)
            
            try:
                # Parse sheet info
                wb = pd.ExcelFile(filepath)
                sheet_names = wb.sheet_names
                row_counts = {}
                for name in sheet_names:
                    df = pd.read_excel(filepath, sheet_name=name)
                    row_counts[name] = len(df)
                
                # Deactivate old datasets
                Dataset.query.update({Dataset.is_active: False})
                
                # Clear old supporting data
                WeeklySession.query.delete()
                TrafficData.query.delete()
                
                # Create new dataset record
                client_name = request.form.get('client_name', '').strip() or 'NuroSparx'
                dataset = Dataset(
                    filename=filename,
                    original_filename=original_name,
                    client_name=client_name,
                    file_path=filepath,
                    is_active=True,
                    sheet_names=json.dumps(sheet_names),
                    row_counts=json.dumps(row_counts),
                )
                db.session.add(dataset)
                db.session.flush()
                
                # Load supporting data if available
                _load_supporting_data(filepath, dataset)
                
                db.session.commit()
                
                flash(f'Dataset "{original_name}" uploaded successfully for client "{client_name}"! Sheets: {", ".join(sheet_names)}', 'success')
            
            except Exception as e:
                flash(f'Error processing file: {str(e)}', 'error')
                if os.path.exists(filepath):
                    os.remove(filepath)
            
            return redirect(url_for('upload_dataset'))
        
        # GET — show upload page
        datasets = Dataset.query.order_by(Dataset.upload_date.desc()).all()
        active = Dataset.query.filter_by(is_active=True).first()
        
        return render_template('upload.html', datasets=datasets, active=active)
    
    @app.route('/activate-dataset/<int:dataset_id>', methods=['POST'])
    @admin_required
    def activate_dataset(dataset_id):
        Dataset.query.update({Dataset.is_active: False})
        dataset = Dataset.query.get_or_404(dataset_id)
        dataset.is_active = True
        
        # Reload supporting data
        WeeklySession.query.delete()
        TrafficData.query.delete()
        _load_supporting_data(dataset.file_path, dataset)
        
        db.session.commit()
        flash(f'Activated client dataset: {dataset.client_name or dataset.original_filename}', 'success')
        return redirect(request.referrer or url_for('upload_dataset'))

    @app.route('/rename-client/<int:dataset_id>', methods=['POST'])
    @admin_required
    def rename_client(dataset_id):
        new_name = request.form.get('client_name', '').strip()
        if new_name:
            ds = Dataset.query.get_or_404(dataset_id)
            ds.client_name = new_name
            db.session.commit()
            flash(f'Client name updated to "{new_name}"', 'success')
        return redirect(request.referrer or url_for('upload_dataset'))
    
    # ── API Settings ────────────────────────────────────────────
    
    @app.route('/api-settings', methods=['GET', 'POST'])
    @admin_required
    def api_settings():
        if request.method == 'POST':
            service = request.form.get('service')
            
            if service == 'dataforseo':
                login = request.form.get('dataforseo_login', '')
                password = request.form.get('dataforseo_password', '')
                
                config = APIConfig.query.filter_by(service_name='dataforseo').first()
                if not config:
                    config = APIConfig(service_name='dataforseo')
                    db.session.add(config)
                
                config.set_config({'login': login, 'password': password})
                
                # Test connection
                from integrations.dataforseo_api import DataforSEOClient
                client = DataforSEOClient(login, password)
                success, msg = client.test_connection()
                config.is_connected = success
                config.last_verified = datetime.now(timezone.utc)
                config.last_error = None if success else msg
                
                db.session.commit()
                
                if success:
                    flash(f'DataforSEO connected! {msg}', 'success')
                else:
                    flash(f'DataforSEO connection failed: {msg}', 'error')
            
            elif service == 'screaming_frog':
                config = APIConfig.query.filter_by(service_name='screaming_frog').first()
                if not config:
                    config = APIConfig(service_name='screaming_frog')
                    db.session.add(config)
                
                sf_path = request.form.get('sf_path', '')
                config.set_config({'path': sf_path})
                config.is_connected = bool(sf_path and os.path.exists(sf_path))
                config.last_verified = datetime.now(timezone.utc)
                
                db.session.commit()
                flash('Screaming Frog configuration saved', 'success')
            
            return redirect(url_for('api_settings'))
        
        # GET
        configs = {}
        for svc in ['google_oauth', 'dataforseo', 'screaming_frog']:
            config = APIConfig.query.filter_by(service_name=svc).first()
            configs[svc] = config
        
        # Check Google OAuth status
        try:
            from integrations.google_auth import GoogleAuthManager
            gauth = GoogleAuthManager(
                Config.GOOGLE_OAUTH_CREDENTIALS,
                Config.GOOGLE_TOKEN_PATH,
                Config.GOOGLE_SCOPES,
            )
            google_connected = gauth.is_authenticated
        except:
            google_connected = False
        
        return render_template('api_settings.html',
            configs=configs,
            google_connected=google_connected,
        )
    
    # ── Google OAuth Flow ───────────────────────────────────────
    
    @app.route('/oauth/google/connect')
    @admin_required
    def google_oauth_connect():
        from integrations.google_auth import GoogleAuthManager
        
        gauth = GoogleAuthManager(
            Config.GOOGLE_OAUTH_CREDENTIALS,
            Config.GOOGLE_TOKEN_PATH,
            Config.GOOGLE_SCOPES,
        )
        
        redirect_uri = url_for('google_oauth_callback', _external=True)
        
        try:
            auth_url, state = gauth.create_auth_flow(redirect_uri)
            session['oauth_state'] = state
            return redirect(auth_url)
        except Exception as e:
            flash(f'OAuth error: {str(e)}', 'error')
            return redirect(url_for('api_settings'))
    
    @app.route('/oauth/callback')
    @admin_required
    def google_oauth_callback():
        from integrations.google_auth import GoogleAuthManager
        
        gauth = GoogleAuthManager(
            Config.GOOGLE_OAUTH_CREDENTIALS,
            Config.GOOGLE_TOKEN_PATH,
            Config.GOOGLE_SCOPES,
        )
        
        redirect_uri = url_for('google_oauth_callback', _external=True)
        
        try:
            gauth.handle_callback(request.url, redirect_uri)
            
            # Update API config
            config = APIConfig.query.filter_by(service_name='google_oauth').first()
            if not config:
                config = APIConfig(service_name='google_oauth')
                db.session.add(config)
            config.is_connected = True
            config.last_verified = datetime.now(timezone.utc)
            db.session.commit()
            
            flash('Google APIs connected successfully!', 'success')
        except Exception as e:
            flash(f'OAuth callback error: {str(e)}', 'error')
        
        return redirect(url_for('api_settings'))
    
    @app.route('/oauth/google/disconnect', methods=['POST'])
    @admin_required
    def google_oauth_disconnect():
        from integrations.google_auth import GoogleAuthManager
        
        gauth = GoogleAuthManager(
            Config.GOOGLE_OAUTH_CREDENTIALS,
            Config.GOOGLE_TOKEN_PATH,
            Config.GOOGLE_SCOPES,
        )
        gauth.disconnect()
        
        config = APIConfig.query.filter_by(service_name='google_oauth').first()
        if config:
            config.is_connected = False
            db.session.commit()
        
        flash('Google APIs disconnected', 'info')
        return redirect(url_for('api_settings'))
    
    # ── Report Sharing ──────────────────────────────────────────
    
    @app.route('/share/dashboard', methods=['POST'])
    @admin_required
    def share_dashboard():
        client_name = request.form.get('client_name', '').strip()
        custom_title = request.form.get('title', '').strip()
        expiry_choice = request.form.get('expiry_days', '30')
        dataset_id = request.form.get('dataset_id', type=int)
        
        active_ds = None
        if dataset_id:
            active_ds = Dataset.query.get(dataset_id)
        if not active_ds:
            active_ds = Dataset.query.filter_by(is_active=True).first()
            if active_ds:
                dataset_id = active_ds.id
                
        if not client_name:
            client_name = active_ds.client_name if (active_ds and active_ds.client_name) else 'NuroSparx'
            
        title = custom_title or f'{client_name} — SEO Performance Dashboard'
        
        expires_at = None
        if expiry_choice != '0':
            try:
                days = int(expiry_choice)
                expires_at = datetime.now(timezone.utc) + timedelta(days=days)
            except ValueError:
                expires_at = datetime.now(timezone.utc) + timedelta(days=30)
        
        token = uuid.uuid4().hex
        
        shared = SharedReport(
            report_type='dashboard',
            client_name=client_name,
            dataset_id=dataset_id,
            job_number=0,
            run_id=None,
            share_token=token,
            title=title,
            created_by=current_user.username,
            expires_at=expires_at,
        )
        db.session.add(shared)
        db.session.commit()
        
        share_url = url_for('view_shared', token=token, _external=True)
        flash(f'Client Dashboard share link generated: {share_url}', 'success')
        
        next_url = request.form.get('next') or request.referrer or url_for('shared_reports_list')
        return redirect(next_url)

    @app.route('/share/<int:job_num>/<int:run_id>', methods=['POST'])
    @admin_required
    def share_report(job_num, run_id):
        job_run = JobRun.query.get_or_404(run_id)
        
        # Generate unique token
        token = uuid.uuid4().hex
        active_ds = Dataset.query.filter_by(is_active=True).first()
        client_name = active_ds.client_name if (active_ds and active_ds.client_name) else 'NuroSparx'
        
        shared = SharedReport(
            report_type='job',
            client_name=client_name,
            dataset_id=active_ds.id if active_ds else None,
            job_number=job_num,
            run_id=run_id,
            share_token=token,
            title=f'{_job_names()[job_num]} — {job_run.run_date.strftime("%B %d, %Y")}',
            created_by=current_user.username,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db.session.add(shared)
        db.session.commit()
        
        share_url = url_for('view_shared', token=token, _external=True)
        flash(f'Report shared! Link: {share_url}', 'success')
        return redirect(url_for(f'job{job_num}_detail'))
    
    @app.route('/shared/<token>')
    def view_shared(token):
        shared = SharedReport.query.filter_by(share_token=token, is_active=True).first_or_404()
        
        # Check expiry
        if shared.expires_at:
            exp = shared.expires_at if shared.expires_at.tzinfo else shared.expires_at.replace(tzinfo=timezone.utc)
            if exp < datetime.now(timezone.utc):
                abort(410)  # Gone
        
        # Increment view count
        shared.view_count += 1
        db.session.commit()
        
        # ── Dashboard Share ──
        if shared.report_type == 'dashboard' or not shared.job_number:
            jobs_data = []
            for job_num in range(1, 5):
                query = JobRun.query.filter_by(job_number=job_num, status='completed')
                if shared.dataset_id:
                    latest = query.filter_by(dataset_id=shared.dataset_id).order_by(JobRun.run_date.desc()).first()
                    if not latest:
                        latest = query.order_by(JobRun.run_date.desc()).first()
                else:
                    latest = query.order_by(JobRun.run_date.desc()).first()

                categories = _get_job_categories_with_tasks(job_num, latest.id if latest else None, shared.dataset_id)
                jobs_data.append({
                    'number': job_num,
                    'name': _job_names()[job_num],
                    'icon': _job_icons()[job_num],
                    'latest_run': latest,
                    'categories': categories,
                })
            
            if shared.dataset_id:
                sessions = WeeklySession.query.filter_by(dataset_id=shared.dataset_id).order_by(WeeklySession.week_starting).all()
                if not sessions:
                    sessions = WeeklySession.query.order_by(WeeklySession.week_starting).all()
                traffic = TrafficData.query.filter_by(dataset_id=shared.dataset_id).order_by(TrafficData.change_pct).all()
                if not traffic:
                    traffic = TrafficData.query.order_by(TrafficData.change_pct).all()
            else:
                sessions = WeeklySession.query.order_by(WeeklySession.week_starting).all()
                traffic = TrafficData.query.order_by(TrafficData.change_pct).all()
            
            total_issues = sum(j['latest_run'].issues_found for j in jobs_data if j['latest_run'])
            total_critical = sum(j['latest_run'].critical_count for j in jobs_data if j['latest_run'])
            pending_approvals = ProductQAIssue.query.filter_by(status='pending').count()
            
            return render_template('shared_dashboard.html',
                shared=shared,
                jobs=jobs_data,
                sessions=sessions,
                traffic=traffic,
                total_issues=total_issues,
                total_critical=total_critical,
                pending_approvals=pending_approvals,
            )
        
        # ── Individual Job Run Report ──
        job_run = JobRun.query.get(shared.run_id)
        data = None
        if shared.job_number == 1:
            from jobs.job1_crawl_monitor import get_crawl_summary
            data = get_crawl_summary(shared.run_id)
        elif shared.job_number == 2:
            from jobs.job2_gsc_monitor import get_gsc_summary
            data = get_gsc_summary(shared.run_id)
        elif shared.job_number == 3:
            from jobs.job3_product_qa import get_product_qa_summary
            data = get_product_qa_summary(shared.run_id)
        elif shared.job_number == 4:
            from jobs.job4_redirect_monitor import get_redirect_summary
            data = get_redirect_summary(shared.run_id)
        
        categories = _get_job_categories_with_tasks(shared.job_number, shared.run_id, shared.dataset_id)
        return render_template('shared_report.html',
            shared=shared, job_run=job_run, data=data,
            categories=categories,
            job_name=_job_names().get(shared.job_number, 'Report'),
        )
    
    @app.route('/shared-reports')
    @admin_required
    def shared_reports_list():
        dashboard_reports = SharedReport.query.filter_by(report_type='dashboard')\
            .order_by(SharedReport.created_at.desc()).all()
        job_reports = SharedReport.query.filter(
            (SharedReport.report_type == 'job') | (SharedReport.report_type.is_(None))
        ).order_by(SharedReport.created_at.desc()).all()
        
        datasets = Dataset.query.order_by(Dataset.upload_date.desc()).all()
        active_dataset = Dataset.query.filter_by(is_active=True).first()
        
        return render_template('shared_reports.html',
            dashboard_reports=dashboard_reports,
            job_reports=job_reports,
            datasets=datasets,
            active_dataset=active_dataset,
            job_names=_job_names(),
        )
    
    @app.route('/revoke-share/<int:share_id>', methods=['POST'])
    @admin_required
    def revoke_share(share_id):
        shared = SharedReport.query.get_or_404(share_id)
        shared.is_active = False
        db.session.commit()
        flash('Share link revoked', 'info')
        return redirect(request.referrer or url_for('shared_reports_list'))

    # ── Access Management (Superadmin Only) ─────────────────────

    @app.route('/access-management')
    @superadmin_required
    def access_management():
        users = User.query.order_by(User.id.asc()).all()
        datasets = Dataset.query.order_by(Dataset.upload_date.desc()).all()
        return render_template('access_management.html', users=users, datasets=datasets)

    @app.route('/access-management/create', methods=['POST'])
    @superadmin_required
    def create_user():
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        role = request.form.get('role', 'viewer').strip()
        project_all = request.form.get('project_all') == 'all'
        selected_projects = request.form.getlist('project_ids')
        
        if not username or not password:
            flash('Username and password are required.', 'error')
            return redirect(url_for('access_management'))
        
        if User.query.filter_by(username=username).first():
            flash(f'Username "{username}" is already taken.', 'error')
            return redirect(url_for('access_management'))
        
        if email and User.query.filter_by(email=email).first():
            flash(f'Email "{email}" is already registered.', 'error')
            return redirect(url_for('access_management'))
        
        if role == 'superadmin' or project_all:
            assigned = ['all']
        else:
            assigned = [int(p) for p in selected_projects if str(p).isdigit()]
        
        new_user = User(
            username=username,
            email=email,
            role=role,
            is_active=True,
        )
        new_user.set_password(password)
        new_user.set_assigned_projects_list(assigned)
        db.session.add(new_user)
        db.session.commit()
        
        flash(f'User "{username}" created successfully with role "{role}".', 'success')
        return redirect(url_for('access_management'))

    @app.route('/access-management/edit/<int:user_id>', methods=['POST'])
    @superadmin_required
    def edit_user(user_id):
        user = User.query.get_or_404(user_id)
        email = request.form.get('email', '').strip()
        new_password = request.form.get('new_password', '').strip()
        role = request.form.get('role', user.role).strip()
        project_all = request.form.get('project_all') == 'all'
        selected_projects = request.form.getlist('project_ids')
        
        if email and email != user.email:
            existing = User.query.filter_by(email=email).first()
            if existing and existing.id != user.id:
                flash(f'Email "{email}" is already in use by another user.', 'error')
                return redirect(url_for('access_management'))
            user.email = email
            
        if new_password:
            user.set_password(new_password)
            
        user.role = role
        if role == 'superadmin' or project_all:
            assigned = ['all']
        else:
            assigned = [int(p) for p in selected_projects if str(p).isdigit()]
        user.set_assigned_projects_list(assigned)
        
        db.session.commit()
        flash(f'Permissions updated for user "{user.username}".', 'success')
        return redirect(url_for('access_management'))

    @app.route('/access-management/delete/<int:user_id>', methods=['POST'])
    @superadmin_required
    def delete_user(user_id):
        if user_id == current_user.id:
            flash('You cannot delete your own account.', 'error')
            return redirect(url_for('access_management'))
            
        user = User.query.get_or_404(user_id)
        name = user.username
        db.session.delete(user)
        db.session.commit()
        flash(f'User "{name}" has been removed.', 'info')
        return redirect(url_for('access_management'))

    # ── Report Export (.xlsx) ───────────────────────────────────

    @app.route('/export/job1/<int:run_id>')
    @login_required
    def export_job1(run_id):
        job_run = JobRun.query.get_or_404(run_id)
        if job_run.dataset_id and not current_user.has_project_access(job_run.dataset_id):
            abort(403)
        from services.export_service import export_job1_crawl_issues
        client_name = job_run.dataset.client_name if (job_run.dataset and job_run.dataset.client_name) else 'NuroSparx'
        bio = export_job1_crawl_issues(run_id, client_name=client_name)
        date_str = job_run.run_date.strftime('%Y%m%d')
        safe_name = secure_filename(client_name).replace('_', '-')
        return send_file(
            bio,
            as_attachment=True,
            download_name=f"{safe_name}_Job1_Crawl_Issues_{date_str}.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    @app.route('/export/job2/<int:run_id>')
    @login_required
    def export_job2(run_id):
        job_run = JobRun.query.get_or_404(run_id)
        if job_run.dataset_id and not current_user.has_project_access(job_run.dataset_id):
            abort(403)
        from services.export_service import export_job2_gsc_anomalies
        client_name = job_run.dataset.client_name if (job_run.dataset and job_run.dataset.client_name) else 'NuroSparx'
        bio = export_job2_gsc_anomalies(run_id, client_name=client_name)
        date_str = job_run.run_date.strftime('%Y%m%d')
        safe_name = secure_filename(client_name).replace('_', '-')
        return send_file(
            bio,
            as_attachment=True,
            download_name=f"{safe_name}_Job2_GSC_Anomalies_{date_str}.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    @app.route('/export/job3/<int:run_id>')
    @login_required
    def export_job3(run_id):
        job_run = JobRun.query.get_or_404(run_id)
        if job_run.dataset_id and not current_user.has_project_access(job_run.dataset_id):
            abort(403)
        from services.export_service import export_job3_product_qa
        client_name = job_run.dataset.client_name if (job_run.dataset and job_run.dataset.client_name) else 'NuroSparx'
        bio = export_job3_product_qa(run_id, client_name=client_name)
        date_str = job_run.run_date.strftime('%Y%m%d')
        safe_name = secure_filename(client_name).replace('_', '-')
        return send_file(
            bio,
            as_attachment=True,
            download_name=f"{safe_name}_Job3_Product_QA_{date_str}.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    @app.route('/export/job4/<int:run_id>')
    @login_required
    def export_job4(run_id):
        job_run = JobRun.query.get_or_404(run_id)
        if job_run.dataset_id and not current_user.has_project_access(job_run.dataset_id):
            abort(403)
        from services.export_service import export_job4_redirect_checks
        client_name = job_run.dataset.client_name if (job_run.dataset and job_run.dataset.client_name) else 'NuroSparx'
        bio = export_job4_redirect_checks(run_id, client_name=client_name)
        date_str = job_run.run_date.strftime('%Y%m%d')
        safe_name = secure_filename(client_name).replace('_', '-')
        return send_file(
            bio,
            as_attachment=True,
            download_name=f"{safe_name}_Job4_Redirect_Checks_{date_str}.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    @app.route('/export/dashboard')
    @login_required
    def export_dashboard_report():
        active_acc = _get_active_account()
        dataset_id = active_acc.id if active_acc else None
        client_name = active_acc.client_name if (active_acc and active_acc.client_name) else 'NuroSparx'
        
        if dataset_id and not current_user.has_project_access(dataset_id):
            abort(403)
            
        from services.export_service import export_full_dashboard
        bio = export_full_dashboard(dataset_id=dataset_id, client_name=client_name)
        date_str = datetime.now(timezone.utc).strftime('%Y%m%d')
        safe_name = secure_filename(client_name).replace('_', '-')
        return send_file(
            bio,
            as_attachment=True,
            download_name=f"{safe_name}_Full_SEO_Report_{date_str}.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    @app.route('/export/shared/<token>')
    def export_shared(token):
        shared = SharedReport.query.filter_by(share_token=token, is_active=True).first_or_404()
        if shared.expires_at:
            exp = shared.expires_at if shared.expires_at.tzinfo else shared.expires_at.replace(tzinfo=timezone.utc)
            if exp < datetime.now(timezone.utc):
                abort(410)
                
        client_name = shared.client_name or 'Client'
        date_str = datetime.now(timezone.utc).strftime('%Y%m%d')
        safe_name = secure_filename(client_name).replace('_', '-')
        
        if shared.report_type == 'dashboard' or not shared.job_number:
            from services.export_service import export_full_dashboard
            bio = export_full_dashboard(dataset_id=shared.dataset_id, client_name=client_name)
            fname = f"{safe_name}_SEO_Performance_Report_{date_str}.xlsx"
        elif shared.job_number == 1:
            from services.export_service import export_job1_crawl_issues
            bio = export_job1_crawl_issues(shared.run_id, client_name=client_name)
            fname = f"{safe_name}_Job1_Crawl_{date_str}.xlsx"
        elif shared.job_number == 2:
            from services.export_service import export_job2_gsc_anomalies
            bio = export_job2_gsc_anomalies(shared.run_id, client_name=client_name)
            fname = f"{safe_name}_Job2_GSC_{date_str}.xlsx"
        elif shared.job_number == 3:
            from services.export_service import export_job3_product_qa
            bio = export_job3_product_qa(shared.run_id, client_name=client_name)
            fname = f"{safe_name}_Job3_ProductQA_{date_str}.xlsx"
        elif shared.job_number == 4:
            from services.export_service import export_job4_redirect_checks
            bio = export_job4_redirect_checks(shared.run_id, client_name=client_name)
            fname = f"{safe_name}_Job4_Redirects_{date_str}.xlsx"
        else:
            abort(404)
            
        return send_file(
            bio,
            as_attachment=True,
            download_name=fname,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    # ── Category Approvals & Task Workflow ──────────────────────

    @app.route('/category/approve', methods=['POST'])
    @login_required
    def approve_category():
        job_number = request.form.get('job_number', type=int)
        run_id = request.form.get('run_id', type=int)
        category = request.form.get('category', '').strip()
        item_count = request.form.get('item_count', type=int, default=1)
        severity = request.form.get('severity', 'High').strip()
        custom_title = request.form.get('title', '').strip()

        if not category or not job_number:
            flash('Invalid category or job specification.', 'error')
            return redirect(request.referrer or url_for('dashboard'))

        active_account = _get_active_account()
        dataset_id = active_account.id if active_account else None
        client_name = active_account.client_name if (active_account and active_account.client_name) else 'NuroSparx'

        task = PendingTask.query.filter_by(
            dataset_id=dataset_id,
            job_number=job_number,
            category=category
        ).first()

        title = custom_title or f"Fix {category} ({item_count} items)"

        if not task:
            task = PendingTask(
                dataset_id=dataset_id,
                client_name=client_name,
                job_number=job_number,
                run_id=run_id,
                category=category,
                title=title,
                description=f"Actionable fix for {item_count} items in category '{category}' identified during {_job_names().get(job_number, 'Audit')}.",
                item_count=item_count,
                severity=severity,
                approval_status='approved',
                status='pending',
                approved_by=current_user.username,
                approved_at=datetime.now(timezone.utc),
            )
            db.session.add(task)
        else:
            task.approval_status = 'approved'
            task.status = 'pending'
            task.item_count = item_count
            task.severity = severity
            task.run_id = run_id or task.run_id
            task.approved_by = current_user.username
            task.approved_at = datetime.now(timezone.utc)

        db.session.commit()
        flash(f'Category "{category}" approved! Moved to Pending Tasks for implementation.', 'success')
        return redirect(request.form.get('next') or request.referrer or url_for('pending_tasks'))

    @app.route('/category/disapprove', methods=['POST'])
    @login_required
    def disapprove_category():
        job_number = request.form.get('job_number', type=int)
        category = request.form.get('category', '').strip()

        active_account = _get_active_account()
        dataset_id = active_account.id if active_account else None

        task = PendingTask.query.filter_by(
            dataset_id=dataset_id,
            job_number=job_number,
            category=category
        ).first()

        if task:
            task.approval_status = 'disapproved'
            db.session.commit()

        flash(f'Category "{category}" marked as Disapproved / Skipped. Stays in job dashboard.', 'info')
        return redirect(request.referrer or url_for('dashboard'))

    @app.route('/shared/category/approve/<token>', methods=['POST'])
    def shared_approve_category(token):
        shared = SharedReport.query.filter_by(share_token=token, is_active=True).first_or_404()
        job_number = request.form.get('job_number', type=int, default=1)
        run_id = request.form.get('run_id', type=int, default=shared.run_id)
        category = request.form.get('category', '').strip()
        item_count = request.form.get('item_count', type=int, default=1)
        severity = request.form.get('severity', 'High').strip()

        if not category:
            flash('Invalid category.', 'error')
            return redirect(request.referrer or url_for('view_shared', token=token))

        client_name = shared.client_name or 'Client'
        dataset_id = shared.dataset_id

        task = PendingTask.query.filter_by(
            dataset_id=dataset_id,
            job_number=job_number,
            category=category
        ).first()

        title = f"Fix {category} ({item_count} items)"

        if not task:
            task = PendingTask(
                dataset_id=dataset_id,
                client_name=client_name,
                job_number=job_number,
                run_id=run_id,
                category=category,
                title=title,
                description=f"Actionable fix approved by Client ({client_name}) for '{category}'.",
                item_count=item_count,
                severity=severity,
                approval_status='approved',
                status='pending',
                approved_by=f"Client ({client_name})",
                approved_at=datetime.now(timezone.utc),
            )
            db.session.add(task)
        else:
            task.approval_status = 'approved'
            task.status = 'pending'
            task.approved_by = f"Client ({client_name})"
            task.approved_at = datetime.now(timezone.utc)

        db.session.commit()
        flash(f'Category "{category}" approved for implementation! The SEO development team has been queued.', 'success')
        return redirect(request.referrer or url_for('view_shared', token=token))

    @app.route('/shared/category/disapprove/<token>', methods=['POST'])
    def shared_disapprove_category(token):
        shared = SharedReport.query.filter_by(share_token=token, is_active=True).first_or_404()
        job_number = request.form.get('job_number', type=int, default=1)
        category = request.form.get('category', '').strip()

        task = PendingTask.query.filter_by(
            dataset_id=shared.dataset_id,
            job_number=job_number,
            category=category
        ).first()

        if task:
            task.approval_status = 'disapproved'
            db.session.commit()

        flash(f'Category "{category}" marked as Disapproved / Skipped.', 'info')
        return redirect(request.referrer or url_for('view_shared', token=token))

    # ── Pending Tasks Dashboard ─────────────────────────────────

    @app.route('/pending-tasks')
    @login_required
    def pending_tasks():
        active_account = _get_active_account()
        active_acc_id = active_account.id if active_account else None

        status_filter = request.args.get('status', 'all')
        job_filter = request.args.get('job', type=int)

        query = PendingTask.query
        if active_acc_id:
            query = query.filter_by(dataset_id=active_acc_id)

        if status_filter in ('pending', 'completed', 'verified'):
            query = query.filter_by(status=status_filter)
        elif status_filter == 'disapproved':
            query = query.filter_by(approval_status='disapproved')
        else:
            query = query.filter(PendingTask.approval_status != 'disapproved')

        if job_filter:
            query = query.filter_by(job_number=job_filter)

        tasks = query.order_by(
            PendingTask.status.asc(),
            PendingTask.id.desc()
        ).all()

        base_q = PendingTask.query
        if active_acc_id:
            base_q = base_q.filter_by(dataset_id=active_acc_id)

        pending_count = base_q.filter_by(status='pending', approval_status='approved').count()
        completed_count = base_q.filter_by(status='completed').count()
        verified_count = base_q.filter_by(status='verified').count()

        return render_template('pending_tasks.html',
            tasks=tasks,
            active_dataset=active_account,
            status_filter=status_filter,
            job_filter=job_filter,
            pending_count=pending_count,
            completed_count=completed_count,
            verified_count=verified_count,
            job_names=_job_names(),
        )

    @app.route('/pending-tasks/<int:task_id>/complete', methods=['POST'])
    @login_required
    def complete_pending_task(task_id):
        task = PendingTask.query.get_or_404(task_id)
        if task.dataset_id and not current_user.has_project_access(task.dataset_id):
            abort(403)

        notes = request.form.get('notes', '').strip()
        task.status = 'completed'
        task.completed_by = current_user.username
        task.completed_at = datetime.now(timezone.utc)
        if notes:
            task.developer_notes = notes

        db.session.commit()
        flash(f'Task "{task.title}" marked as Completed! Ready for automated live verification.', 'success')
        return redirect(request.referrer or url_for('pending_tasks'))

    @app.route('/pending-tasks/<int:task_id>/verify', methods=['POST'])
    @login_required
    def verify_pending_task(task_id):
        task = PendingTask.query.get_or_404(task_id)
        if task.dataset_id and not current_user.has_project_access(task.dataset_id):
            abort(403)

        from services.verification_service import verify_task_on_website
        result = verify_task_on_website(task.id)

        if result['success']:
            flash(f"🎉 Verification Succeeded: {result['details']} Task status changed to VERIFIED!", 'success')
        else:
            flash(f"⚠️ Verification Alert: {result['details']}", 'warning')

        return redirect(request.referrer or url_for('pending_tasks'))

    @app.route('/pending-tasks/<int:task_id>/export')
    @login_required
    def export_pending_task(task_id):
        task = PendingTask.query.get_or_404(task_id)
        if task.dataset_id and not current_user.has_project_access(task.dataset_id):
            abort(403)

        from services.export_service import export_task_issues
        bio = export_task_issues(task.id)
        slug = secure_filename(task.category.lower().replace(' ', '_'))
        date_str = datetime.now(timezone.utc).strftime('%Y%m%d')

        return send_file(
            bio,
            as_attachment=True,
            download_name=f"Task_{task.id}_{slug}_{date_str}.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    @app.route('/pending-tasks/<int:task_id>/delete', methods=['POST'])
    @admin_required
    def delete_pending_task(task_id):
        task = PendingTask.query.get_or_404(task_id)
        name = task.title
        db.session.delete(task)
        db.session.commit()
        flash(f'Task "{name}" removed.', 'info')
        return redirect(request.referrer or url_for('pending_tasks'))

    
    @app.route('/api/dashboard-data')
    @login_required
    def api_dashboard_data():
        sessions = WeeklySession.query.order_by(WeeklySession.week_starting).all()
        traffic = TrafficData.query.order_by(TrafficData.change_pct).all()
        
        return jsonify({
            'sessions': {
                'labels': [s.week_starting for s in sessions],
                'data': [s.organic_sessions for s in sessions],
            },
            'traffic': {
                'labels': [t.landing_page for t in traffic[:20]],
                'previous': [t.sessions_previous for t in traffic[:20]],
                'current': [t.sessions_current for t in traffic[:20]],
                'change': [t.change_pct for t in traffic[:20]],
            },
        })
    
    @app.route('/api/job/<int:job_num>/data')
    @login_required
    def api_job_data(job_num):
        run_id = request.args.get('run_id', type=int)
        
        if job_num == 1:
            from jobs.job1_crawl_monitor import get_crawl_summary
            summary = get_crawl_summary(run_id)
            if not summary:
                return jsonify({})
            return jsonify({
                'severity_counts': summary['severity_counts'],
                'issue_type_counts': summary['issue_type_counts'],
                'total': summary['total_issues'],
            })
        
        elif job_num == 2:
            from jobs.job2_gsc_monitor import get_gsc_summary
            summary = get_gsc_summary(run_id)
            if not summary:
                return jsonify({})
            
            anomalies_data = []
            for a in summary['anomalies']:
                anomalies_data.append({
                    'query': a.query,
                    'clicks_current': a.clicks_current,
                    'clicks_previous': a.clicks_previous,
                    'clicks_change': a.clicks_change_pct,
                    'impressions_change': a.impressions_change_pct,
                    'position_current': a.position_current,
                    'position_previous': a.position_previous,
                    'position_change': a.position_change,
                    'alert_level': a.alert_level,
                    'is_branded': a.is_branded,
                })
            
            return jsonify({
                'alert_counts': summary['alert_counts'],
                'anomalies': anomalies_data,
            })
        
        elif job_num == 4:
            from jobs.job4_redirect_monitor import get_redirect_summary
            summary = get_redirect_summary(run_id)
            if not summary:
                return jsonify({})
            return jsonify({
                'result_counts': summary['result_counts'],
                'pass_rate': summary['pass_rate'],
            })
        
        return jsonify({})


def _job_names():
    return {
        1: 'Technical SEO Crawl Monitor',
        2: 'GSC Ranking Anomaly Monitor',
        3: 'Product SEO QA',
        4: 'Redirect/Migration Monitor',
    }


def _job_icons():
    return {
        1: '🔍',
        2: '📊',
        3: '🛍️',
        4: '🔗',
    }


# ── Application Entry Point ────────────────────────────────────

app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5050, use_reloader=False)
