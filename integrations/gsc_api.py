"""Google Search Console API integration for live data pulls."""

import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def pull_gsc_data(google_auth, site_url, days=7):
    """Pull GSC query performance data.
    
    Args:
        google_auth: GoogleAuthManager instance.
        site_url: The GSC property URL.
        days: Number of days for the current period.
    
    Returns:
        List of dicts with query performance data, or None.
    """
    try:
        from googleapiclient.discovery import build
        
        creds = google_auth.get_credentials()
        if not creds:
            logger.warning("GSC API: Not authenticated")
            return None
        
        service = build('searchconsole', 'v1', credentials=creds)
        
        # Current period
        end_date = datetime.now().date() - timedelta(days=3)  # GSC has 3-day lag
        start_date = end_date - timedelta(days=days)
        
        # Previous period
        prev_end = start_date - timedelta(days=1)
        prev_start = prev_end - timedelta(days=days)
        
        # Pull current period
        current_data = _query_gsc(service, site_url, 
                                   start_date.isoformat(), end_date.isoformat())
        
        # Pull previous period
        previous_data = _query_gsc(service, site_url,
                                    prev_start.isoformat(), prev_end.isoformat())
        
        # Merge data
        results = _merge_periods(current_data, previous_data)
        
        logger.info(f"Pulled {len(results)} queries from GSC")
        return results
    
    except Exception as e:
        logger.error(f"Failed to pull GSC data: {e}")
        return None


def _query_gsc(service, site_url, start_date, end_date):
    """Execute a GSC query."""
    request = {
        'startDate': start_date,
        'endDate': end_date,
        'dimensions': ['query'],
        'rowLimit': 1000,
    }
    
    response = service.searchanalytics().query(
        siteUrl=site_url, body=request
    ).execute()
    
    results = {}
    for row in response.get('rows', []):
        query = row['keys'][0]
        results[query] = {
            'clicks': row.get('clicks', 0),
            'impressions': row.get('impressions', 0),
            'position': row.get('position', 0),
        }
    
    return results


def _merge_periods(current, previous):
    """Merge current and previous period data."""
    all_queries = set(list(current.keys()) + list(previous.keys()))
    
    results = []
    for query in all_queries:
        curr = current.get(query, {'clicks': 0, 'impressions': 0, 'position': 0})
        prev = previous.get(query, {'clicks': 0, 'impressions': 0, 'position': 0})
        
        results.append({
            'query': query,
            'clicks_current': curr['clicks'],
            'clicks_previous': prev['clicks'],
            'impressions_current': curr['impressions'],
            'impressions_previous': prev['impressions'],
            'position_current': curr['position'],
            'position_previous': prev['position'],
        })
    
    return results


def get_gsc_properties(google_auth):
    """List available GSC properties.
    
    Returns:
        List of site URLs.
    """
    try:
        from googleapiclient.discovery import build
        
        creds = google_auth.get_credentials()
        if not creds:
            return []
        
        service = build('searchconsole', 'v1', credentials=creds)
        sites = service.sites().list().execute()
        
        return [s['siteUrl'] for s in sites.get('siteEntry', [])]
    
    except Exception as e:
        logger.error(f"Failed to list GSC properties: {e}")
        return []
