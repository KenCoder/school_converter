import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any
import shutil
import zipfile
from dataclasses import dataclass
import html

from cc_converter.docx_converter import convert_assessment_to_docx
from cc_converter.xml_parser import parse_cartridge, ParserError


@dataclass
class OrganizationItem:
    """Represents an item in the organization hierarchy."""
    identifier: str
    title: str
    identifierref: Optional[str] = None
    children: List['OrganizationItem'] = None
    
    def __post_init__(self):
        if self.children is None:
            self.children = []


@dataclass
class Resource:
    """Represents a resource in the manifest."""
    identifier: str
    type: str
    href: str
    files: List[str] = None
    
    def __post_init__(self):
        if self.files is None:
            self.files = []


class EnhancedConverter:
    """Enhanced converter that creates hierarchical structure with HTML navigation and DOCX files."""
    
    def __init__(self, font_mapping: Optional[Dict[str, str]] = None):
        self.font_mapping = font_mapping or {}
        self.referenced_resources: Set[str] = set()
        self.resources: Dict[str, Resource] = {}
        self.assessments: Dict[str, Any] = {}  # Store parsed assessments by resource ID
        
    def convert_cartridge(self, cartridge_path: Path, output_dir: Path, limit: Optional[int] = None) -> None:
        """Convert a cartridge file to hierarchical structure with DOCX files.
        
        Args:
            cartridge_path: Path to the cartridge file
            output_dir: Path where the output should be created
            limit: Maximum number of assessments to process
        """
        # Create output directory
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Parse the cartridge to get assessments and loose files
        assessments, loose_files = parse_cartridge(str(cartridge_path), self.font_mapping, limit)
        
        # Store assessments by their file path for later use
        with zipfile.ZipFile(cartridge_path, 'r') as zf:
            # Parse the manifest to get organization and resources
            self._parse_manifest_from_zip(zf)
            
            # Extract the organization hierarchy
            organization = self._extract_organization_from_zip(zf)
            
            # Create a mapping of assessments by their XML file path
            self._create_assessment_mapping(zf, assessments)
            
            # Create the directory structure
            self._create_directory_structure(organization, output_dir, zf, assessments)
            
            # Copy unreferenced resources to loose files directory
            self._copy_loose_files(output_dir, zf, loose_files)
    
    def _parse_manifest_from_zip(self, zf: zipfile.ZipFile) -> None:
        """Parse the imsmanifest.xml file from the zip to extract organization and resources."""
        with zf.open("imsmanifest.xml") as manifest_file:
            tree = ET.parse(manifest_file)
        
        root = tree.getroot()
        
        # Define namespaces
        namespaces = {
            'imscp': 'http://www.imsglobal.org/xsd/imsccv1p2/imscp_v1p1',
            'lom': 'http://ltsc.ieee.org/xsd/imsccv1p2/LOM/resource',
            'lomimscc': 'http://ltsc.ieee.org/xsd/imsccv1p2/LOM/manifest'
        }
        
        # Parse resources
        resources_elem = root.find('.//imscp:resources', namespaces)
        if resources_elem is not None:
            for resource_elem in resources_elem.findall('.//imscp:resource', namespaces):
                identifier = resource_elem.get('identifier')
                resource_type = resource_elem.get('type', '')
                href = resource_elem.get('href', '')
                
                files = []
                for file_elem in resource_elem.findall('.//imscp:file', namespaces):
                    file_href = file_elem.get('href')
                    if file_href:
                        files.append(file_href)
                
                self.resources[identifier] = Resource(
                    identifier=identifier,
                    type=resource_type,
                    href=href,
                    files=files
                )
        
        # Parse organization to track referenced resources
        organizations_elem = root.find('.//imscp:organizations', namespaces)
        if organizations_elem is not None:
            for item_elem in organizations_elem.findall('.//imscp:item', namespaces):
                identifierref = item_elem.get('identifierref')
                if identifierref:
                    self.referenced_resources.add(identifierref)
    
    def _extract_organization_from_zip(self, zf: zipfile.ZipFile) -> OrganizationItem:
        """Extract the organization hierarchy from the manifest in the zip."""
        with zf.open("imsmanifest.xml") as manifest_file:
            tree = ET.parse(manifest_file)
        
        root = tree.getroot()
        
        # Define namespaces
        namespaces = {
            'imscp': 'http://www.imsglobal.org/xsd/imsccv1p2/imscp_v1p1',
            'lom': 'http://ltsc.ieee.org/xsd/imsccv1p2/LOM/resource',
            'lomimscc': 'http://ltsc.ieee.org/xsd/imsccv1p2/LOM/manifest'
        }
        
        # Get course title from metadata
        course_title = self._get_course_title(root, namespaces)
        
        # Find the organization
        organization_elem = root.find('.//imscp:organization', namespaces)
        if organization_elem is None:
            # Fallback to no namespace
            organization_elem = root.find('.//organization')
        
        if organization_elem is None:
            # Create a simple structure if no organization found
            return OrganizationItem(
                identifier="root",
                title=course_title,
                children=[]
            )
        
        # Find the root item
        root_item_elem = organization_elem.find('.//imscp:item', namespaces)
        if root_item_elem is None:
            # Fallback to no namespace
            root_item_elem = organization_elem.find('.//item')
        
        if root_item_elem is None:
            return OrganizationItem(
                identifier="root",
                title=course_title,
                children=[]
            )
        
        # Parse the root item and its children
        root_item = self._parse_item_element(root_item_elem, namespaces)
        # Override the title with the course title
        root_item.title = course_title
        return root_item
    
    def _get_course_title(self, root: ET.Element, namespaces: Dict[str, str]) -> str:
        """Extract the course title from metadata."""
        # Try to get title from LOM metadata
        title_elem = root.find('.//lomimscc:title/lomimscc:string', namespaces)
        if title_elem is not None and title_elem.text:
            return title_elem.text.strip()
        
        # Fallback to no namespace
        title_elem = root.find('.//title/string')
        if title_elem is not None and title_elem.text:
            return title_elem.text.strip()
        
        return "Course Content"
    
    def _parse_item_element(self, item_elem: ET.Element, namespaces: Dict[str, str]) -> OrganizationItem:
        """Parse an item element and its children recursively."""
        identifier = item_elem.get('identifier', '')
        identifierref = item_elem.get('identifierref')
        
        # Get the title
        title_elem = item_elem.find('.//imscp:title', namespaces)
        if title_elem is None:
            # Fallback to no namespace
            title_elem = item_elem.find('.//title')
        
        title = title_elem.text if title_elem is not None and title_elem.text else "Untitled"
        
        # Create the item
        item = OrganizationItem(
            identifier=identifier,
            title=title,
            identifierref=identifierref
        )
        
        # Parse direct children only
        for child_elem in item_elem:
            if child_elem.tag.endswith('item') or child_elem.tag == 'item':
                child_item = self._parse_item_element(child_elem, namespaces)
                item.children.append(child_item)
        
        return item
    
    def _create_directory_structure(self, organization: OrganizationItem, output_dir: Path, 
                                  zf: zipfile.ZipFile, assessments: List[Any]) -> None:
        """Create the directory structure based on the organization."""
        # Create index.html for the main directory
        self._create_index_html(output_dir, organization, zf, assessments)
        
        # Process children recursively
        for child in organization.children:
            self._process_organization_item(child, output_dir, zf, assessments)
    
    def _process_organization_item(self, item: OrganizationItem, parent_dir: Path, 
                                 zf: zipfile.ZipFile, assessments: List[Any]) -> None:
        """Process a single organization item."""
        if item.identifierref:
            # This item references a resource
            self._process_resource_item(item, parent_dir, zf, assessments)
        else:
            # This item is a container (folder)
            self._process_container_item(item, parent_dir, zf, assessments)
    
    def _process_resource_item(self, item: OrganizationItem, parent_dir: Path, 
                             zf: zipfile.ZipFile, assessments: List[Any]) -> None:
        """Process an item that references a resource."""
        resource = self.resources.get(item.identifierref)
        if not resource:
            print(f"Warning: Resource {item.identifierref} not found")
            return
        
        # Create a files subdirectory if it doesn't exist
        files_dir = parent_dir / "files"
        files_dir.mkdir(exist_ok=True)
        
        # Copy the resource files and convert XML to DOCX
        for file_path in resource.files:
            try:
                with zf.open(file_path) as source_file:
                    # Use just the filename, not the full path
                    dest_path = files_dir / Path(file_path).name
                    
                    # Write the file
                    with open(dest_path, 'wb') as dest_file:
                        dest_file.write(source_file.read())
                    
                    # If it's an XML file, also convert to DOCX
                    if file_path.lower().endswith('.xml'):
                        try:
                            # Find the assessment that corresponds to this file
                            assessment = self.assessments_by_file.get(file_path)
                            
                            if assessment:
                                # Create regular DOCX
                                docx_path = dest_path.with_suffix('.docx')
                                convert_assessment_to_docx(assessment, docx_path, zf, self.font_mapping, is_answer_key=False)
                                
                                # Create answer key DOCX - use a different approach for the filename
                                key_filename = dest_path.stem + '_key.docx'
                                key_path = dest_path.parent / key_filename
                                convert_assessment_to_docx(assessment, key_path, zf, self.font_mapping, is_answer_key=True)
                                
                                print(f"Created {docx_path} and {key_path}")
                        except Exception as e:
                            print(f"Warning: Could not convert XML file {file_path}: {e}")
            except Exception as e:
                print(f"Warning: Could not process file {file_path}: {e}")
    
    def _process_container_item(self, item: OrganizationItem, parent_dir: Path, 
                              zf: zipfile.ZipFile, assessments: List[Any]) -> None:
        """Process an item that is a container (folder)."""
        # Create the directory
        item_dir = parent_dir / self._sanitize_filename(item.title)
        item_dir.mkdir(exist_ok=True)
        
        # Create index.html for this directory
        self._create_index_html(item_dir, item, zf, assessments)
        
        # Process children
        for child in item.children:
            self._process_organization_item(child, item_dir, zf, assessments)
    
    def _create_index_html(self, directory: Path, item: OrganizationItem, 
                          zf: zipfile.ZipFile, assessments: List[Any]) -> None:
        """Create an index.html file for a directory."""
        html_content = self._generate_index_html(item, directory, zf, assessments)
        
        index_path = directory / "index.html"
        with open(index_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
    
    def _generate_index_html(self, item: OrganizationItem, directory: Path, 
                           zf: zipfile.ZipFile, assessments: List[Any]) -> str:
        """Generate HTML content for the index file."""
        html_parts = [
            '<!DOCTYPE html>',
            '<html lang="en">',
            '<head>',
            '    <meta charset="UTF-8">',
            '    <meta name="viewport" content="width=device-width, initial-scale=1.0">',
            f'    <title>{html.escape(item.title)}</title>',
            '    <style>',
            '        body { font-family: Arial, sans-serif; margin: 40px; }',
            '        h1 { color: #333; border-bottom: 2px solid #eee; padding-bottom: 10px; }',
            '        .item { margin: 10px 0; padding: 10px; border: 1px solid #ddd; border-radius: 5px; }',
            '        .item a { text-decoration: none; color: #0066cc; }',
            '        .item a:hover { text-decoration: underline; }',
            '        .folder { background-color: #f9f9f9; }',
            '        .file { background-color: #fff; }',
            '        .files-section { margin-top: 20px; }',
            '        .files-section h3 { color: #666; }',
            '        .docx-links { margin-left: 20px; font-size: 0.9em; }',
            '        .docx-links a { color: #666; }',
            '    </style>',
            '</head>',
            '<body>',
            f'    <h1>{html.escape(item.title)}</h1>'
        ]
        
        # Add children
        if item.children:
            html_parts.append('    <div class="content">')
            for child in item.children:
                if child.identifierref:
                    # It's a file
                    resource = self.resources.get(child.identifierref)
                    if resource and resource.files:
                        # Use the first file as the main file
                        main_file = Path(resource.files[0]).name
                        display_title = child.title
                        
                        # Check if this is a Schoology message (HTML file)
                        if main_file.lower().endswith('.html'):
                            display_title += " (Schoology Message)"
                        
                        html_parts.append('        <div class="item file">')
                        
                        # For XML files, make the primary link the DOCX file
                        if main_file.lower().endswith('.xml'):
                            html_parts.append(f'            <a href="files/{html.escape(main_file.replace(".xml", ".docx"))}">{html.escape(display_title)}</a>')
                            html_parts.append('            <div class="docx-links">')
                            html_parts.append(f'                <a href="files/{html.escape(main_file.replace(".xml", "_key.docx"))}">Answer Key</a>')
                            html_parts.append('            </div>')
                        else:
                            # For non-XML files, link to the original file
                            html_parts.append(f'            <a href="files/{html.escape(main_file)}">{html.escape(display_title)}</a>')
                        
                        html_parts.append('        </div>')
                    else:
                        # No files found, show as broken link
                        html_parts.append('        <div class="item file">')
                        html_parts.append(f'            <span style="color: #999;">{html.escape(child.title)} (file not found)</span>')
                        html_parts.append('        </div>')
                else:
                    # It's a folder
                    child_dir = directory / self._sanitize_filename(child.title)
                    html_parts.append('        <div class="item folder">')
                    html_parts.append(f'            <a href="{html.escape(self._sanitize_filename(child.title))}/index.html">{html.escape(child.title)}</a>')
                    html_parts.append('        </div>')
            html_parts.append('    </div>')
        
        # Add files section if this item has a resource
        if item.identifierref:
            resource = self.resources.get(item.identifierref)
            if resource and resource.files:
                html_parts.append('    <div class="files-section">')
                html_parts.append('        <h3>Files:</h3>')
                for file_path in resource.files:
                    file_name = Path(file_path).name
                    display_name = file_name
                    
                    # Check if this is a Schoology message (HTML file)
                    if file_name.lower().endswith('.html'):
                        display_name += " (Schoology Message)"
                    
                    html_parts.append('        <div class="item file">')
                    
                    # For XML files, make the primary link the DOCX file
                    if file_name.lower().endswith('.xml'):
                        html_parts.append(f'            <a href="files/{html.escape(file_name.replace(".xml", ".docx"))}">{html.escape(display_name)}</a>')
                        html_parts.append('            <div class="docx-links">')
                        html_parts.append(f'                <a href="files/{html.escape(file_name.replace(".xml", "_key.docx"))}">Answer Key</a>')
                        html_parts.append('            </div>')
                    else:
                        # For non-XML files, link to the original file
                        html_parts.append(f'            <a href="files/{html.escape(file_name)}">{html.escape(display_name)}</a>')
                    
                    html_parts.append('        </div>')
                html_parts.append('    </div>')
        
        html_parts.extend([
            '</body>',
            '</html>'
        ])
        
        return '\n'.join(html_parts)
    
    def _copy_loose_files(self, output_dir: Path, zf: zipfile.ZipFile, loose_files: List[str]) -> None:
        """Copy unreferenced resources to a loose files directory."""
        loose_dir = output_dir / "loose_files"
        loose_dir.mkdir(exist_ok=True)
        
        # Copy files that are not referenced by any resource
        for file_path in loose_files:
            try:
                with zf.open(file_path) as source_file:
                    dest_path = loose_dir / Path(file_path).name
                    with open(dest_path, 'wb') as dest_file:
                        dest_file.write(source_file.read())
            except Exception as e:
                print(f"Warning: Could not copy loose file {file_path}: {e}")
        
        # Also copy resources that are not referenced in the organization
        for identifier, resource in self.resources.items():
            if identifier not in self.referenced_resources:
                # This is a loose resource
                for file_path in resource.files:
                    try:
                        with zf.open(file_path) as source_file:
                            dest_path = loose_dir / Path(file_path).name
                            with open(dest_path, 'wb') as dest_file:
                                dest_file.write(source_file.read())
                    except Exception as e:
                        print(f"Warning: Could not copy unreferenced file {file_path}: {e}")
    
    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize a filename for use as a directory name."""
        # Remove or replace invalid characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        
        # Remove leading/trailing spaces and dots
        filename = filename.strip(' .')
        
        # Ensure it's not empty
        if not filename:
            filename = "untitled"
        
        return filename
    
    def _create_assessment_mapping(self, zf: zipfile.ZipFile, assessments: List[Any]) -> None:
        """Create a mapping of assessments by their XML file path."""
        self.assessments_by_file = {}
        
        # Get all XML files from the zip
        xml_files = [f for f in zf.namelist() if f.lower().endswith('.xml')]
        
        # For each assessment, try to find which XML file it came from
        for assessment in assessments:
            # Try to match by parsing each XML file and comparing titles
            for xml_file in xml_files:
                try:
                    with zf.open(xml_file) as f:
                        xml_content = f.read().decode('utf-8')
                    
                    # Quick check: if the XML contains the assessment title, it's likely a match
                    if assessment.title in xml_content:
                        self.assessments_by_file[xml_file] = assessment
                        break
                except Exception:
                    continue 