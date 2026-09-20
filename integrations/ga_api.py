"""Google Analytics 4 API integration for organic session data."""

import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def pull_ga_data(google_auth, property_id, days=7):
    """Pull GA4 organic session data by landing page.
    
    Args:
        google_auth: GoogleAuthManager instance.
        property_id: GA4 property ID (e.g., '123456789').
        days: Number of days to pull.
    
    Returns:
        List of dicts or None.
    """
    try:
        from googleapiclient.discovery import build
        
        creds = google_auth.get_credentials()
        if not creds:
            logger.warning("GA4 API: Not authenticated")
            return None
        
        service = build('analyticsdata', 'v1beta', credentials=creds)
        
        end_date = datetime.now().date() - timedelta(days=1)
        start_date = end_date - timedelta(days=days)
        
        request = {
            'dateRanges': [{'startDate': start_date.isoformat(), 'endDate': end_date.isoformat()}],
            'dimensions': [{'name': 'landingPage'}],
            'metrics': [{'name': 'sessions'}],
            'dimensionFilter': {
                'filter': {
                    'fieldName': 'sessionDefaultChannelGroup',
                    'stringFilter': {'matchType': 'EXACT', 'value': 'Organic Search'},
                }
            },
            'limit': 500,
        }
        
        response = service.properties().runReport(
            property=f'properties/{property_id}',
            body=request,
        ).execute()
        
        results = []
        for row in response.get('rows', []):
            results.append({
                'landing_page': row['dimensionValues'][0]['value'],
                'sessions': int(row['metricValues'][0]['value']),
            })
        
        logger.info(f"Pulled {len(results)} landing pages from GA4")
        return results
    
    except Exception as e:
        logger.error(f"Failed to pull GA4 data: {e}")
        return None


def get_ga_properties(google_auth):
    """List available GA4 properties."""
    try:
        from googleapiclient.discovery import build
        
        creds = google_auth.get_credentials()
        if not creds:
            return []
        
        service = build('analyticsadmin', 'v1beta', credentials=creds)
        response = service.accounts().list().execute()
        
        properties = []
        for account in response.get('accounts', []):
            account_name = account['name']
            props = service.properties().list(
                filter=f'parent:{account_name}'
            ).execute()
            for prop in props.get('properties', []):
                properties.append({
                    'id': prop['name'].split('/')[-1],
                    'name': prop.get('displayName', prop['name']),
                })
        
        return properties
    
    except Exception as e:
        logger.error(f"Failed to list GA4 properties: {e}")
        return []
