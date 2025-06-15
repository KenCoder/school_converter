# Google Docs Converter

This converter creates Google Docs from assessment data using the Google Docs API. It provides the same functionality as the DOCX converter but creates documents directly in Google Drive with proper formatting, hanging indents, and autonumbering.

## Features

- **Separate sections**: Multiple choice and short answer questions are organized in separate sections
- **Proper numbering**: Each section starts numbering at 1
- **Hanging indents**: All question numbers have proper hanging indents
- **Multiple choice format**: Questions formatted as "_________ N." with lettered answer options (A., B., C., etc.)
- **Short answer format**: Questions formatted as "1., 2., 3.."
- **Answer key support**: Optional answer keys for multiple choice questions
- **Batch processing**: Convert entire cartridges with multiple assessments

## Setup

### 1. Install Required Packages

```bash
pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client
```

### 2. Set Up Google Cloud Project

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Google Docs API:
   - Go to "APIs & Services" > "Library"
   - Search for "Google Docs API"
   - Click on it and press "Enable"

### 3. Create Credentials

1. Go to "APIs & Services" > "Credentials"
2. Click "Create Credentials" > "OAuth 2.0 Client IDs"
3. If prompted, configure the OAuth consent screen first:
   - Choose "External" user type
   - Fill in the required fields (app name, user support email, developer contact)
   - Add your email to test users
4. For the OAuth 2.0 Client ID:
   - Choose "Desktop application"
   - Give it a name (e.g., "School Converter")
   - Click "Create"
5. Download the credentials JSON file and save it as `credentials.json` in your project directory

### 4. First-Time Authentication

When you run the converter for the first time, it will:
1. Open a web browser for Google OAuth authentication
2. Ask you to sign in with your Google account
3. Request permission to create Google Docs
4. Save an authentication token for future use

## Usage

### Basic Usage

```python
from cc_converter.google_docs_converter import convert_assessment_to_google_docs
from cc_converter.xml_parser import parse_cartridge

# Parse a cartridge and convert the first assessment
assessments = parse_cartridge('path/to/cartridge.zip', limit=1)
assessment = assessments[0]

# Convert to Google Docs
document_id, document_url = convert_assessment_to_google_docs(
    assessment=assessment,
    document_title="My Assessment",
    credentials_path="credentials.json"
)

print(f"Created Google Doc: {document_url}")
```

### Convert Entire Cartridge

```python
from cc_converter.google_docs_converter import convert_cartridge_to_google_docs

# Convert all assessments in a cartridge
results = convert_cartridge_to_google_docs(
    cartridge_path="path/to/cartridge.zip",
    credentials_path="credentials.json"
)

for title, doc_id, doc_url in results:
    print(f"Created: {title} - {doc_url}")
```

### Command Line Usage

Use the provided example script:

```bash
# Convert all assessments
python example_google_docs.py path/to/cartridge.zip

# Convert just the first assessment (for testing)
python example_google_docs.py path/to/cartridge.zip --single

# Include answer keys
python example_google_docs.py path/to/cartridge.zip --answer-key

# Limit number of assessments
python example_google_docs.py path/to/cartridge.zip --limit 5
```

## Document Format

The converter creates Google Docs with the following structure:

### Multiple Choice Questions
```
Multiple Choice Questions

_________ 1.    What is the capital of France?
               A. London
               B. Paris
               C. Berlin
               D. Madrid

_________ 2.    Which planet is closest to the sun?
               A. Venus
               B. Mercury
               C. Earth
               D. Mars
```

### Short Answer Questions
```
Short Answer Questions

1. Explain the process of photosynthesis.

2. Describe the causes of World War I.

3. What are the main components of a computer?
```

### With Answer Key
When `is_answer_key=True`, multiple choice questions show the correct answer:

```
[ B ] 1.    What is the capital of France?
            A. London
            B. Paris
            C. Berlin
            D. Madrid
```

## API Reference

### `GoogleDocsConverter`

Main converter class that handles authentication and document creation.

#### `authenticate(credentials_path, token_path)`
Authenticate with Google Docs API.

#### `convert_assessment(assessment, document_title, resource_zip, is_answer_key)`
Convert a single assessment to a Google Doc.

### Helper Functions

#### `convert_assessment_to_google_docs(assessment, document_title, **kwargs)`
Convert a single assessment to Google Docs.

#### `convert_cartridge_to_google_docs(cartridge_path, **kwargs)`
Convert all assessments in a cartridge to Google Docs.

## Formatting Details

- **Hanging indents**: Questions use proper hanging indents (0.75" for MC, 0.25" for SA)
- **Section headers**: Formatted as Heading 2 style
- **Document title**: Formatted as Heading 1 style
- **Autonumbering**: Each section restarts numbering at 1
- **Spacing**: Proper spacing between questions and sections

## Limitations

- Images are currently shown as placeholder text (enhancement needed)
- Complex text formatting (fonts, colors) is simplified to plain text
- Requires internet connection for Google API access
- Rate limits may apply for bulk conversions

## Troubleshooting

### Authentication Issues
- Make sure `credentials.json` is in the correct location
- Delete `token.json` to force re-authentication
- Check that Google Docs API is enabled in your project

### Permission Errors
- Ensure your Google account has permission to create documents
- Check OAuth consent screen configuration

### Rate Limiting
- Google APIs have usage limits
- For bulk conversions, consider adding delays between requests

## Security Notes

- Keep your `credentials.json` file secure and don't commit it to version control
- The `token.json` file contains access tokens - treat it as sensitive
- Consider using service account credentials for production deployments 