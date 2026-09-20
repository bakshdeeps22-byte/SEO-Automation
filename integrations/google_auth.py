"""Google OAuth2 flow handler.

Manages the OAuth2 authorization flow for Google APIs
(GSC, GA, Sheets, Docs).
"""

import os
import json
from pathlib import Path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
import logging

logger = logging.getLogger(__name__)


class GoogleAuthManager:
    """Manages Google OAuth2 authentication."""
    
    def __init__(self, credentials_path, token_path, scopes):
        self.credentials_path = Path(credentials_path)
        self.token_path = Path(token_path)
        self.scopes = scopes
        self._credentials = None
    
    @property
    def is_authenticated(self):
        """Check if we have valid credentials."""
        creds = self.get_credentials()
        return creds is not None and creds.valid
    
    def get_credentials(self):
        """Get current credentials, refreshing if needed."""
        if self._credentials and self._credentials.valid:
            return self._credentials
        
        # Try loading from token file
        if self.token_path.exists():
            try:
                self._credentials = Credentials.from_authorized_user_file(
                    str(self.token_path), self.scopes
                )
                
                # Refresh if expired
                if self._credentials and self._credentials.expired and self._credentials.refresh_token:
                    self._credentials.refresh(Request())
                    self._save_token()
                
                if self._credentials and self._credentials.valid:
                    return self._credentials
            except Exception as e:
                logger.error(f"Failed to load/refresh token: {e}")
        
        return None
    
    def create_auth_flow(self, redirect_uri):
        """Create an OAuth2 flow for user authorization.
        
        Args:
            redirect_uri: The callback URL after authorization.
        
        Returns:
            (authorization_url, state) tuple.
        """
        if not self.credentials_path.exists():
            raise FileNotFoundError(f"OAuth credentials not found: {self.credentials_path}")
        
        flow = Flow.from_client_secrets_file(
            str(self.credentials_path),
            scopes=self.scopes,
            redirect_uri=redirect_uri,
        )
        
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent',
        )
        
        return authorization_url, state
    
    def handle_callback(self, authorization_response, redirect_uri):
        """Handle the OAuth2 callback.
        
        Args:
            authorization_response: The full callback URL.
            redirect_uri: The redirect URI used in the flow.
        
        Returns:
            True if successful.
        """
        flow = Flow.from_client_secrets_file(
            str(self.credentials_path),
            scopes=self.scopes,
            redirect_uri=redirect_uri,
        )
        
        flow.fetch_token(authorization_response=authorization_response)
        self._credentials = flow.credentials
        self._save_token()
        
        return True
    
    def disconnect(self):
        """Remove stored credentials."""
        self._credentials = None
        if self.token_path.exists():
            self.token_path.unlink()
    
    def _save_token(self):
        """Save credentials to token file."""
        if self._credentials:
            self.token_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.token_path, 'w') as f:
                f.write(self._credentials.to_json())
