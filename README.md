# School Converter

This repository contains a minimal command line application for converting
1EdTech Common Cartridge (`.imscc`) files to various formats. Currently supported formats are:
- Microsoft Word document files (.docx)
- Google Docs (created directly via Google Docs API)
- Google Forms format (JSON files that can be imported to Google Forms)
- Direct Google Forms creation via API (with image support)

## Usage

```bash
# Default (DOCX) export
cc-convert sample1.imscc output_dir

# Google Docs export
cc-convert sample1.imscc --format google_docs --credentials path/to/credentials.json

# Google Forms JSON export
cc-convert sample1.imscc output_dir --format google_forms

# Direct Google Forms API export with images
cc-convert sample1.imscc --format google_forms_api --credentials path/to/credentials.json
```

## Command Line Options

```
--format      Choose the output format: docx (default), google_docs, google_forms, or google_forms_api
--font-map    Path to JSON file with font mapping for docx output
--credentials Path to Google API credentials JSON file (required for google_docs and google_forms_api)
--answer-key  Include answer keys for multiple choice questions (google_docs format only)
```

## Export Formats

### 1. DOCX Export (--format docx)

Creates Microsoft Word documents with:
- Proper formatting and styles
- Hanging indents for question numbering
- Separate sections for multiple choice and short answer questions
- Image support (when resource files are available)

### 2. Google Docs Export (--format google_docs)

Creates Google Docs directly via the Google Docs API with:
- Professional formatting with hanging indents
- Separate sections for multiple choice and short answer questions
- Multiple choice questions formatted as "_________ N." with A., B., C. options
- Short answer questions numbered 1., 2., 3.
- Optional answer key support
- Documents created directly in your Google Drive

#### Setting up for Google Docs

1. Create a Google Cloud Platform project
2. Enable the Google Docs API
3. Create OAuth 2.0 credentials (Desktop application)
4. Download the credentials JSON file
5. Use the `--credentials` option to specify the file path

Example with answer key:
```bash
cc-convert quiz.imscc --format google_docs --credentials credentials.json --answer-key
```

### 3. Google Forms JSON Export (--format google_forms)

The Google Forms JSON export creates files that represent the quiz structure in a format
compatible with Google Forms. These files include:
- Question text (with placeholders for images)
- Multiple choice options
- Correct answers (for automatic grading)

Note: Images are represented as placeholders in the export. You'll need to manually add images
when importing into Google Forms.

### 4. Direct Google Forms API Export (--format google_forms_api)

The direct API export option creates Google Forms directly through the Google Forms API:
- Creates fully functional Google Forms in your account
- Automatically uploads and includes images in questions
- Configures grading and correct answers
- Returns links to the created forms

#### Setting up Google API Credentials

To use the direct API export (google_forms_api or google_docs), you need to:

1. Create a Google Cloud Platform project
2. Enable the required APIs:
   - For Google Docs: Google Docs API
   - For Google Forms: Google Forms API and Google Drive API
3. Create OAuth 2.0 credentials (Desktop application)
4. Download the credentials JSON file
5. Provide the path to this file using the `--credentials` option

On first use, you'll be prompted to authorize the application through a browser window.

## Additional Resources

- For detailed Google Docs setup and usage: See `README_GOOGLE_DOCS.md`
- For API reference and advanced usage: Check the converter module documentation

## Development

Run tests with:

```bash
python -m unittest discover -s tests -v
```
