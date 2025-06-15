#!/usr/bin/env python3
"""
Standalone script to retrieve an existing Google Form as JSON.

This script can be used independently without the cc_converter module.

Setup:
1. Install required packages:
   pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib

2. Get Google API credentials:
   - Go to Google Cloud Console
   - Create a project or select existing one
   - Enable Google Forms API and Google Drive API
   - Create credentials (OAuth 2.0 Client ID for desktop application)
   - Download the credentials JSON file

Usage:
    python retrieve_google_form.py <form_id_or_url> [output_file]
    
Examples:
    python retrieve_google_form.py 1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms
    python retrieve_google_form.py https://docs.google.com/forms/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit
    python retrieve_google_form.py <form_id> form_data.json
"""

import sys
import json
import re
import os
from pathlib import Path
from typing import Optional, Dict, Any

try:
    import googleapiclient.discovery
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
except ImportError as e:
    print("Error: Required Google API packages not found.")
    print("Please install them with:")
    print("pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib")
    sys.exit(1)


# Define the required scopes
SCOPES = [
    'https://www.googleapis.com/auth/forms',
    'https://www.googleapis.com/auth/drive'
]

# Default paths for credentials and token storage
DEFAULT_TOKEN_FILE = Path.home() / '.google_forms_retriever' / 'token.json'
DEFAULT_CREDENTIALS_FILE = Path.home() / '.google_forms_retriever' / 'credentials.json'


class GoogleFormRetriever:
    """Standalone class to retrieve Google Forms data."""
    
    def __init__(self, credentials_file: Optional[str] = None):
        """Initialize the form retriever.
        
        Args:
            credentials_file: Path to the Google API credentials JSON file.
                If None, looks for credentials in default location or current directory.
        """
        self.credentials_file = self._find_credentials_file(credentials_file)
        self.token_file = DEFAULT_TOKEN_FILE
        self.creds = None
        self.forms_service = None
    
    def _find_credentials_file(self, credentials_file: Optional[str]) -> Path:
        """Find the credentials file in various locations."""
        if credentials_file:
            path = Path(credentials_file)
            if path.exists():
                return path
            else:
                raise FileNotFoundError(f"Credentials file not found: {credentials_file}")
        
        # Check common locations
        possible_paths = [
            DEFAULT_CREDENTIALS_FILE,
            Path("credentials.json"),
            Path("client_secret.json"),
            Path.home() / "credentials.json",
        ]
        
        for path in possible_paths:
            if path.exists():
                return path
        
        raise FileNotFoundError(
            "Google API credentials file not found. Please:\n"
            "1. Download credentials from Google Cloud Console\n"
            "2. Save as 'credentials.json' in current directory, or\n"
            "3. Specify path with --credentials argument\n"
            f"4. Or save to default location: {DEFAULT_CREDENTIALS_FILE}"
        )
    
    def authenticate(self):
        """Authenticate with the Google API."""
        # Load existing credentials if available
        if self.token_file.exists():
            try:
                self.creds = Credentials.from_authorized_user_info(
                    json.loads(self.token_file.read_text()), SCOPES
                )
            except Exception as e:
                print(f"Warning: Could not load saved credentials: {e}")
                self.creds = None
        
        # If credentials don't exist or are invalid, authenticate
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                try:
                    self.creds.refresh(Request())
                except Exception as e:
                    print(f"Could not refresh credentials: {e}")
                    self.creds = None
            
            if not self.creds:
                print(f"Starting authentication flow using credentials from: {self.credentials_file}")
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.credentials_file), SCOPES
                )
                self.creds = flow.run_local_server(port=0)
            
            # Save the credentials for future use
            self.token_file.parent.mkdir(parents=True, exist_ok=True)
            self.token_file.write_text(json.dumps({
                'token': self.creds.token,
                'refresh_token': self.creds.refresh_token,
                'token_uri': self.creds.token_uri,
                'client_id': self.creds.client_id,
                'client_secret': self.creds.client_secret,
                'scopes': self.creds.scopes,
            }))
            print(f"Credentials saved to: {self.token_file}")
        
        # Build the Forms service
        self.forms_service = googleapiclient.discovery.build(
            'forms', 'v1', credentials=self.creds
        )
        print("Successfully authenticated with Google Forms API")
    
    def extract_form_id(self, form_identifier: str) -> str:
        """Extract form ID from either a form ID or a Google Forms URL.
        
        Args:
            form_identifier: Either a form ID or a full Google Forms URL
            
        Returns:
            The extracted form ID
            
        Raises:
            ValueError: If the form identifier is invalid
        """
        # Check if it's already just a form ID (alphanumeric string with underscores and dashes)
        if re.match(r'^[a-zA-Z0-9_-]+$', form_identifier):
            return form_identifier
        
        # Try to extract from Google Forms URL patterns
        url_patterns = [
            r'https://docs\.google\.com/forms/d/([a-zA-Z0-9_-]+)',
            r'https://forms\.gle/([a-zA-Z0-9_-]+)',
        ]
        
        for pattern in url_patterns:
            match = re.search(pattern, form_identifier)
            if match:
                return match.group(1)
        
        raise ValueError(
            f"Invalid form identifier: {form_identifier}\n"
            "Please provide either:\n"
            "- A form ID (e.g., 1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms)\n"
            "- A Google Forms URL (e.g., https://docs.google.com/forms/d/.../edit)\n"
            "- A forms.gle short URL"
        )
    
    def get_form(self, form_identifier: str) -> Dict[str, Any]:
        """Retrieve a Google Form as JSON.
        
        Args:
            form_identifier: Either a form ID or a Google Forms URL
            
        Returns:
            Dictionary containing the form data
            
        Raises:
            Exception: If the form cannot be retrieved
        """
        if not self.forms_service:
            self.authenticate()
        
        form_id = self.extract_form_id(form_identifier)
        print(f"Retrieving form with ID: {form_id}")
        
        try:
            # Retrieve the form
            form = self.forms_service.forms().get(formId=form_id).execute()
            print(f"Successfully retrieved form: {form.get('info', {}).get('title', 'Untitled')}")
            return form
        except Exception as e:
            raise Exception(f"Failed to retrieve form with ID {form_id}: {str(e)}")


def retrieve_form_as_json(
    form_identifier: str, 
    credentials_file: Optional[str] = None,
    output_file: Optional[str] = None,
    pretty_print: bool = True
) -> Dict[str, Any]:
    """Retrieve a Google Form as JSON.
    
    Args:
        form_identifier: Either a form ID or a Google Forms URL
        credentials_file: Path to the Google API credentials JSON file
        output_file: Optional path to save the JSON output
        pretty_print: Whether to format the JSON with indentation
        
    Returns:
        Dictionary containing the form data
    """
    retriever = GoogleFormRetriever(credentials_file)
    form_data = retriever.get_form(form_identifier)
    
    # Convert to JSON string
    if pretty_print:
        json_output = json.dumps(form_data, indent=2, ensure_ascii=False)
    else:
        json_output = json.dumps(form_data, ensure_ascii=False)
    
    # Save to file if specified
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(json_output)
        print(f"Form data saved to: {output_file}")
    
    return form_data


def main():
    """Main function for command-line usage."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Retrieve a Google Form as JSON",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s 1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms
  %(prog)s https://docs.google.com/forms/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit
  %(prog)s <form_id> --output form_data.json
  %(prog)s <form_id> --credentials /path/to/credentials.json
        """
    )
    
    parser.add_argument(
        'form_identifier',
        help='Google Form ID or URL'
    )
    parser.add_argument(
        '--output', '-o',
        help='Output file path (if not specified, prints to stdout)'
    )
    parser.add_argument(
        '--credentials', '-c',
        help='Path to Google API credentials JSON file'
    )
    parser.add_argument(
        '--compact',
        action='store_true',
        help='Output compact JSON without indentation'
    )
    
    # Handle legacy positional argument for output file
    if len(sys.argv) == 3 and not sys.argv[2].startswith('-'):
        # Legacy usage: script form_id output_file
        args = parser.parse_args([sys.argv[1], '--output', sys.argv[2]])
    else:
        args = parser.parse_args()
    
    try:
        form_data = retrieve_form_as_json(
            args.form_identifier,
            credentials_file=args.credentials,
            output_file=args.output,
            pretty_print=not args.compact
        )
        
        # If no output file specified, print to stdout
        if not args.output:
            if args.compact:
                print(json.dumps(form_data, ensure_ascii=False))
            else:
                print(json.dumps(form_data, indent=2, ensure_ascii=False))
            
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main() 