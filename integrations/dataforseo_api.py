"""DataforSEO API client for SERP tracking, on-page audit, and redirect checking."""

import requests
import logging
from base64 import b64encode

logger = logging.getLogger(__name__)

API_BASE = 'https://api.dataforseo.com/v3'


class DataforSEOClient:
    """REST client for DataforSEO API."""
    
    def __init__(self, login, password):
        self.login = login
        self.password = password
        self._session = requests.Session()
        creds = b64encode(f'{login}:{password}'.encode()).decode()
        self._session.headers.update({
            'Authorization': f'Basic {creds}',
            'Content-Type': 'application/json',
        })
    
    @property
    def is_configured(self):
        return bool(self.login and self.password)
    
    def test_connection(self):
        """Test API connection.
        
        Returns:
            (success, message) tuple.
        """
        if not self.is_configured:
            return False, 'API credentials not configured'
        
        try:
            resp = self._session.get(f'{API_BASE}/appendix/user_data')
            data = resp.json()
            
            if data.get('status_code') == 20000:
                balance = data.get('tasks', [{}])[0].get('result', [{}])[0].get('money', {})
                return True, f'Connected. Balance: ${balance.get("balance", "N/A")}'
            else:
                return False, data.get('status_message', 'Unknown error')
        
        except Exception as e:
            return False, str(e)
    
    def check_redirect_chain(self, url):
        """Check the redirect chain for a URL.
        
        Returns:
            Dict with redirect chain info.
        """
        try:
            payload = [{'url': url}]
            resp = self._session.post(
                f'{API_BASE}/on_page/redirect_chains',
                json=payload,
            )
            data = resp.json()
            
            if data.get('status_code') == 20000:
                tasks = data.get('tasks', [])
                if tasks and tasks[0].get('result'):
                    return tasks[0]['result'][0]
            
            return None
        
        except Exception as e:
            logger.error(f"DataforSEO redirect check failed: {e}")
            return None
    
    def on_page_audit(self, url):
        """Run an on-page SEO audit for a URL.
        
        Returns:
            Dict with audit results.
        """
        try:
            payload = [{'url': url, 'max_crawl_pages': 1}]
            resp = self._session.post(
                f'{API_BASE}/on_page/task_post',
                json=payload,
            )
            data = resp.json()
            
            if data.get('status_code') == 20000:
                return data.get('tasks', [{}])[0]
            
            return None
        
        except Exception as e:
            logger.error(f"DataforSEO on-page audit failed: {e}")
            return None
    
    def serp_check(self, keyword, location_code=2840, language_code='en'):
        """Check SERP rankings for a keyword.
        
        Args:
            keyword: Search query.
            location_code: Location (2840 = US).
            language_code: Language code.
        
        Returns:
            Dict with SERP results.
        """
        try:
            payload = [{
                'keyword': keyword,
                'location_code': location_code,
                'language_code': language_code,
            }]
            resp = self._session.post(
                f'{API_BASE}/serp/google/organic/live/advanced',
                json=payload,
            )
            data = resp.json()
            
            if data.get('status_code') == 20000:
                return data.get('tasks', [{}])[0].get('result', [{}])[0]
            
            return None
        
        except Exception as e:
            logger.error(f"DataforSEO SERP check failed: {e}")
            return None
