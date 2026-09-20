"""Job 4 — Redirect/Migration Regression Monitor.

Checks the old URL mapping to detect redirect failures, wrong destinations,
and chain issues using deterministic pass/fail rules.
"""

import pandas as pd
from datetime import datetime, timezone
from models import db, RedirectCheck, JobRun
from jobs import now_utc
import time
import logging

logger = logging.getLogger(__name__)


def run_redirect_monitor(dataset_path, triggered_by='manual', dataset_id=None):
    """Execute the redirect regression monitor.
    
    Args:
        dataset_path: Path to the active Excel dataset.
        triggered_by: 'manual' or 'scheduled'.
        dataset_id: Optional ID of the dataset/account.
    
    Returns:
        JobRun instance with results.
    """
    start_time = time.time()
    run_date = now_utc()
    
    job_run = JobRun(
        job_name='Redirect/Migration Regression Monitor',
        job_number=4,
        run_date=run_date,
        status='running',
        triggered_by=triggered_by,
        dataset_id=dataset_id,
    )
    db.session.add(job_run)
    db.session.commit()
    
    try:
        df = pd.read_excel(dataset_path, sheet_name='old_url_map')
        logger.info(f"Job 4: Loaded {len(df)} redirect mappings from old_url_map sheet")
        
        checks = []
        
        for _, row in df.iterrows():
            old_url = str(row.get('old_url', ''))
            expected_url = str(row.get('expected_new_url', ''))
            first_status = int(row.get('first_status_code', 0))
            hops = int(row.get('redirect_hops', 0)) if pd.notna(row.get('redirect_hops')) else 0
            final_url = str(row.get('final_url', '')) if pd.notna(row.get('final_url')) else ''
            
            # Apply deterministic rules
            pass_fail, failure_reason = _check_redirect(
                expected_url=expected_url,
                actual_status=first_status,
                actual_final_url=final_url,
                hops=hops,
            )
            
            check = RedirectCheck(
                run_id=job_run.id,
                run_date=run_date,
                old_url=old_url,
                expected_url=expected_url,
                expected_status=301,
                actual_status=first_status,
                actual_final_url=final_url,
                redirect_hops=hops,
                pass_fail=pass_fail,
                failure_reason=failure_reason,
            )
            checks.append(check)
        
        db.session.add_all(checks)
        
        # Count results
        result_counts = {'PASS': 0, 'CRITICAL': 0, 'WARNING': 0}
        for c in checks:
            result_counts[c.pass_fail] = result_counts.get(c.pass_fail, 0) + 1
        
        critical_count = result_counts.get('CRITICAL', 0)
        
        summary_parts = ['Redirect Regression Report']
        summary_parts.append('─' * 30)
        summary_parts.append(f'✅ {result_counts["PASS"]} passing redirects')
        if result_counts['CRITICAL'] > 0:
            summary_parts.append(f'🔴 {result_counts["CRITICAL"]} CRITICAL failures')
        if result_counts['WARNING'] > 0:
            summary_parts.append(f'🟡 {result_counts["WARNING"]} warnings')
        summary_parts.append(f'\nTotal: {len(checks)} redirect mappings checked')
        
        job_run.status = 'completed'
        job_run.issues_found = result_counts.get('CRITICAL', 0) + result_counts.get('WARNING', 0)
        job_run.critical_count = critical_count
        job_run.summary = '\n'.join(summary_parts)
        job_run.duration_seconds = round(time.time() - start_time, 2)
        
        db.session.commit()
        logger.info(f"Job 4 completed: {job_run.issues_found} issues in {job_run.duration_seconds}s")
        
        return job_run
    
    except Exception as e:
        job_run.status = 'failed'
        job_run.summary = f'Error: {str(e)}'
        job_run.duration_seconds = round(time.time() - start_time, 2)
        db.session.commit()
        logger.error(f"Job 4 failed: {e}", exc_info=True)
        raise


def _check_redirect(expected_url, actual_status, actual_final_url, hops):
    """Apply deterministic redirect check rules.
    
    Rules:
    - Expected 301 → actual 301, correct dest = PASS
    - Expected 301 → 404 = CRITICAL
    - Expected 301 → 302 = WARNING  
    - 301 → wrong destination = CRITICAL
    - redirect hops > 1 = WARNING (even if final dest is correct)
    """
    reasons = []
    result = 'PASS'
    
    # Check 1: Did the redirect return a 404?
    if actual_status == 404:
        return 'CRITICAL', 'Redirect returns 404 — old URL is completely broken'
    
    # Check 2: Did the redirect return a 5xx?
    if actual_status >= 500:
        return 'CRITICAL', f'Server error {actual_status} — redirect is broken'
    
    # Check 3: Is it a 302 instead of 301?
    if actual_status == 302:
        result = 'WARNING'
        reasons.append('Using temporary 302 redirect instead of permanent 301')
    
    # Check 4: Does the final URL match expected?
    if actual_final_url and expected_url:
        # Normalize URLs for comparison
        norm_expected = _normalize_url(expected_url)
        norm_actual = _normalize_url(actual_final_url)
        
        if norm_expected != norm_actual:
            result = 'CRITICAL'
            reasons.append(f'Wrong destination: expected {expected_url}, got {actual_final_url}')
    
    # Check 5: Too many redirect hops?
    if hops > 1:
        if result != 'CRITICAL':
            result = 'WARNING'
        reasons.append(f'{hops} redirect hops (should be 1)')
    
    if not reasons:
        reasons.append('301 redirect to correct destination')
    
    return result, '; '.join(reasons)


def _normalize_url(url):
    """Normalize a URL for comparison."""
    url = url.rstrip('/')
    url = url.replace('https://', '').replace('http://', '')
    url = url.replace('www.', '')
    return url.lower()


def get_redirect_summary(run_id=None):
    """Get summary stats for the redirect monitor."""
    if run_id:
        checks = RedirectCheck.query.filter_by(run_id=run_id).all()
    else:
        latest_run = JobRun.query.filter_by(job_number=4, status='completed')\
            .order_by(JobRun.run_date.desc()).first()
        if not latest_run:
            return None
        checks = RedirectCheck.query.filter_by(run_id=latest_run.id).all()
        run_id = latest_run.id
    
    result_counts = {'PASS': 0, 'CRITICAL': 0, 'WARNING': 0}
    for c in checks:
        result_counts[c.pass_fail] = result_counts.get(c.pass_fail, 0) + 1
    
    return {
        'run_id': run_id,
        'total_checks': len(checks),
        'result_counts': result_counts,
        'checks': checks,
        'pass_rate': round((result_counts['PASS'] / len(checks)) * 100, 1) if checks else 0,
    }
