"""Job 1 — Weekly Technical SEO Crawl Monitor.

Reads the 'crawl' sheet from the active dataset and evaluates each URL
against 11 technical SEO checks, generating prioritized issue reports.
"""

import pandas as pd
from datetime import datetime, timezone
from models import db, CrawlIssue, JobRun
from jobs import SEVERITY_WEIGHTS, ISSUE_EXPLANATIONS, now_utc
import time
import logging

logger = logging.getLogger(__name__)


def run_crawl_monitor(dataset_path, triggered_by='manual', dataset_id=None):
    """Execute the technical crawl monitor job.
    
    Args:
        dataset_path: Path to the active Excel dataset.
        triggered_by: 'manual' or 'scheduled'.
        dataset_id: Optional ID of the dataset/account.
    
    Returns:
        JobRun instance with results.
    """
    start_time = time.time()
    run_date = now_utc()
    
    # Create job run record
    job_run = JobRun(
        job_name='Technical SEO Crawl Monitor',
        job_number=1,
        run_date=run_date,
        status='running',
        triggered_by=triggered_by,
        dataset_id=dataset_id,
    )
    db.session.add(job_run)
    db.session.commit()
    
    try:
        # Read crawl data
        df = pd.read_excel(dataset_path, sheet_name='crawl')
        logger.info(f"Job 1: Loaded {len(df)} URLs from crawl sheet")
        
        issues = []
        
        for _, row in df.iterrows():
            url = str(row.get('url', ''))
            template = str(row.get('template', ''))
            status_code = int(row.get('status_code', 200))
            title = str(row.get('title', '')) if pd.notna(row.get('title')) else ''
            title_length = int(row.get('title_length', 0)) if pd.notna(row.get('title_length')) else len(title)
            meta_present = bool(row.get('meta_description_present', False))
            canonical = str(row.get('canonical', '')) if pd.notna(row.get('canonical')) else ''
            indexable = bool(row.get('indexable', True))
            robots_blocked = bool(row.get('robots_blocked', False))
            word_count = int(row.get('word_count', 0)) if pd.notna(row.get('word_count')) else 0
            inlinks = int(row.get('inlinks', 0)) if pd.notna(row.get('inlinks')) else 0
            in_sitemap = bool(row.get('in_sitemap', False))
            
            # Check 1: 4xx errors
            if 400 <= status_code < 500:
                issues.append(_create_issue(
                    run_id=job_run.id, run_date=run_date, url=url,
                    template=template, issue='4xx Error',
                    severity='Critical',
                    detail=f'HTTP {status_code}',
                ))
            
            # Check 2: 5xx errors
            if 500 <= status_code < 600:
                issues.append(_create_issue(
                    run_id=job_run.id, run_date=run_date, url=url,
                    template=template, issue='5xx Error',
                    severity='Critical',
                    detail=f'HTTP {status_code}',
                ))
            
            # Check 3: Redirects
            if 300 <= status_code < 400:
                redirect_target = str(row.get('redirect_target', '')) if pd.notna(row.get('redirect_target')) else ''
                issues.append(_create_issue(
                    run_id=job_run.id, run_date=run_date, url=url,
                    template=template, issue='Redirect',
                    severity='Medium',
                    detail=f'HTTP {status_code} → {redirect_target[:80]}',
                ))
            
            # Only check on-page issues for 200 responses
            if status_code == 200:
                # Check 4: Missing title
                if not title or title.strip() == '':
                    issues.append(_create_issue(
                        run_id=job_run.id, run_date=run_date, url=url,
                        template=template, issue='Missing Title',
                        severity='High',
                    ))
                
                # Check 5: Title too long
                elif title_length > 60:
                    issues.append(_create_issue(
                        run_id=job_run.id, run_date=run_date, url=url,
                        template=template, issue='Title Too Long',
                        severity='Medium',
                        detail=f'{title_length} chars: "{title[:60]}..."',
                    ))
                
                # Check 6: Missing meta description
                if not meta_present:
                    issues.append(_create_issue(
                        run_id=job_run.id, run_date=run_date, url=url,
                        template=template, issue='Missing Meta Description',
                        severity='High',
                    ))
                
                # Check 7: Missing canonical
                if not canonical or canonical.strip() == '':
                    issues.append(_create_issue(
                        run_id=job_run.id, run_date=run_date, url=url,
                        template=template, issue='Missing Canonical',
                        severity='High',
                    ))
                
                # Check 8: Non-indexable
                if not indexable:
                    issues.append(_create_issue(
                        run_id=job_run.id, run_date=run_date, url=url,
                        template=template, issue='Non-Indexable',
                        severity='Critical',
                    ))
                
                # Check 9: Robots blocked
                if robots_blocked:
                    issues.append(_create_issue(
                        run_id=job_run.id, run_date=run_date, url=url,
                        template=template, issue='Robots Blocked',
                        severity='Critical',
                    ))
                
                # Check 10: Zero internal links
                if inlinks == 0:
                    issues.append(_create_issue(
                        run_id=job_run.id, run_date=run_date, url=url,
                        template=template, issue='Zero Internal Links',
                        severity='High',
                    ))
                
                # Check 11: Not in sitemap
                if not in_sitemap:
                    issues.append(_create_issue(
                        run_id=job_run.id, run_date=run_date, url=url,
                        template=template, issue='Not in Sitemap',
                        severity='Medium',
                    ))
                
                # Check 12: Thin content
                if word_count < 200:
                    issues.append(_create_issue(
                        run_id=job_run.id, run_date=run_date, url=url,
                        template=template, issue='Thin Content',
                        severity='Medium',
                        detail=f'Only {word_count} words',
                    ))
        
        # Bulk insert issues
        db.session.add_all(issues)
        
        # Calculate summary counts
        severity_counts = {}
        issue_type_counts = {}
        for issue in issues:
            severity_counts[issue.severity] = severity_counts.get(issue.severity, 0) + 1
            issue_type_counts[issue.issue] = issue_type_counts.get(issue.issue, 0) + 1
        
        critical_count = severity_counts.get('Critical', 0)
        
        # Build summary
        summary_parts = ['SEO Health Report']
        summary_parts.append('─' * 30)
        for issue_type, count in sorted(issue_type_counts.items(), key=lambda x: -x[1]):
            summary_parts.append(f'{count} {issue_type.lower()} issues')
        summary_parts.append(f'\nTotal: {len(issues)} issues across {len(df)} URLs')
        
        job_run.status = 'completed'
        job_run.issues_found = len(issues)
        job_run.critical_count = critical_count
        job_run.summary = '\n'.join(summary_parts)
        job_run.duration_seconds = round(time.time() - start_time, 2)
        
        db.session.commit()
        logger.info(f"Job 1 completed: {len(issues)} issues found in {job_run.duration_seconds}s")
        
        return job_run
    
    except Exception as e:
        job_run.status = 'failed'
        job_run.summary = f'Error: {str(e)}'
        job_run.duration_seconds = round(time.time() - start_time, 2)
        db.session.commit()
        logger.error(f"Job 1 failed: {e}", exc_info=True)
        raise


def _create_issue(run_id, run_date, url, template, issue, severity, detail=None):
    """Create a CrawlIssue instance with explanations."""
    info = ISSUE_EXPLANATIONS.get(issue, {})
    priority_score = SEVERITY_WEIGHTS.get(severity, 1)
    
    return CrawlIssue(
        run_id=run_id,
        run_date=run_date,
        url=url,
        template=template,
        issue=issue,
        severity=severity,
        priority_score=priority_score,
        why_it_matters=info.get('why', ''),
        recommended_action=detail + '. ' + info.get('action', '') if detail else info.get('action', ''),
        owner='SEO Team',
        detected_date=run_date,
    )


def get_crawl_summary(run_id=None):
    """Get summary stats for the crawl monitor.
    
    Returns dict with counts per issue type and severity.
    """
    if run_id:
        issues = CrawlIssue.query.filter_by(run_id=run_id).all()
    else:
        # Get latest run
        latest_run = JobRun.query.filter_by(job_number=1, status='completed')\
            .order_by(JobRun.run_date.desc()).first()
        if not latest_run:
            return None
        issues = CrawlIssue.query.filter_by(run_id=latest_run.id).all()
        run_id = latest_run.id
    
    severity_counts = {'Critical': 0, 'High': 0, 'Medium': 0, 'Low': 0}
    issue_type_counts = {}
    
    for issue in issues:
        severity_counts[issue.severity] = severity_counts.get(issue.severity, 0) + 1
        issue_type_counts[issue.issue] = issue_type_counts.get(issue.issue, 0) + 1
    
    return {
        'run_id': run_id,
        'total_issues': len(issues),
        'severity_counts': severity_counts,
        'issue_type_counts': issue_type_counts,
        'issues': issues,
    }
