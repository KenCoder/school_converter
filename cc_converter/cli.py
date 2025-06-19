import argparse
import sys
import glob
import zipfile
import shutil
from pathlib import Path
from typing import Dict, Optional, List

from cc_converter.xml_parser import parse_extracted_file, ParserError
from cc_converter.docx_converter import convert_cartridge_to_docx, convert_assessment_to_docx


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Convert and unpack 1EdTech Common Cartridge files"
    )
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Convert command
    convert_parser = subparsers.add_parser('convert', help='Convert cartridge files to docx')
    convert_parser.add_argument(
        "input", 
        type=str,
        help="Path to .imscc file(s) or extracted XML file(s). Can use wildcards (e.g., *.imscc)"
    )
    convert_parser.add_argument(
        "output", 
        type=Path, 
        help="Base directory to write output documents. Each input file will create its own subdirectory", 
        nargs="?", 
        default=Path("docs")
    )
    convert_parser.add_argument(
        "--font-map", type=str, help="Path to JSON file with font mapping", default=None
    )
    convert_parser.add_argument(
        "--limit", type=int, help="Maximum number of assessments to process", default=None
    )
    
    # Unpack command
    unpack_parser = subparsers.add_parser('unpack', help='Unpack cartridge files to directories')
    unpack_parser.add_argument(
        "input",
        type=str,
        help="Path to .imscc file(s). Can use wildcards (e.g., *.imscc)"
    )
    unpack_parser.add_argument(
        "output",
        type=Path,
        help="Base directory to write unpacked files. Each cartridge will create its own subdirectory",
        nargs="?",
        default=Path("unpacked")
    )

    return parser.parse_args(argv)


def unpack_cartridge(input_path: Path, output_path: Path) -> None:
    """Unpack a single cartridge file to a directory."""
    try:
        # Create output directory named after the cartridge
        cartridge_output = output_path / input_path.stem
        cartridge_output.mkdir(parents=True, exist_ok=True)
        
        # Extract all files from the cartridge
        with zipfile.ZipFile(input_path, 'r') as zf:
            zf.extractall(cartridge_output)
        
        print(f"Unpacked {input_path} to {cartridge_output}")
    except Exception as e:
        print(f"Error unpacking cartridge {input_path}: {str(e)}", file=sys.stderr)
        sys.exit(1)


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
    
    if not args.command:
        print("Error: No command specified. Use 'convert' or 'unpack'.", file=sys.stderr)
        sys.exit(1)
    
    if args.command == 'convert':
        # Handle convert command
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
    
    elif args.command == 'unpack':
        # Handle unpack command
        input_pattern = args.input
        output_path = args.output
        
        # Expand wildcards and get list of input files
        input_files = [Path(f) for f in glob.glob(input_pattern)]
        
        if not input_files:
            print(f"No files found matching pattern: {input_pattern}", file=sys.stderr)
            sys.exit(1)
        
        # Filter to only .imscc files
        imscc_files = [f for f in input_files if f.suffix.lower() == '.imscc']
        
        if not imscc_files:
            print(f"No .imscc files found matching pattern: {input_pattern}", file=sys.stderr)
            sys.exit(1)
        
        # Create base output directory
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Unpack each cartridge file
        for input_file in imscc_files:
            if not input_file.exists():
                print(f"Input file not found: {input_file}", file=sys.stderr)
                continue
            unpack_cartridge(input_file, output_path)


if __name__ == '__main__':
    main()
