#!/usr/bin/env python3
"""
Helper script to retrieve an existing Google Form as JSON.

Usage:
    python retrieve_form.py <form_id>
    python retrieve_form.py https://docs.google.com/forms/d/<form_id>/edit
"""

import sys
import json
import re
from pathlib import Path
from typing import Optional, Dict, Any
import googleapiclient.discovery
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# Import the authentication setup from the main module
from .google_forms_api import SCOPES, TOKEN_FILE, CREDENTIALS_FILE


class FormRetriever:
    """Helper class to retrieve Google Forms data."""
    
    def __init__(self, credentials_file: Optional[str] = None):
        """Initialize the form retriever.
        
        Args:
            credentials_file: Path to the Google API credentials JSON file.
                If None, uses the default path.
        """
        if credentials_file:
            self.credentials_file = Path(credentials_file)
        else:
            self.credentials_file = CREDENTIALS_FILE
            
        self.creds = None
        self.forms_service = None
    
    def authenticate(self):
        """Authenticate with the Google API using the same method as GoogleFormsAPIClient."""
        if TOKEN_FILE.exists():
            self.creds = Credentials.from_authorized_user_info(
                json.loads(TOKEN_FILE.read_text()), SCOPES
            )
            
        # If credentials don't exist or are invalid, prompt user to authenticate
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                if not self.credentials_file.exists():
                    raise FileNotFoundError(
                        f"Google API credentials file not found at {self.credentials_file}. "
                        "Please obtain credentials from Google Cloud Console and save them."
                    )
                
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.credentials_file), SCOPES
                )
                self.creds = flow.run_local_server(port=0)
                
            # Save the credentials for future use
            TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
            TOKEN_FILE.write_text(json.dumps({
                'token': self.creds.token,
                'refresh_token': self.creds.refresh_token,
                'token_uri': self.creds.token_uri,
                'client_id': self.creds.client_id,
                'client_secret': self.creds.client_secret,
                'scopes': self.creds.scopes,
            }))
        
        # Build the Forms service
        self.forms_service = googleapiclient.discovery.build(
            'forms', 'v1', credentials=self.creds
        )
    
    def extract_form_id(self, form_identifier: str) -> str:
        """Extract form ID from either a form ID or a Google Forms URL.
        
        Args:
            form_identifier: Either a form ID or a full Google Forms URL
            
        Returns:
            The extracted form ID
            
        Raises:
            ValueError: If the form identifier is invalid
        """
        # Check if it's already just a form ID (alphanumeric string)
        if re.match(r'^[a-zA-Z0-9_-]+$', form_identifier):
            return form_identifier
        
        # Try to extract from Google Forms URL
        url_pattern = r'https://docs\.google\.com/forms/d/([a-zA-Z0-9_-]+)'
        match = re.search(url_pattern, form_identifier)
        
        if match:
            return match.group(1)
        
        raise ValueError(
            f"Invalid form identifier: {form_identifier}. "
            "Please provide either a form ID or a valid Google Forms URL."
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
        
        try:
            # Retrieve the form
            form = self.forms_service.forms().get(formId=form_id).execute()
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
    retriever = FormRetriever(credentials_file)
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
    if len(sys.argv) < 2:
        print("Usage: python retrieve_form.py <form_id_or_url> [output_file]")
        print("\nExamples:")
        print("  python retrieve_form.py 1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms")
        print("  python retrieve_form.py https://docs.google.com/forms/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit")
        print("  python retrieve_form.py <form_id> output.json")
        sys.exit(1)
    
    form_identifier = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        form_data = retrieve_form_as_json(form_identifier, output_file=output_file)
        
        # If no output file specified, print to stdout
        if not output_file:
            print(json.dumps(form_data, indent=2, ensure_ascii=False))
            
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main() 