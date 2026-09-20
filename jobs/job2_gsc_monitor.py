"""Job 2 — GSC Ranking Anomaly Monitor.

Compares current vs previous period GSC data to detect meaningful
ranking declines using deterministic rules.
"""

import pandas as pd
from datetime import datetime, timezone
from models import db, RankingAnomaly, JobRun
from jobs import now_utc
import time
import logging

logger = logging.getLogger(__name__)

# Brand terms for this dataset
BRAND_TERMS = ['meridian', 'meridianpet']


def run_gsc_monitor(dataset_path, triggered_by='manual', dataset_id=None):
    """Execute the GSC ranking anomaly monitor.
    
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
        job_name='GSC Ranking Anomaly Monitor',
        job_number=2,
        run_date=run_date,
        status='running',
        triggered_by=triggered_by,
        dataset_id=dataset_id,
    )
    db.session.add(job_run)
    db.session.commit()
    
    try:
        df = pd.read_excel(dataset_path, sheet_name='gsc_queries')
        logger.info(f"Job 2: Loaded {len(df)} queries from gsc_queries sheet")
        
        anomalies = []
        
        for _, row in df.iterrows():
            query = str(row.get('query', ''))
            
            clicks_prev = int(row.get('clicks_mar_2026', 0))
            clicks_curr = int(row.get('clicks_aug_2026', 0))
            impr_prev = int(row.get('impressions_mar_2026', 0))
            impr_curr = int(row.get('impressions_aug_2026', 0))
            pos_prev = float(row.get('avg_position_mar_2026', 0))
            pos_curr = float(row.get('avg_position_aug_2026', 0))
            
            # Calculate changes
            clicks_change = _pct_change(clicks_prev, clicks_curr)
            impr_change = _pct_change(impr_prev, impr_curr)
            pos_change = pos_curr - pos_prev  # positive = worsened
            
            # Detect if branded
            is_branded = any(term in query.lower() for term in BRAND_TERMS)
            
            # Apply detection rules
            alert_level, alert_reason = _classify_anomaly(
                clicks_change, impr_change, pos_change, is_branded
            )
            
            anomaly = RankingAnomaly(
                run_id=job_run.id,
                run_date=run_date,
                query=query,
                is_branded=is_branded,
                clicks_current=clicks_curr,
                clicks_previous=clicks_prev,
                clicks_change_pct=round(clicks_change, 1),
                impressions_current=impr_curr,
                impressions_previous=impr_prev,
                impressions_change_pct=round(impr_change, 1),
                position_current=pos_curr,
                position_previous=pos_prev,
                position_change=round(pos_change, 1),
                alert_level=alert_level,
                alert_reason=alert_reason,
            )
            anomalies.append(anomaly)
        
        db.session.add_all(anomalies)
        
        # Count alerts
        alert_counts = {}
        for a in anomalies:
            alert_counts[a.alert_level] = alert_counts.get(a.alert_level, 0) + 1
        
        critical_count = alert_counts.get('HIGH', 0)
        total_alerts = sum(v for k, v in alert_counts.items() if k != 'STABLE' and k != 'IMPROVED')
        
        summary_parts = ['GSC Ranking Anomaly Report']
        summary_parts.append('─' * 30)
        for level in ['HIGH', 'MEDIUM', 'WATCH', 'IMPROVED', 'STABLE']:
            count = alert_counts.get(level, 0)
            if count > 0:
                summary_parts.append(f'{count} {level.lower()} priority queries')
        
        job_run.status = 'completed'
        job_run.issues_found = total_alerts
        job_run.critical_count = critical_count
        job_run.summary = '\n'.join(summary_parts)
        job_run.duration_seconds = round(time.time() - start_time, 2)
        
        db.session.commit()
        logger.info(f"Job 2 completed: {total_alerts} anomalies found in {job_run.duration_seconds}s")
        
        return job_run
    
    except Exception as e:
        job_run.status = 'failed'
        job_run.summary = f'Error: {str(e)}'
        job_run.duration_seconds = round(time.time() - start_time, 2)
        db.session.commit()
        logger.error(f"Job 2 failed: {e}", exc_info=True)
        raise


def _pct_change(old, new):
    """Calculate percentage change."""
    if old == 0:
        return 0 if new == 0 else 100.0
    return ((new - old) / old) * 100


def _classify_anomaly(clicks_change, impr_change, pos_change, is_branded):
    """Apply deterministic rules to classify ranking anomalies.
    
    Rules:
    - HIGH: clicks decline >= 30% AND impressions decline < 20% AND position worsened >= 3
    - MEDIUM: clicks decline >= 20% AND position worsened >= 2
    - WATCH: clicks decline >= 10%
    - IMPROVED: clicks increased >= 10%
    - STABLE: everything else
    
    Branded queries get downgraded one level (brand traffic is more stable).
    """
    reasons = []
    
    # Check for declines
    if clicks_change <= -30 and impr_change > -20 and pos_change >= 3:
        level = 'HIGH'
        reasons.append(f'Clicks dropped {abs(clicks_change):.0f}% while impressions only changed {impr_change:.0f}%')
        reasons.append(f'Position worsened by {pos_change:.1f} positions')
        reasons.append('This suggests a ranking issue, not a demand/seasonality change')
    elif clicks_change <= -20 and pos_change >= 2:
        level = 'MEDIUM'
        reasons.append(f'Clicks dropped {abs(clicks_change):.0f}% with position worsening by {pos_change:.1f}')
    elif clicks_change <= -10:
        level = 'WATCH'
        reasons.append(f'Clicks declined {abs(clicks_change):.0f}% — monitoring recommended')
    elif clicks_change >= 10:
        level = 'IMPROVED'
        reasons.append(f'Clicks improved {clicks_change:.0f}%')
    else:
        level = 'STABLE'
        reasons.append('No significant changes detected')
    
    # Branded queries are less actionable
    if is_branded and level in ('HIGH', 'MEDIUM'):
        level = 'WATCH'
        reasons.append('(Branded query — downgraded priority)')
    
    return level, '; '.join(reasons)


def get_gsc_summary(run_id=None):
    """Get summary stats for the GSC monitor."""
    if run_id:
        anomalies = db.session.query(RankingAnomaly).filter_by(run_id=run_id).all()
    else:
        latest_run = JobRun.query.filter_by(job_number=2, status='completed')\
            .order_by(JobRun.run_date.desc()).first()
        if not latest_run:
            return None
        anomalies = db.session.query(RankingAnomaly).filter_by(run_id=latest_run.id).all()
        run_id = latest_run.id
    
    alert_counts = {'HIGH': 0, 'MEDIUM': 0, 'WATCH': 0, 'IMPROVED': 0, 'STABLE': 0}
    for a in anomalies:
        alert_counts[a.alert_level] = alert_counts.get(a.alert_level, 0) + 1
    
    # Separate branded vs non-branded
    non_branded = [a for a in anomalies if not a.is_branded]
    branded = [a for a in anomalies if a.is_branded]
    
    return {
        'run_id': run_id,
        'total_queries': len(anomalies),
        'alert_counts': alert_counts,
        'anomalies': anomalies,
        'non_branded': non_branded,
        'branded': branded,
        'non_branded_alerts': len([a for a in non_branded if a.alert_level in ('HIGH', 'MEDIUM', 'WATCH')]),
    }
