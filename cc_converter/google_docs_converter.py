from pathlib import Path
from typing import Dict, Optional, List, Tuple, Union
import zipfile
import io
import base64
import os
import mimetypes
import requests
from io import BytesIO

from .models import Assessment, QuestionType, TextRun, TextStyle, ImageInfo, TextContent


class GoogleDocsConverter:
    """Converter for Assessment objects to Google Docs using Google Docs API."""

    def __init__(self, font_mapping: Optional[Dict[str, str]] = None, storage_folder: Optional[str] = None):
        """Initialize the converter.

        Args:
            font_mapping: An optional mapping from font names in the source to
                font names in Google Docs.
            storage_folder: Name of the Google Drive folder to store images.
        """
        self.font_mapping = font_mapping or {}
        self.service = None
        self.drive_service = None
        self.storage_folder_name = storage_folder
        self.storage_folder_id = None
        self.images_folder_id = None

    def authenticate(self, credentials_path: str = None, token_path: str = None):
        """Authenticate with Google Docs API.
        
        Args:
            credentials_path: Path to credentials.json file
            token_path: Path to store/load token.json file
        """
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
        except ImportError:
            raise ImportError(
                "Google API libraries are required. Install with: "
                "pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client"
            )

        # Scopes required for Google Docs API and Drive API
        SCOPES = [
            'https://www.googleapis.com/auth/documents',
            'https://www.googleapis.com/auth/drive',
            'https://www.googleapis.com/auth/drive.file'
        ]
        
        creds = None
        token_path = token_path or 'token.json'
        
        # Load existing token if available
        if Path(token_path).exists():
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        
        # If there are no (valid) credentials available, let the user log in
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                credentials_path = credentials_path or 'credentials.json'
                if not Path(credentials_path).exists():
                    raise FileNotFoundError(
                        f"Credentials file not found at {credentials_path}. "
                        "Please download it from Google Cloud Console."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
                creds = flow.run_local_server(port=0)
            
            # Save the credentials for the next run
            with open(token_path, 'w') as token:
                token.write(creds.to_json())

        self.service = build('docs', 'v1', credentials=creds)
        self.drive_service = build('drive', 'v3', credentials=creds)
        
        # Setup Drive folders if storage folder is specified
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

    def _extract_image_data(
        self, img_path: str, resource_zip: Optional[zipfile.ZipFile]
    ) -> Optional[Dict[str, any]]:
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

    def _upload_image_to_drive(self, img_data: Dict[str, any]) -> Optional[str]:
        """Upload an image to Google Drive and return the web content link.
        
        Args:
            img_data: Dictionary with image data.
            
        Returns:
            Link to the uploaded image or None if upload failed.
        """
        if not self.drive_service:
            return None
            
        try:
            from googleapiclient.http import MediaIoBaseUpload
            
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

    def convert_assessment(
        self, 
        assessment: Assessment, 
        document_title: str,
        resource_zip: Optional[zipfile.ZipFile] = None,
        is_answer_key: bool = False
    ) -> str:
        """Convert an Assessment object to a Google Doc.

        Args:
            assessment: The Assessment object to convert.
            document_title: The title for the Google Doc.
            resource_zip: An optional zipfile containing resources such as images.
            is_answer_key: Whether to include answer keys for multiple choice questions.
            
        Returns:
            The document ID of the created Google Doc.
        """
        if not self.service:
            raise RuntimeError("Must authenticate with Google Docs API first. Call authenticate() method.")

        # Create a new document
        doc = self.service.documents().create(body={'title': document_title}).execute()
        document_id = doc.get('documentId')

        # Build the content requests for text first
        text_requests = []
        
        # Add title
        text_requests.append({
            'insertText': {
                'location': {'index': 1},
                'text': f"{assessment.title}\n\n"
            }
        })

        # Format title as heading
        text_requests.append({
            'updateParagraphStyle': {
                'range': {'startIndex': 1, 'endIndex': len(assessment.title) + 1},
                'paragraphStyle': {
                    'namedStyleType': 'HEADING_1'
                },
                'fields': 'namedStyleType'
            }
        })

        current_index = len(assessment.title) + 3  # After title and two newlines
        image_insertion_data = []  # List to track where images need to be inserted

        # Process all questions in order
        question_number = 1
        for section in assessment.sections:
            for question in section.items:
                # Extract question content and images first
                question_content, question_images = self._extract_text_and_images(question.text, resource_zip)
                
                # For answer key, we'll handle the answer marking in the numbering
                if is_answer_key and question.question_type == QuestionType.MULTIPLE_CHOICE:
                    # Find correct answer
                    correct_option_idx = next(
                        (idx for idx, opt in enumerate(question.response_options) 
                         if opt.ident == question.correct_response), None
                    )
                    answer_prefix = f"[{chr(65 + correct_option_idx)}] " if correct_option_idx is not None else ""
                else:
                    answer_prefix = ""
                
                # Add the blank line after the number
                full_question = answer_prefix + question_content + " _______ \n"
                
                # Store image insertion data for later
                if question_images:
                    for img in question_images:
                        image_insertion_data.append({
                            'image': img,
                            'index': current_index + len(full_question)
                        })
                
                text_requests.append({
                    'insertText': {
                        'location': {'index': current_index},
                        'text': full_question
                    }
                })
                
                # Apply native numbered list to question
                text_requests.append({
                    'createParagraphBullets': {
                        'range': {
                            'startIndex': current_index,
                            'endIndex': current_index + len(full_question) - 1
                        },
                        'bulletPreset': 'NUMBERED_DECIMAL_ALPHA_ROMAN'
                    }
                })
                
                current_index += len(full_question)
                
                # Add answer options for multiple choice questions
                if question.question_type == QuestionType.MULTIPLE_CHOICE:
                    for opt_idx, option in enumerate(question.response_options):
                        option_content, option_images = self._extract_text_and_images(option.text, resource_zip)
                        option_text = f"{option_content}\n"
                        
                        # Store image insertion data for later
                        if option_images:
                            for img in option_images:
                                image_insertion_data.append({
                                    'image': img,
                                    'index': current_index + len(option_text)
                                })
                        
                        text_requests.append({
                            'insertText': {
                                'location': {'index': current_index},
                                'text': option_text
                            }
                        })
                        
                        # Apply native numbered list to answer option
                        text_requests.append({
                            'createParagraphBullets': {
                                'range': {
                                    'startIndex': current_index,
                                    'endIndex': current_index + len(option_text) - 1
                                },
                                'bulletPreset': 'NUMBERED_DECIMAL_ALPHA_ROMAN'
                            }
                        })
                        
                        # Add indentation for answer options
                        text_requests.append({
                            'updateParagraphStyle': {
                                'range': {
                                    'startIndex': current_index,
                                    'endIndex': current_index + len(option_text) - 1
                                },
                                'paragraphStyle': {
                                    'indentFirstLine': {'magnitude': 36, 'unit': 'PT'},
                                    'indentStart': {'magnitude': 36, 'unit': 'PT'}
                                },
                                'fields': 'indentFirstLine,indentStart'
                            }
                        })
                        
                        current_index += len(option_text)
                
                # Add space between questions
                text_requests.append({
                    'insertText': {
                        'location': {'index': current_index},
                        'text': "\n"
                    }
                })
                current_index += 1
                question_number += 1

        # Execute all text requests in batch
        if text_requests:
            self.service.documents().batchUpdate(
                documentId=document_id,
                body={'requests': text_requests}
            ).execute()

        # Now handle image insertions
        if image_insertion_data and self.drive_service:
            # Sort images by index in reverse order to maintain correct positions
            image_insertion_data.sort(key=lambda x: x['index'], reverse=True)
            
            for img_data in image_insertion_data:
                img_info = img_data['image']
                # Upload image to Drive
                img_url = self._upload_image_to_drive(img_info['data'])
                if img_url:
                    # Insert image into document
                    # Note: We insert images after the text content, not at the exact character position
                    # This ensures the images appear near the related text
                    self._insert_image_in_document(
                        document_id, 
                        img_url, 
                        img_data['index'],
                        img_info['alt_text'],
                        img_info['width'],
                        img_info['height']
                    )

        return document_id

    def _extract_text_and_images(
        self, content_list: List[TextContent], resource_zip: Optional[zipfile.ZipFile]
    ) -> Tuple[str, List[Dict[str, any]]]:
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
                text_parts.append(content.text)
            elif isinstance(content, ImageInfo):
                # Extract the image data
                img_data = self._extract_image_data(content.src, resource_zip)
                if img_data:
                    images.append({
                        'data': img_data,
                        'alt_text': f'Image: {img_data["name"]}',
                        'width': content.width,
                        'height': content.height
                    })
                else:
                    # Fallback to text placeholder if image extraction fails
                    text_parts.append(f"[Image: {content.src}]")
                
        return "".join(text_parts), images

    def _insert_image_in_document(self, document_id: str, image_url: str, index: int, alt_text: str = "", width: Optional[int] = None, height: Optional[int] = None) -> int:
        """Insert an image into the Google Doc.
        
        Args:
            document_id: The document ID.
            image_url: URL of the image to insert.
            index: Position to insert the image.
            alt_text: Alternative text for the image.
            width: Optional width in pixels.
            height: Optional height in pixels.
            
        Returns:
            New index after the image insertion.
        """
        try:
            # Prepare the image insertion request
            image_request = {
                'insertInlineImage': {
                    'location': {'index': index},
                    'uri': image_url
                }
            }
            
            # Add object size if dimensions are provided
            if width and height:
                # Convert pixels to points (1 pixel = 0.75 points)
                width_pts = width * 0.75
                height_pts = height * 0.75
                
                image_request['insertInlineImage']['objectSize'] = {
                    'height': {'magnitude': height_pts, 'unit': 'PT'},
                    'width': {'magnitude': width_pts, 'unit': 'PT'}
                }
            
            # Execute the request
            result = self.service.documents().batchUpdate(
                documentId=document_id,
                body={'requests': [image_request]}
            ).execute()
            
            # Return the index after the image (images take up 1 character position)
            return index + 1
            
        except Exception as e:
            print(f"Error inserting image: {str(e)}")
            # Return the original index if insertion fails
            return index

    def _extract_text_content(self, content: List[TextContent]) -> str:
        """Extract plain text from TextContent objects.
        
        Note: This method now only extracts text and ignores images.
        Use _extract_text_and_images for proper image handling.
        """
        text_parts = []
        for item in content:
            if isinstance(item, TextRun):
                text_parts.append(item.text)
            elif isinstance(item, ImageInfo):
                # For compatibility, still include a text placeholder
                text_parts.append(f"[Image: {item.src}]")
        return ''.join(text_parts)

    def get_document_url(self, document_id: str) -> str:
        """Get the URL to view/edit the Google Doc."""
        return f"https://docs.google.com/document/d/{document_id}/edit"


def convert_assessment_to_google_docs(
    assessment: Assessment,
    document_title: str,
    credentials_path: str = None,
    token_path: str = None,
    resource_zip: Optional[Union[str, zipfile.ZipFile]] = None,
    font_mapping: Optional[Dict[str, str]] = None,
    storage_folder: Optional[str] = None,
    is_answer_key: bool = False
) -> Tuple[str, str]:
    """Convert an Assessment object to a Google Doc.

    Args:
        assessment: The Assessment object to convert.
        document_title: The title for the Google Doc.
        credentials_path: Path to Google API credentials.json file.
        token_path: Path to store/load token.json file.
        resource_zip: An optional zipfile or path to a zipfile containing resources.
        font_mapping: An optional mapping from font names in the source to font names in Google Docs.
        storage_folder: Name of the Google Drive folder to store images.
        is_answer_key: Whether to include answer keys for multiple choice questions.
        
    Returns:
        Tuple of (document_id, document_url)
    """
    # Handle resource_zip parameter
    zip_to_close = None
    if isinstance(resource_zip, str):
        zip_to_close = zipfile.ZipFile(resource_zip, 'r')
        resource_zip = zip_to_close

    try:
        # Create converter and authenticate
        converter = GoogleDocsConverter(font_mapping, storage_folder)
        converter.authenticate(credentials_path, token_path)
        
        # Convert assessment
        document_id = converter.convert_assessment(assessment, document_title, resource_zip, is_answer_key)
        document_url = converter.get_document_url(document_id)
        
        return document_id, document_url
    finally:
        # Close the zipfile if we opened it
        if zip_to_close:
            zip_to_close.close()


def convert_cartridge_to_google_docs(
    cartridge_path: Union[str, Path],
    credentials_path: str = None,
    token_path: str = None,
    font_mapping: Optional[Dict[str, str]] = None,
    storage_folder: Optional[str] = None,
    limit: Optional[int] = None,
    is_answer_key: bool = False
) -> List[Tuple[str, str, str]]:
    """Extract assessments from a cartridge and convert them to Google Docs.

    Args:
        cartridge_path: Path to the cartridge file.
        credentials_path: Path to Google API credentials.json file.
        token_path: Path to store/load token.json file.
        font_mapping: An optional mapping from font names in the source to font names in Google Docs.
        storage_folder: Name of the Google Drive folder to store images.
        limit: Maximum number of assessments to process (default: all).
        is_answer_key: Whether to include answer keys for multiple choice questions.
        
    Returns:
        List of tuples containing (assessment_title, document_id, document_url) for each created document.
    """
    from .xml_parser import parse_cartridge

    # Normalize paths
    cartridge_path = Path(cartridge_path)

    # Parse the cartridge
    assessments = parse_cartridge(cartridge_path, font_mapping, limit)

    # Convert each assessment
    results = []
    with zipfile.ZipFile(cartridge_path, 'r') as zf:
        converter = GoogleDocsConverter(font_mapping, storage_folder)
        converter.authenticate(credentials_path, token_path)
        
        for assessment in assessments:
            document_id = converter.convert_assessment(assessment, assessment.title, zf, is_answer_key)
            document_url = converter.get_document_url(document_id)
            results.append((assessment.title, document_id, document_url))

    return results 