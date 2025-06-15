import argparse
import sys
from pathlib import Path
from typing import Dict, Optional

from .xml_parser import parse_extracted_file, ParserError
from .docx_converter import convert_cartridge_to_docx, convert_assessment_to_docx
from .google_forms_converter import convert_cartridge_to_google_forms, convert_assessment_to_google_forms
from .google_forms_api import convert_cartridge_to_google_forms_api, convert_assessment_to_google_forms_api
from .google_docs_converter import convert_cartridge_to_google_docs, convert_assessment_to_google_docs


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Convert 1EdTech Common Cartridge files to doc files"
    )
    parser.add_argument("input", type=Path, help="Path to .imscc file or extracted XML file")
    parser.add_argument(
        "output", type=Path, help="Directory to write output document or output file", nargs="?", default=Path("out")
    )
    parser.add_argument(
        "--font-map", type=str, help="Path to JSON file with font mapping", default=None
    )
    parser.add_argument(
        "--format", type=str, 
        choices=["docx", "google_docs", "google_forms", "google_forms_api"], 
        default="docx",
        help="Output format: docx, google_docs (Google Docs API), google_forms (JSON file), or google_forms_api (direct API upload with images)"
    )
    parser.add_argument(
        "--credentials", type=str,
        help="Path to Google API credentials JSON file (required for google_docs and google_forms_api)",
        default=None
    )
    parser.add_argument(
        "--storage-folder", type=str,
        help="Folder to store created forms and image files (only for google_forms_api format)",
        default=None
    )
    parser.add_argument(
        "--answer-key", action="store_true",
        help="Include answer keys for multiple choice questions (google_docs format only)",
        default=False
    )
    parser.add_argument(
        "--limit", type=int,
        help="Maximum number of assessments to process (default: all)",
        default=None
    )
    return parser.parse_args(argv)


def load_font_mapping(font_map_path: Optional[str]) -> Dict[str, str]:
    """Load font mapping from a JSON file."""
    if not font_map_path:
        return {}
    
    import json
    try:
        with open(font_map_path, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"Error loading font mapping: {str(e)}")
        return {}


def main(argv=None):
    args = parse_args(argv)
    
    # Load font mapping if provided
    font_mapping = load_font_mapping(args.font_map)
    
    input_path = args.input
    output_path = args.output
    output_format = args.format
    credentials_file = args.credentials
    storage_folder = args.storage_folder
    answer_key = args.answer_key
    limit = args.limit
    
    # Check if credentials are provided for API exports
    if output_format in ["google_forms_api", "google_docs"] and not credentials_file:
        print(f"Error: --credentials is required when using --format={output_format}", file=sys.stderr)
        sys.exit(1)
    
    # Check if input is a file or directory
    if input_path.is_file():
        # Check if it's a cartridge file or extracted XML
        if input_path.suffix.lower() == '.imscc':
            # Process cartridge file
            try:
                if output_format == "docx":
                    num_files = convert_cartridge_to_docx(input_path, output_path, font_mapping, limit)
                    print(f"Created {num_files} docx files in {output_path}")
                elif output_format == "google_docs":
                    results = convert_cartridge_to_google_docs(
                        input_path, 
                        credentials_file,
                        font_mapping=font_mapping,
                        limit=limit,
                        is_answer_key=answer_key
                    )
                    print(f"Created {len(results)} Google Docs:")
                    for title, doc_id, doc_url in results:
                        print(f"  {title}: {doc_url}")
                elif output_format == "google_forms":
                    num_files = convert_cartridge_to_google_forms(input_path, output_path, limit)
                    print(f"Created {num_files} Google Forms JSON files in {output_path}")
                elif output_format == "google_forms_api":
                    form_urls = convert_cartridge_to_google_forms_api(
                        input_path, 
                        credentials_file,
                        storage_folder,
                        limit
                    )
                    print(f"Created {len(form_urls)} Google Forms:")
                    for url in form_urls:
                        print(f"  {url}")
            except Exception as e:
                print(f"Error processing cartridge: {str(e)}", file=sys.stderr)
                sys.exit(1)
        else:
            # Process single XML file
            try:
                # Parse the XML file
                assessment = parse_extracted_file(str(input_path), font_mapping)
                
                if output_format == "docx":
                    # If output is a directory, use the input filename
                    if output_path.suffix.lower() != '.docx':
                        output_path.mkdir(parents=True, exist_ok=True)
                        output_file = output_path / f"{input_path.stem}.docx"
                    else:
                        output_file = output_path
                    
                    # Convert to DOCX
                    convert_assessment_to_docx(assessment, output_file)
                    print(f"Created {output_file}")
                    
                elif output_format == "google_docs":
                    # Convert to Google Docs
                    document_id, document_url = convert_assessment_to_google_docs(
                        assessment, 
                        assessment.title,
                        credentials_file,
                        font_mapping=font_mapping,
                        is_answer_key=answer_key
                    )
                    print(f"Created Google Doc: {assessment.title}")
                    print(f"  URL: {document_url}")
                    
                elif output_format == "google_forms":
                    # If output is a directory, use the input filename
                    if output_path.suffix.lower() != '.json':
                        output_path.mkdir(parents=True, exist_ok=True)
                        output_file = output_path / f"{input_path.stem}.json"
                    else:
                        output_file = output_path
                    
                    # Convert to Google Forms format
                    convert_assessment_to_google_forms(assessment, output_file)
                    print(f"Created {output_file}")
                    
                elif output_format == "google_forms_api":
                    # Direct API upload
                    form_url = convert_assessment_to_google_forms_api(
                        assessment, 
                        None,  # No resource zip for single XML file
                        credentials_file,
                        storage_folder
                    )
                    print(f"Created Google Form: {form_url}")
                    
            except ParserError as e:
                print(f"Error parsing file: {str(e)}", file=sys.stderr)
                sys.exit(1)
            except Exception as e:
                print(f"Error converting file: {str(e)}", file=sys.stderr)
                sys.exit(1)
    else:
        print(f"Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":  # pragma: no cover
    main()
