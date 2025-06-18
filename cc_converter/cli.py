import argparse
import sys
import glob
from pathlib import Path
from typing import Dict, Optional, List

from cc_converter.xml_parser import parse_extracted_file, ParserError
from cc_converter.docx_converter import convert_cartridge_to_docx, convert_assessment_to_docx


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Convert 1EdTech Common Cartridge files to docx files"
    )
    parser.add_argument(
        "input", 
        type=str,  # Changed from Path to str to handle wildcards
        help="Path to .imscc file(s) or extracted XML file(s). Can use wildcards (e.g., *.imscc)"
    )
    parser.add_argument(
        "output", 
        type=Path, 
        help="Base directory to write output documents. Each input file will create its own subdirectory", 
        nargs="?", 
        default=Path("docs")
    )
    parser.add_argument(
        "--font-map", type=str, help="Path to JSON file with font mapping", default=None
    )
    parser.add_argument(
        "--limit", type=int, help="Maximum number of assessments to process", default=None
    )

    return parser.parse_args(argv)


def process_single_file(input_path: Path, output_path: Path, font_mapping: Optional[Dict], limit: Optional[int]) -> None:
    """Process a single input file and convert it to docx."""
    if input_path.suffix.lower() == '.imscc':
        # Process cartridge file
        try:
            # Create a subdirectory for this cartridge
            cartridge_output = output_path / input_path.stem
            cartridge_output.mkdir(parents=True, exist_ok=True)
            
            num_files = convert_cartridge_to_docx(input_path, cartridge_output, font_mapping, limit)
            print(f"Created {num_files} docx files in {cartridge_output}")
        except Exception as e:
            print(f"Error processing cartridge {input_path}: {str(e)}", file=sys.stderr)
            sys.exit(1)
    else:
        # Process single XML file
        try:
            # Parse the XML file
            assessment = parse_extracted_file(str(input_path), font_mapping)
            
            # If output is a directory, use the input filename
            if output_path.suffix.lower() != '.docx':
                output_path.mkdir(parents=True, exist_ok=True)
                output_file = output_path / f"{input_path.stem}.docx"
            else:
                output_file = output_path
            
            # Convert to DOCX
            convert_assessment_to_docx(assessment, output_file)
            print(f"Created {output_file}")
                
        except ParserError as e:
            print(f"Error parsing file {input_path}: {str(e)}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Error converting file {input_path}: {str(e)}", file=sys.stderr)
            sys.exit(1)


def main(argv=None):
    args = parse_args(argv)
    input_pattern = args.input
    output_path = args.output
    font_mapping = None
    limit = args.limit

    # Load font mapping if provided
    if args.font_map:
        try:
            import json
            with open(args.font_map, 'r') as f:
                font_mapping = json.load(f)
        except Exception as e:
            print(f"Error loading font mapping: {str(e)}", file=sys.stderr)
            sys.exit(1)

    # Expand wildcards and get list of input files
    input_files = [Path(f) for f in glob.glob(input_pattern)]
    
    if not input_files:
        print(f"No files found matching pattern: {input_pattern}", file=sys.stderr)
        sys.exit(1)

    # Create base output directory
    output_path.mkdir(parents=True, exist_ok=True)

    # Process each input file
    for input_file in input_files:
        if not input_file.exists():
            print(f"Input file not found: {input_file}", file=sys.stderr)
            continue
        process_single_file(input_file, output_path, font_mapping, limit)


if __name__ == '__main__':
    main()
