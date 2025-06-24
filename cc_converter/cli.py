import argparse
import sys
import zipfile
import shutil
import html
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
        help="Path to .imscc file(s) or extracted XML file(s), or directory containing .imscc files"
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


def process_single_file(input_path: Path, output_path: Path, font_mapping: Optional[Dict], limit: Optional[int], shared_loose_files_dir: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Process a single input file and convert it to hierarchical structure with DOCX files.
    
    Returns:
        Dictionary containing hierarchy data if successful, None otherwise
    """
    if input_path.suffix.lower() == '.imscc':
        # Process cartridge file using enhanced converter
        try:
            # Create a subdirectory for this cartridge
            cartridge_output = output_path / input_path.stem
            cartridge_output.mkdir(parents=True, exist_ok=True)
            
            # Use the enhanced converter
            converter = HierarchyConverter(font_mapping, shared_loose_files_dir=shared_loose_files_dir)
            hierarchy_data = converter.convert_cartridge_with_hierarchy(input_path, cartridge_output, limit)
            print(f"Created hierarchical structure with DOCX files in {cartridge_output}")
            return {
                'cartridge_name': input_path.stem,
                'cartridge_path': str(cartridge_output.relative_to(output_path)),
                'hierarchy': converter._hierarchy_node_to_dict(hierarchy_data) if hierarchy_data else None
            }
        except Exception as e:
            print(f"Error processing cartridge {input_path}: {str(e)}", file=sys.stderr)
            sys.exit(1)
    else:
        # Process single XML file (legacy support)
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
            convert_assessment_to_docx(assessment, output_file, input_xml_path=input_path, output_dir=output_path)
            rel_output_file = output_file.relative_to(output_path)
            print(f"Created {rel_output_file}")
            return None
                
        except ParserError as e:
            print(f"Error parsing file {input_path}: {str(e)}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Error converting file {input_path}: {str(e)}", file=sys.stderr)
            sys.exit(1)


def create_root_index_html(output_path: Path) -> None:
    """Create a root index.html file that links to all cartridge index.html files."""
    # Find all index.html files in subdirectories
    index_files = []
    for subdir in output_path.iterdir():
        if subdir.is_dir() and subdir.name != "loose_files":  # Exclude loose_files directory
            index_path = subdir / "index.html"
            if index_path.exists():
                index_files.append((subdir.name, index_path))
    
    if not index_files:
        print("No index.html files found in subdirectories")
        return
    
    # Sort by directory name for consistent ordering
    index_files.sort(key=lambda x: x[0])
    
    # Check if shared loose files directory exists and has files
    shared_loose_files_dir = output_path / "loose_files"
    has_loose_files = shared_loose_files_dir.exists() and any(shared_loose_files_dir.iterdir())
    
    # Generate HTML content
    html_content = [
        '<!DOCTYPE html>',
        '<html lang="en">',
        '<head>',
        '    <meta charset="UTF-8">',
        '    <meta name="viewport" content="width=device-width, initial-scale=1.0">',
        '    <title>Schoology Index</title>',
        '    <style>',
        '        body { font-family: Arial, sans-serif; margin: 40px; }',
        '        h1 { color: #333; border-bottom: 2px solid #eee; padding-bottom: 10px; }',
        '        .cartridge { margin: 15px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; background-color: #f9f9f9; }',
        '        .cartridge a { text-decoration: none; color: #0066cc; font-size: 16px; font-weight: bold; }',
        '        .cartridge a:hover { text-decoration: underline; }',
        '        .cartridge-name { color: #666; font-size: 14px; margin-top: 5px; }',
        '        .loose-files { margin: 15px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; background-color: #f0f8ff; }',
        '        .loose-files a { text-decoration: none; color: #0066cc; font-size: 16px; font-weight: bold; }',
        '        .loose-files a:hover { text-decoration: underline; }',
        '        .loose-files-name { color: #666; font-size: 14px; margin-top: 5px; }',
        '    </style>',
        '</head>',
        '<body>',
        '    <h1>Schoology Index</h1>',
        '    <p>Click on any cartridge below to view its contents:</p>',
        '    <div class="content">'
    ]
    
    for dir_name, index_path in index_files:
        relative_path = index_path.relative_to(output_path)
        html_content.append('        <div class="cartridge">')
        html_content.append(f'            <a href="{html.escape(str(relative_path))}">{html.escape(dir_name)}</a>')
        html_content.append(f'            <div class="cartridge-name">{html.escape(dir_name)}</div>')
        html_content.append('        </div>')
    
    # Add loose files section if it exists and has files
    if has_loose_files:
        html_content.append('        <div class="loose-files">')
        html_content.append('            <a href="loose_files/">Shared Loose Files</a>')
        html_content.append('            <div class="loose-files-name">All loose files from all cartridges in this session</div>')
        html_content.append('        </div>')
    
    html_content.extend([
        '    </div>',
        '</body>',
        '</html>'
    ])
    
    # Write the index.html file
    index_path = output_path / "index.html"
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(html_content))
    
    print(f"Created root index.html with {len(index_files)} cartridge links")
    if has_loose_files:
        print("Added link to shared loose files directory")


def create_combined_hierarchy_json(output_path: Path, all_hierarchies: List[Dict[str, Any]]) -> None:
    """Create a combined hierarchy.json file that includes all cartridges."""
    combined_hierarchy = {
        'type': 'combined_cartridges',
        'title': 'Schoology Collection',
        'cartridges': all_hierarchies,
        'loose_files_path': 'loose_files' if (output_path / 'loose_files').exists() else None
    }
    
    # Write to JSON file
    json_path = output_path / "hierarchy.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(combined_hierarchy, f, indent=2, ensure_ascii=False)
    
    print(f"Created combined hierarchy.json with {len(all_hierarchies)} cartridges")


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
            # If input is a directory, find all .imscc and .xml files
            input_files = list(input_path.glob("*.imscc")) + list(input_path.glob("*.xml"))
        elif input_path.is_file():
            # If input is a single file
            input_files = [input_path]
        else:
            print(f"Input path not found: {input_path}", file=sys.stderr)
            sys.exit(1)
        
        if not input_files:
            print(f"No .imscc or .xml files found in: {input_path}", file=sys.stderr)
            sys.exit(1)

        # Create base output directory
        output_path.mkdir(parents=True, exist_ok=True)

        # Create shared loose files directory for all cartridges in this session
        shared_loose_files_dir = output_path / "loose_files"
        shared_loose_files_dir.mkdir(exist_ok=True)

        # Collect all hierarchy data for combined hierarchy.json
        all_hierarchies = []
        imscc_files = [f for f in input_files if f.suffix.lower() == '.imscc']
        xml_files = [f for f in input_files if f.suffix.lower() == '.xml']

        # Process each input file
        for input_file in input_files:
            if not input_file.exists():
                print(f"Input file not found: {input_file}", file=sys.stderr)
                continue
            
            hierarchy_data = process_single_file(input_file, output_path, font_mapping, limit, shared_loose_files_dir)
            if hierarchy_data:
                all_hierarchies.append(hierarchy_data)
        
        # Create combined hierarchy.json if we have multiple cartridges
        if len(imscc_files) > 1 and all_hierarchies:
            create_combined_hierarchy_json(output_path, all_hierarchies)
        elif len(imscc_files) == 1 and all_hierarchies:
            # For single cartridge, create individual hierarchy.json
            cartridge_data = all_hierarchies[0]
            cartridge_output = output_path / cartridge_data['cartridge_name']
            if cartridge_data['hierarchy']:
                json_path = cartridge_output / "hierarchy.json"
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(cartridge_data['hierarchy'], f, indent=2, ensure_ascii=False)
                print(f"Created hierarchy.json for {cartridge_data['cartridge_name']}")
    
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
