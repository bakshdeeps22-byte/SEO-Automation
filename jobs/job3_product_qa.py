"""Job 3 — Product SEO QA.

Checks product pages for SEO quality issues and generates
AI-suggested corrections that require human approval.
"""

import pandas as pd
from datetime import datetime, timezone
from models import db, ProductQAIssue, JobRun
from jobs import now_utc
import time
import re
import logging

logger = logging.getLogger(__name__)

# Ideal ranges for product page metadata
TITLE_MIN_LENGTH = 30
TITLE_MAX_LENGTH = 60
META_MIN_LENGTH = 120
META_MAX_LENGTH = 160
PRODUCT_MIN_WORD_COUNT = 200

# Generic titles that indicate missing/default metadata
GENERIC_TITLE_PATTERNS = [
    r'^(meridian pet supply)$',  # Just the brand name, nothing else
    r'^(home|product|page|untitled)',
]


def run_product_qa(dataset_path, triggered_by='manual', dataset_id=None):
    """Execute the product SEO QA job.
    
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
        job_name='Product Page SEO QA',
        job_number=3,
        run_date=run_date,
        status='running',
        triggered_by=triggered_by,
        dataset_id=dataset_id,
    )
    db.session.add(job_run)
    db.session.commit()
    
    try:
        df = pd.read_excel(dataset_path, sheet_name='crawl')
        
        # Filter to product/variant templates with 200 status
        products = df[
            (df['template'].isin(['product', 'variant'])) &
            (df['status_code'] == 200)
        ].copy()
        
        logger.info(f"Job 3: Found {len(products)} product pages to QA")
        
        issues = []
        
        for _, row in products.iterrows():
            url = str(row.get('url', ''))
            title = str(row.get('title', '')) if pd.notna(row.get('title')) else ''
            title_length = int(row.get('title_length', 0)) if pd.notna(row.get('title_length')) else len(title)
            meta_present = bool(row.get('meta_description_present', False))
            canonical = str(row.get('canonical', '')) if pd.notna(row.get('canonical')) else ''
            indexable = bool(row.get('indexable', True))
            word_count = int(row.get('word_count', 0)) if pd.notna(row.get('word_count')) else 0
            template = str(row.get('template', ''))
            
            # Extract product name from URL
            product_name = _extract_product_name(url)
            
            # Check 1: Title length
            if title_length > TITLE_MAX_LENGTH:
                suggested = _shorten_title(title)
                issues.append(ProductQAIssue(
                    run_id=job_run.id, run_date=run_date, url=url,
                    product_name=product_name, template=template,
                    issue_type='Title Too Long',
                    current_value=f'{title} ({title_length} chars)',
                    suggested_value=f'{suggested} ({len(suggested)} chars)',
                    status='pending',
                    ai_confidence=0.85,
                ))
            elif title_length < TITLE_MIN_LENGTH:
                suggested = _expand_title(title, product_name)
                issues.append(ProductQAIssue(
                    run_id=job_run.id, run_date=run_date, url=url,
                    product_name=product_name, template=template,
                    issue_type='Title Too Short',
                    current_value=f'{title} ({title_length} chars)',
                    suggested_value=f'{suggested} ({len(suggested)} chars)',
                    status='pending',
                    ai_confidence=0.75,
                ))
            
            # Check 2: Generic/duplicate title
            if _is_generic_title(title):
                suggested = _generate_product_title(product_name, url)
                issues.append(ProductQAIssue(
                    run_id=job_run.id, run_date=run_date, url=url,
                    product_name=product_name, template=template,
                    issue_type='Generic/Default Title',
                    current_value=title,
                    suggested_value=suggested,
                    status='pending',
                    ai_confidence=0.70,
                ))
            
            # Check 3: Missing meta description
            if not meta_present:
                issues.append(ProductQAIssue(
                    run_id=job_run.id, run_date=run_date, url=url,
                    product_name=product_name, template=template,
                    issue_type='Missing Meta Description',
                    current_value='(none)',
                    suggested_value=f'Shop {product_name} at Meridian Pet Supply. Free shipping on orders over $49. Quality pet products delivered to your door.',
                    status='pending',
                    ai_confidence=0.65,
                ))
            
            # Check 4: Canonical issues (variant with self-referencing canonical)
            if template == 'variant' and canonical and '?variant=' in canonical:
                parent_url = canonical.split('?')[0]
                issues.append(ProductQAIssue(
                    run_id=job_run.id, run_date=run_date, url=url,
                    product_name=product_name, template=template,
                    issue_type='Variant Self-Canonical',
                    current_value=f'Canonical: {canonical}',
                    suggested_value=f'Canonical should point to parent: {parent_url}',
                    status='pending',
                    ai_confidence=0.90,
                ))
            
            # Check 5: Non-indexable product
            if not indexable:
                issues.append(ProductQAIssue(
                    run_id=job_run.id, run_date=run_date, url=url,
                    product_name=product_name, template=template,
                    issue_type='Non-Indexable Product',
                    current_value='noindex',
                    suggested_value='Remove noindex — product pages should be indexable unless out of stock',
                    status='pending',
                    ai_confidence=0.95,
                ))
            
            # Check 6: Thin content
            if word_count < PRODUCT_MIN_WORD_COUNT:
                issues.append(ProductQAIssue(
                    run_id=job_run.id, run_date=run_date, url=url,
                    product_name=product_name, template=template,
                    issue_type='Thin Product Content',
                    current_value=f'{word_count} words',
                    suggested_value=f'Expand product description to at least {PRODUCT_MIN_WORD_COUNT} words with features, benefits, and usage instructions',
                    status='pending',
                    ai_confidence=0.60,
                ))
        
        db.session.add_all(issues)
        
        critical_count = len([i for i in issues if i.issue_type in ('Non-Indexable Product', 'Generic/Default Title')])
        
        summary_parts = ['Product SEO QA Report']
        summary_parts.append('─' * 30)
        
        issue_types = {}
        for i in issues:
            issue_types[i.issue_type] = issue_types.get(i.issue_type, 0) + 1
        
        for itype, count in sorted(issue_types.items(), key=lambda x: -x[1]):
            summary_parts.append(f'{count} {itype.lower()} issues')
        summary_parts.append(f'\n{len(issues)} total issues across {len(products)} products')
        summary_parts.append(f'{len([i for i in issues if i.status == "pending"])} pending human approval')
        
        job_run.status = 'completed'
        job_run.issues_found = len(issues)
        job_run.critical_count = critical_count
        job_run.summary = '\n'.join(summary_parts)
        job_run.duration_seconds = round(time.time() - start_time, 2)
        
        db.session.commit()
        logger.info(f"Job 3 completed: {len(issues)} issues found in {job_run.duration_seconds}s")
        
        return job_run
    
    except Exception as e:
        job_run.status = 'failed'
        job_run.summary = f'Error: {str(e)}'
        job_run.duration_seconds = round(time.time() - start_time, 2)
        db.session.commit()
        logger.error(f"Job 3 failed: {e}", exc_info=True)
        raise


def _extract_product_name(url):
    """Extract a human-readable product name from URL."""
    # Get last path segment
    path = url.rstrip('/').split('/')[-1]
    # Remove query params
    path = path.split('?')[0]
    # Convert hyphens to spaces, title case
    name = path.replace('-', ' ').title()
    return name


def _is_generic_title(title):
    """Check if a title is generic/default."""
    title_lower = title.strip().lower()
    for pattern in GENERIC_TITLE_PATTERNS:
        if re.match(pattern, title_lower):
            return True
    return False


def _shorten_title(title):
    """Generate a shortened title suggestion."""
    # Remove brand suffix if present
    if '|' in title:
        parts = title.split('|')
        main = parts[0].strip()
        brand = parts[-1].strip()
        if len(main) <= TITLE_MAX_LENGTH:
            return main
        # Truncate main part
        return main[:TITLE_MAX_LENGTH - len(brand) - 3] + ' | ' + brand
    return title[:TITLE_MAX_LENGTH - 3] + '...'


def _expand_title(title, product_name):
    """Generate an expanded title suggestion."""
    if '|' in title:
        return title
    return f'{product_name} | Meridian Pet Supply'


def _generate_product_title(product_name, url):
    """Generate a title for a product with a generic/missing title."""
    return f'{product_name} | Meridian Pet Supply'


def get_product_qa_summary(run_id=None):
    """Get summary stats for the product QA job."""
    if run_id:
        issues = ProductQAIssue.query.filter_by(run_id=run_id).all()
    else:
        latest_run = JobRun.query.filter_by(job_number=3, status='completed')\
            .order_by(JobRun.run_date.desc()).first()
        if not latest_run:
            return None
        issues = ProductQAIssue.query.filter_by(run_id=latest_run.id).all()
        run_id = latest_run.id
    
    status_counts = {'pending': 0, 'approved': 0, 'rejected': 0}
    issue_type_counts = {}
    
    for issue in issues:
        status_counts[issue.status] = status_counts.get(issue.status, 0) + 1
        issue_type_counts[issue.issue_type] = issue_type_counts.get(issue.issue_type, 0) + 1
    
    return {
        'run_id': run_id,
        'total_issues': len(issues),
        'status_counts': status_counts,
        'issue_type_counts': issue_type_counts,
        'issues': issues,
    }
