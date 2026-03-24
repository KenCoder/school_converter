import argparse
import sys
import zipfile
import shutil
from pathlib import Path
from typing import Dict, Optional, List, Any
import json

from cc_converter.xml_parser import parse_extracted_file, ParserError
from cc_converter.docx_converter import convert_assessment_to_docx
from cc_converter.hierarchy_converter import HierarchyConverter


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Convert and unpack 1EdTech Schoology files"
    )
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Convert command
    convert_parser = subparsers.add_parser('convert', help='Convert cartridge files to hierarchical structure with DOCX files')
    convert_parser.add_argument(
        "input", 
        type=str,
        help="Path to .imscc file or directory containing .imscc files"
    )
    convert_parser.add_argument(
        "output", 
        type=Path, 
        help="Output directory (defaults to same directory as input with cartridge name)", 
        nargs="?", 
        default=None
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
        help="Path to .imscc file(s) or directory containing .imscc files"
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


def process_single_file(input_path: Path, output_path: Path, font_mapping: Optional[Dict], limit: Optional[int], is_single_cartridge: bool = False, shared_loose_files_dir: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Process a single input file and convert it to hierarchical structure with DOCX files.
    
    Args:
        input_path: Path to the cartridge file
        output_path: Base output directory
        font_mapping: Optional font mapping
        limit: Maximum number of assessments to process
        is_single_cartridge: Whether this is a single cartridge conversion (output directly to output_path)
        shared_loose_files_dir: Optional shared loose files directory
    
    Returns:
        Dictionary containing hierarchy data if successful, None otherwise
    """
    if input_path.suffix.lower() == '.imscc':
        # Process cartridge file using enhanced converter
        try:
            # Determine the actual output directory for this cartridge
            if is_single_cartridge:
                # For single cartridge, convert directly into the output path
                cartridge_output = output_path
            else:
                # For multiple cartridges, create a subdirectory
                cartridge_output = output_path / input_path.stem
                cartridge_output.mkdir(parents=True, exist_ok=True)
            
            # Use the enhanced converter
            converter = HierarchyConverter(font_mapping, shared_loose_files_dir=shared_loose_files_dir)
            hierarchy_data = converter.convert_cartridge_with_hierarchy(input_path, cartridge_output, limit)
            print(f"Created hierarchical structure with DOCX files in {cartridge_output}")
            return {
                'cartridge_name': input_path.stem,
                'cartridge_path': str(cartridge_output.relative_to(output_path)) if not is_single_cartridge else '',
                'hierarchy': converter._hierarchy_node_to_dict(hierarchy_data) if hierarchy_data else None
            }
        except Exception as e:
            print(f"Error processing cartridge {input_path}: {str(e)}", file=sys.stderr)
            sys.exit(1)


def main(argv=None):
    args = parse_args(argv)
    
    if not args.command:
        print("Error: No command specified. Use 'convert' or 'unpack'.", file=sys.stderr)
        sys.exit(1)
    
    if args.command == 'convert':
        # Handle convert command
        input_path = Path(args.input)
        output_path = args.output
        font_mapping = None
        limit = args.limit

        # Load font mapping if provided
        if args.font_map:
            try:
                with open(args.font_map, 'r') as f:
                    font_mapping = json.load(f)
            except Exception as e:
                print(f"Error loading font mapping: {str(e)}", file=sys.stderr)
                sys.exit(1)

        # Determine input files
        input_files = []
        if input_path.is_dir():
            # If input is a directory, find all .imscc files
            input_files = list(input_path.glob("*.imscc"))
        elif input_path.is_file():
            # If input is a single file
            input_files = [input_path]
        else:
            print(f"Input path not found: {input_path}", file=sys.stderr)
            sys.exit(1)
        
        if not input_files:
            print(f"No .imscc files found in: {input_path}", file=sys.stderr)
            sys.exit(1)

        # Determine output directory
        # For single cartridge: default to cartridge_name folder next to the cartridge
        # For multiple cartridges: default to a "converted" folder in the input directory
        if output_path is None:
            if len(input_files) == 1:
                # Single cartridge: output to folder with cartridge name in same directory
                cartridge = input_files[0]
                output_path = cartridge.parent / cartridge.stem
            else:
                # Multiple cartridges: output to "converted" folder
                if input_path.is_dir():
                    output_path = input_path / "converted"
                else:
                    output_path = input_path.parent / "converted"
        
        # Create base output directory
        output_path.mkdir(parents=True, exist_ok=True)

        # Determine if this is a single cartridge conversion
        is_single_cartridge = len(input_files) == 1
        
        # Create shared loose files directory only for multiple cartridges
        shared_loose_files_dir = None
        if not is_single_cartridge:
            shared_loose_files_dir = output_path / "loose_files"
            shared_loose_files_dir.mkdir(exist_ok=True)

        # Process each input file
        for input_file in input_files:
            if not input_file.exists():
                print(f"Input file not found: {input_file}", file=sys.stderr)
                continue
            
            process_single_file(input_file, output_path, font_mapping, limit, is_single_cartridge, shared_loose_files_dir)
    
    elif args.command == 'unpack':
        # Handle unpack command
        input_path = Path(args.input)
        output_path = args.output
        
        # Determine input files
        input_files = []
        if input_path.is_dir():
            # If input is a directory, find all .imscc files
            input_files = list(input_path.glob("*.imscc"))
        elif input_path.is_file():
            # If input is a single file
            input_files = [input_path]
        else:
            print(f"Input path not found: {input_path}", file=sys.stderr)
            sys.exit(1)
        
        if not input_files:
            print(f"No .imscc files found in: {input_path}", file=sys.stderr)
            sys.exit(1)
        
        # Filter to only .imscc files
        imscc_files = [f for f in input_files if f.suffix.lower() == '.imscc']
        
        if not imscc_files:
            print(f"No .imscc files found in: {input_path}", file=sys.stderr)
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
