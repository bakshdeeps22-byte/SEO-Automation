"""Google Sheets integration for pushing job results."""

import logging

logger = logging.getLogger(__name__)


def push_to_sheet(google_auth, spreadsheet_id, sheet_name, headers, rows):
    """Push data to a Google Sheet.
    
    Args:
        google_auth: GoogleAuthManager instance.
        spreadsheet_id: Google Sheets spreadsheet ID.
        sheet_name: Name of the sheet/tab.
        headers: List of column headers.
        rows: List of row data (lists).
    """
    try:
        from googleapiclient.discovery import build
        
        creds = google_auth.get_credentials()
        if not creds:
            logger.warning("Google Sheets: Not authenticated")
            return False
        
        service = build('sheets', 'v4', credentials=creds)
        
        # Prepare data
        data = [headers] + rows
        
        body = {
            'values': data
        }
        
        # Clear existing data
        service.spreadsheets().values().clear(
            spreadsheetId=spreadsheet_id,
            range=f'{sheet_name}!A:Z',
        ).execute()
        
        # Write new data
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f'{sheet_name}!A1',
            valueInputOption='RAW',
            body=body,
        ).execute()
        
        logger.info(f"Pushed {len(rows)} rows to Google Sheet '{sheet_name}'")
        return True
    
    except Exception as e:
        logger.error(f"Failed to push to Google Sheet: {e}")
        return False
