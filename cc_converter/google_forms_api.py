from pathlib import Path
import os
import json
import mimetypes
import base64
import zipfile
import shutil
from typing import Dict, Optional, List, Union, Any, Tuple

import googleapiclient.discovery
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload
from io import BytesIO
import requests

from .models import Assessment, TextRun, ImageInfo, QuestionType, TextContent, Item


# Define the required scopes
SCOPES = [
    'https://www.googleapis.com/auth/forms',
    'https://www.googleapis.com/auth/drive'
]

# Path where credentials will be stored
TOKEN_FILE = Path.home() / '.cc_converter' / 'token.json'
CREDENTIALS_FILE = Path.home() / '.cc_converter' / 'credentials.json'


class GoogleFormsAPIClient:
    """Client for interacting with the Google Forms API."""
    
    def __init__(self, credentials_file: Optional[str] = None, storage_folder: Optional[str] = None):
        """Initialize the API client.
        
        Args:
            credentials_file: Path to the Google API credentials JSON file.
                If None, uses the default path.
            storage_folder: Name of the Google Drive folder to store form data and images.
                If provided, creates a folder structure: storage_folder/forms/ and storage_folder/images/
        """
        if credentials_file:
            self.credentials_file = Path(credentials_file)
        else:
            self.credentials_file = CREDENTIALS_FILE
            
        # Create directory for credentials if it doesn't exist
        self.credentials_file.parent.mkdir(parents=True, exist_ok=True)
        
        self.creds = None
        self.forms_service = None
        self.drive_service = None
        
        # Setup Google Drive storage folder
        self.storage_folder_name = storage_folder
        self.storage_folder_id = None
        self.images_folder_id = None
    
    def authenticate(self):
        """Authenticate with the Google API."""
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
        
        # Build services
        self.forms_service = googleapiclient.discovery.build(
            'forms', 'v1', credentials=self.creds
        )
        self.drive_service = googleapiclient.discovery.build(
            'drive', 'v3', credentials=self.creds
        )
        
        # Setup Drive folder structure if storage folder is specified
        if self.storage_folder_name:
            self._setup_drive_folders()
    
    def _find_or_create_drive_folder(self, folder_name: str, parent_id: Optional[str] = None) -> str:
        """Find or create a folder in Google Drive.
        
        Args:
            folder_name: Name of the folder to find or create.
            parent_id: ID of the parent folder. If None, creates in root.
            
        Returns:
            ID of the found or created folder.
        """
        # Search for existing folder
        query = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        if parent_id:
            query += f" and '{parent_id}' in parents"
        
        results = self.drive_service.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name)',
            pageSize=1
        ).execute()
        
        # If folder exists, return its ID
        if results.get('files'):
            return results['files'][0]['id']
        
        # Create new folder
        folder_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        if parent_id:
            folder_metadata['parents'] = [parent_id]
        
        folder = self.drive_service.files().create(
            body=folder_metadata,
            fields='id'
        ).execute()
        
        print(f"Created Drive folder: {folder_name}")
        return folder['id']
    
    def _setup_drive_folders(self):
        """Setup the folder structure in Google Drive."""
        if not self.drive_service:
            return
            
        # Create main storage folder
        self.storage_folder_id = self._find_or_create_drive_folder(self.storage_folder_name)
        
        # Create images subfolder
        self.images_folder_id = self._find_or_create_drive_folder("images", self.storage_folder_id)
    
    def create_form(self, assessment: Assessment, resource_zip: Optional[zipfile.ZipFile] = None) -> str:
        """Create a new Google Form from an Assessment.
        
        Args:
            assessment: The Assessment to convert.
            resource_zip: An optional zipfile containing resources such as images.
            
        Returns:
            str: The URL of the created form.
        """
        if not self.forms_service:
            self.authenticate()
            
        # Create the form with only the title as required by the API
        form = self.forms_service.forms().create(body={
            'info': {
                'title': assessment.title,
                'documentTitle': assessment.title
            }
        }).execute()
        
        form_id = form['formId']
        
        # Prepare the batch update request
        requests = []
        
        # Set quiz settings in the batch update
        requests.append({
            'updateSettings': {
                'settings': {
                    'quizSettings': {
                        'isQuiz': True
                    }
                },
                'updateMask': 'quizSettings.isQuiz'
            }
        })
        
        # Process each section
        for section_idx, section in enumerate(assessment.sections, 1):
            # Add section header if needed for multi-section assessments
            if len(assessment.sections) > 1:
                requests.append({
                    'createItem': {
                        'item': {
                            'title': f"Section {section_idx}",
                            'description': "",
                            'pageBreakItem': {}
                        },
                        'location': {'index': len(requests)}
                    }
                })
            
            # Process each item
            for item in section.items:
                question_requests = self._create_item_requests(item, resource_zip)
                requests.extend(question_requests)
        
        # Execute batch update
        if requests:
            updated_form = self.forms_service.forms().batchUpdate(
                formId=form_id,
                body={'requests': requests}
            ).execute()
        
        # Move the form to the storage folder if specified
        if self.storage_folder_id:
            try:
                # Move the form file to the storage folder
                self.drive_service.files().update(
                    fileId=form_id,
                    addParents=self.storage_folder_id,
                    removeParents='root',
                    fields='id'
                ).execute()
                print(f"Moved form '{assessment.title}' to storage folder")
            except Exception as e:
                print(f"Warning: Could not move form to storage folder: {str(e)}")
        
        # Return the form URL
        return f"https://docs.google.com/forms/d/{form_id}/edit"
    
    def _create_item_requests(
        self, item: Item, resource_zip: Optional[zipfile.ZipFile]
    ) -> List[Dict[str, Any]]:
        """Create API requests for a question item.
        
        Args:
            item: The assessment item to convert.
            resource_zip: Optional ZIP file containing resources.
            
        Returns:
            List of request objects for the Forms API.
        """
        requests = []
        
        # Convert text content to plain text and extract images
        question_text, question_images = self._extract_text_and_images(item.text, resource_zip)
        
        # Create base question structure
        if item.question_type == QuestionType.MULTIPLE_CHOICE:
            question_item = {
                'title': question_text,
                'questionItem': {
                    'question': {
                        'required': True,
                        'choiceQuestion': {
                            'type': 'RADIO',
                            'options': [],
                            'shuffle': False,
                        }
                    }
                }
            }
            
            # Add options
            for option in item.response_options:
                option_text, option_images = self._extract_text_and_images(option.text, resource_zip)
                question_item['questionItem']['question']['choiceQuestion']['options'].append({
                    'value': option_text
                })
                
            # Set up feedback for correct answers
            if item.correct_response:
                question_item['questionItem']['question']['grading'] = {
                    'pointValue': 1,
                    'correctAnswers': {
                        'answers': []
                    }
                }
                
                for option in item.response_options:
                    if option.ident == item.correct_response:
                        option_text, _ = self._extract_text_and_images(option.text, resource_zip)
                        question_item['questionItem']['question']['grading']['correctAnswers']['answers'].append({
                            'value': option_text
                        })
                        break
                        
        elif item.question_type == QuestionType.ESSAY:
            question_item = {
                'title': question_text,
                'questionItem': {
                    'question': {
                        'required': True,
                        'textQuestion': {
                            'paragraph': True
                        }
                    }
                }
            }
        
        # Create the main question
        requests.append({
            'createItem': {
                'item': question_item,
                'location': {'index': len(requests)}
            }
        })
        
        # Add question images if any
        for img_data in question_images:
            img_url = self._upload_image_to_drive(img_data)
            if img_url:
                # Add image item right after the question
                requests.append({
                    'createItem': {
                        'item': {
                            'imageItem': {
                                'image': {
                                    'sourceUri': img_url,
                                    'altText': 'Question image'
                                }
                            }
                        },
                        'location': {'index': len(requests)}
                    }
                })
        
        return requests
    
    def _extract_text_and_images(
        self, content_list: List[TextContent], resource_zip: Optional[zipfile.ZipFile]
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Extract text and images from content list.
        
        Args:
            content_list: List of TextContent objects.
            resource_zip: Optional ZIP file containing resources.
            
        Returns:
            Tuple of (plain text, list of image data dictionaries)
        """
        text_parts = []
        images = []
        
        for content in content_list:
            if isinstance(content, TextRun):
                # Replace newlines with spaces to avoid Google Forms API error
                text_parts.append(content.text)
                # pass
            elif isinstance(content, ImageInfo):
                # Extract the image data
                img_data = self._extract_image_data(content.src, resource_zip)
                if img_data:
                    images.append(img_data)
                
        return "".join(text_parts), images
    
    def _extract_image_data(
        self, img_path: str, resource_zip: Optional[zipfile.ZipFile]
    ) -> Optional[Dict[str, Any]]:
        """Extract image data from a path or URL.
        
        Args:
            img_path: Path to the image, either in the zip file or a URL.
            resource_zip: Optional ZIP file containing resources.
            
        Returns:
            Dictionary with image data or None if extraction failed.
        """
        # Handle URLs
        if img_path.startswith('http://') or img_path.startswith('https://'):
            try:
                response = requests.get(img_path, timeout=10)
                response.raise_for_status()
                
                # Get MIME type
                content_type = response.headers.get('Content-Type', 'image/jpeg')
                
                return {
                    'name': os.path.basename(img_path),
                    'content': BytesIO(response.content),
                    'mime_type': content_type
                }
            except Exception as e:
                print(f"Error downloading image from URL: {img_path} - {str(e)}")
                return None
        
        # Handle images from ZIP file
        elif resource_zip:
            try:
                # Extract image from ZIP
                with resource_zip.open(img_path) as img_file:
                    content = img_file.read()
                
                # Determine MIME type
                mime_type, _ = mimetypes.guess_type(img_path)
                if not mime_type:
                    mime_type = 'image/jpeg'  # Default to JPEG
                
                return {
                    'name': os.path.basename(img_path),
                    'content': BytesIO(content),
                    'mime_type': mime_type
                }
            except (KeyError, zipfile.BadZipFile) as e:
                print(f"Error extracting image from zip: {img_path} - {str(e)}")
                return None
        
        return None
    
    def _upload_image_to_drive(self, img_data: Dict[str, Any]) -> Optional[str]:
        """Upload an image to Google Drive and return the web content link.
        
        Args:
            img_data: Dictionary with image data.
            
        Returns:
            Link to the uploaded image or None if upload failed.
        """
        if not self.drive_service:
            self.authenticate()
            
        try:
            # Check if the image already exists in the images folder
            if self.images_folder_id:
                query = f"name = '{img_data['name']}' and '{self.images_folder_id}' in parents and trashed = false"
            else:
                query = f"name = '{img_data['name']}' and trashed = false"
                
            results = self.drive_service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, webContentLink)',
                pageSize=1
            ).execute()
            
            # If the image already exists, return its link
            if results.get('files'):
                existing_file = results['files'][0]
                
                # If the file exists but doesn't have a webContentLink, update permissions
                if 'webContentLink' not in existing_file:
                    self.drive_service.permissions().create(
                        fileId=existing_file['id'],
                        body={'role': 'reader', 'type': 'anyone'},
                        fields='id'
                    ).execute()
                    
                    # Get the updated file with webContentLink
                    existing_file = self.drive_service.files().get(
                        fileId=existing_file['id'],
                        fields='webContentLink'
                    ).execute()
                
                print(f"Using existing image file: {img_data['name']}")
                return existing_file.get('webContentLink', '').replace('&export=download', '')
            
            # Create a media upload object
            media = MediaIoBaseUpload(
                img_data['content'],
                mimetype=img_data['mime_type'],
                resumable=True
            )
            
            # Upload to Drive
            file_metadata = {
                'name': img_data['name'],
                'mimeType': img_data['mime_type']
            }
            
            # If we have an images folder, upload there
            if self.images_folder_id:
                file_metadata['parents'] = [self.images_folder_id]
            
            uploaded_file = self.drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, webContentLink',
                supportsAllDrives=True
            ).execute()
            
            # Make the file publicly accessible for embedding
            self.drive_service.permissions().create(
                fileId=uploaded_file['id'],
                body={'role': 'reader', 'type': 'anyone'},
                fields='id'
            ).execute()
            
            # Get the webContentLink
            file = self.drive_service.files().get(
                fileId=uploaded_file['id'],
                fields='webContentLink'
            ).execute()
            
            print(f"Uploaded image to Drive: {img_data['name']}")
            # Return the web content link
            return file.get('webContentLink', '').replace('&export=download', '')
        
        except Exception as e:
            print(f"Error uploading image to Drive: {str(e)}")
            return None


def convert_assessment_to_google_forms_api(
    assessment: Assessment,
    resource_zip: Optional[Union[str, zipfile.ZipFile]] = None,
    credentials_file: Optional[str] = None,
    storage_folder: Optional[str] = None
) -> str:
    """Convert an assessment to a Google Form using the Forms API.
    
    Args:
        assessment: The Assessment object to convert.
        resource_zip: Path to or instance of a ZIP file containing resources.
        credentials_file: Path to the Google API credentials JSON file.
        storage_folder: Name of the Google Drive folder to store form data and images.
        
    Returns:
        URL of the created Google Form.
    """
    # Open the resource zip if a path was provided
    zip_obj = None
    if resource_zip is not None and isinstance(resource_zip, str):
        zip_obj = zipfile.ZipFile(resource_zip, 'r')
    else:
        zip_obj = resource_zip
    
    try:
        # Create the client and authenticate
        client = GoogleFormsAPIClient(credentials_file, storage_folder)
        client.authenticate()
        
        # Create the form and return the URL
        return client.create_form(assessment, zip_obj)
    finally:
        # Close the zip file if we opened it
        if zip_obj is not None and isinstance(resource_zip, str):
            zip_obj.close()


def convert_cartridge_to_google_forms_api(
    cartridge_path: Union[str, Path],
    credentials_file: Optional[str] = None,
    storage_folder: Optional[str] = None,
    limit: Optional[int] = None
) -> List[str]:
    """Convert all assessments in a Common Cartridge file to Google Forms.
    
    Args:
        cartridge_path: Path to the .imscc file.
        credentials_file: Path to the Google API credentials JSON file.
        storage_folder: Name of the Google Drive folder to store form data and images.
        limit: Maximum number of assessments to process (default: all).
        
    Returns:
        List of URLs of created Google Forms.
    """
    from .xml_parser import parse_cartridge
    
    # Convert path strings to Path objects
    if isinstance(cartridge_path, str):
        cartridge_path = Path(cartridge_path)
    
    # Parse the cartridge file
    assessments = parse_cartridge(cartridge_path, limit=limit)
    
    # Open the cartridge as a zip file for resource extraction
    form_urls = []
    with zipfile.ZipFile(cartridge_path, 'r') as resource_zip:
        # Create the client and authenticate once
        client = GoogleFormsAPIClient(credentials_file, storage_folder)
        client.authenticate()
        
        # Convert each assessment
        for assessment in assessments:
            url = client.create_form(assessment, resource_zip)
            form_urls.append(url)
            print(f"Created form: {url}")
    
    return form_urls 