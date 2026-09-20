"""Google Docs integration for generating Monday summary reports."""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def create_summary_doc(google_auth, title, content_sections):
    """Create a Google Doc with the Monday summary.
    
    Args:
        google_auth: GoogleAuthManager instance.
        title: Document title.
        content_sections: List of (heading, body_text) tuples.
    
    Returns:
        Document URL or None.
    """
    try:
        from googleapiclient.discovery import build
        
        creds = google_auth.get_credentials()
        if not creds:
            logger.warning("Google Docs: Not authenticated")
            return None
        
        service = build('docs', 'v1', credentials=creds)
        
        # Create document
        doc = service.documents().create(body={'title': title}).execute()
        doc_id = doc.get('documentId')
        
        # Build content requests
        requests = []
        index = 1
        
        for heading, body in content_sections:
            # Insert heading
            requests.append({
                'insertText': {'location': {'index': index}, 'text': heading + '\n'}
            })
            requests.append({
                'updateParagraphStyle': {
                    'range': {'startIndex': index, 'endIndex': index + len(heading) + 1},
                    'paragraphStyle': {'namedStyleType': 'HEADING_2'},
                    'fields': 'namedStyleType',
                }
            })
            index += len(heading) + 1
            
            # Insert body
            requests.append({
                'insertText': {'location': {'index': index}, 'text': body + '\n\n'}
            })
            index += len(body) + 2
        
        if requests:
            service.documents().batchUpdate(
                documentId=doc_id, body={'requests': requests}
            ).execute()
        
        doc_url = f'https://docs.google.com/document/d/{doc_id}/edit'
        logger.info(f"Created summary doc: {doc_url}")
        return doc_url
    
    except Exception as e:
        logger.error(f"Failed to create Google Doc: {e}")
        return None
