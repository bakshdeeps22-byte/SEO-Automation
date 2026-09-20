"""APScheduler configuration for Monday 10 AM automated runs."""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import logging

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def init_scheduler(app):
    """Initialize and start the scheduler.
    
    Args:
        app: Flask application instance.
    """
    from config.settings import Config
    
    # Configure scheduler
    scheduler.configure(
        timezone=Config.SCHEDULER_TIMEZONE,
    )
    
    # Add the Monday morning job
    scheduler.add_job(
        func=_run_all_jobs,
        trigger=CronTrigger(
            day_of_week=Config.SCHEDULER_DAY_OF_WEEK,
            hour=Config.SCHEDULER_HOUR,
            minute=Config.SCHEDULER_MINUTE,
            timezone=Config.SCHEDULER_TIMEZONE,
        ),
        id='monday_seo_automation',
        name='Monday SEO Automation',
        replace_existing=True,
        kwargs={'app': app},
    )
    
    scheduler.start()
    
    next_run = scheduler.get_job('monday_seo_automation').next_run_time
    logger.info(f"Scheduler started. Next run: {next_run}")
    
    return scheduler


def _run_all_jobs(app):
    """Run all 4 jobs sequentially within the Flask app context."""
    with app.app_context():
        from models import db, Dataset
        from jobs.job1_crawl_monitor import run_crawl_monitor
        from jobs.job2_gsc_monitor import run_gsc_monitor
        from jobs.job3_product_qa import run_product_qa
        from jobs.job4_redirect_monitor import run_redirect_monitor
        
        # Get active dataset
        active_dataset = Dataset.query.filter_by(is_active=True).first()
        if not active_dataset:
            logger.error("No active dataset found. Skipping scheduled run.")
            return
        
        dataset_path = active_dataset.file_path
        logger.info(f"Running all jobs with dataset: {dataset_path}")
        
        jobs = [
            ('Job 1 - Crawl Monitor', run_crawl_monitor),
            ('Job 2 - GSC Monitor', run_gsc_monitor),
            ('Job 3 - Product QA', run_product_qa),
            ('Job 4 - Redirect Monitor', run_redirect_monitor),
        ]
        
        for job_name, job_func in jobs:
            try:
                logger.info(f"Starting {job_name}...")
                job_func(dataset_path, triggered_by='scheduled')
                logger.info(f"{job_name} completed successfully")
            except Exception as e:
                logger.error(f"{job_name} failed: {e}", exc_info=True)
        
        logger.info("All scheduled jobs completed")


def get_next_run_time():
    """Get the next scheduled run time."""
    job = scheduler.get_job('monday_seo_automation')
    if job and job.next_run_time:
        return job.next_run_time
    return None


def run_all_jobs_now(app):
    """Manually trigger all jobs immediately."""
    _run_all_jobs(app)
