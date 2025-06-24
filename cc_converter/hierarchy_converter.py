import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any
import shutil
import zipfile
from dataclasses import dataclass, asdict
import html
import json
from datetime import datetime

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


@dataclass
class HierarchyNode:
    """Represents a node in the hierarchy JSON structure."""
    id: str
    title: str
    type: str  # 'folder' or 'file'
    path: str
    children: List['HierarchyNode'] = None
    files: List[Dict[str, str]] = None  # List of file info dicts
    
    def __post_init__(self):
        if self.children is None:
            self.children = []
        if self.files is None:
            self.files = []


class HierarchyConverter:
    """Enhanced converter that creates hierarchical structure with DOCX files."""
    
    def __init__(self, font_mapping: Optional[Dict[str, str]] = None, template_path: Optional[Path] = None, shared_loose_files_dir: Optional[Path] = None):
        """Initialize the converter.
        
        Args:
            font_mapping: Optional mapping from font names in source to font names in docx
            template_path: Optional path to template docx file
            shared_loose_files_dir: Optional path to shared loose files directory for session-wide loose files
        """
        self.font_mapping = font_mapping or {}
        self.template_path = template_path
        self.shared_loose_files_dir = shared_loose_files_dir
        self.resources = {}
        self.referenced_resources = set()
        self.processed_resources = set()
        self.assessments_by_file = {}
        self.progress_callback = None
        self.output_dir = None  # Store the output directory for relative path logging
        self.total_xml_size = 0  # Total size of XML files to convert
        self.processed_xml_size = 0  # Size of XML files already processed
        
        # Error tracking
        self.errors = []
        self.warnings = []
        self.files_with_errors = set()
        self.files_with_warnings = set()
        self.hierarchy_creation_error = None
        
    def set_progress_callback(self, callback):
        """Set a callback function for progress updates."""
        self.progress_callback = callback
        
    def _report_progress(self, message: str, progress: float = None):
        """Report progress if callback is set."""
        if self.progress_callback:
            self.progress_callback(message, progress)
        
    def _add_error(self, error_type: str, message: str, file_path: str = None):
        """Add an error to the tracking system."""
        error_info = {
            'type': error_type,
            'message': message,
            'file_path': file_path,
            'timestamp': datetime.now().isoformat()
        }
        self.errors.append(error_info)
        if file_path:
            self.files_with_errors.add(file_path)
        print(f"ERROR: {message}")
    
    def _add_warning(self, warning_type: str, message: str, file_path: str = None):
        """Add a warning to the tracking system."""
        warning_info = {
            'type': warning_type,
            'message': message,
            'file_path': file_path,
            'timestamp': datetime.now().isoformat()
        }
        self.warnings.append(warning_info)
        if file_path:
            self.files_with_warnings.add(file_path)
        print(f"Warning: {message}")
    
    def get_conversion_summary(self) -> Dict[str, Any]:
        """Get a summary of the conversion results including errors and warnings."""
        return {
            'total_errors': len(self.errors),
            'total_warnings': len(self.warnings),
            'files_with_errors': len(self.files_with_errors),
            'files_with_warnings': len(self.files_with_warnings),
            'errors': self.errors,
            'warnings': self.warnings,
            'hierarchy_creation_error': self.hierarchy_creation_error,
            'success': len(self.errors) == 0 and self.hierarchy_creation_error is None
        }
    
    def convert_cartridge(self, cartridge_path: Path, output_dir: Path, limit: Optional[int] = None) -> None:
        """Convert a cartridge file to hierarchical structure with DOCX files.
        
        Args:
            cartridge_path: Path to the cartridge file
            output_dir: Path where the output should be created
            limit: Maximum number of assessments to process
        """
        # Use the new method and create the hierarchy.json file
        hierarchy = self.convert_cartridge_with_hierarchy(cartridge_path, output_dir, limit)
        if hierarchy:
            self._create_hierarchy_json(output_dir, hierarchy)
        
        # Get conversion summary
        summary = self.get_conversion_summary()
        
        if summary['success']:
            if summary['total_warnings'] > 0:
                self._report_progress(f"Conversion completed with {summary['total_warnings']} warnings!", 100)
            else:
                self._report_progress("Conversion completed successfully!", 100)
        else:
            error_count = summary['total_errors']
            warning_count = summary['total_warnings']
            files_with_errors = summary['files_with_errors']
            
            if error_count > 0:
                self._report_progress(f"Conversion completed with {error_count} errors affecting {files_with_errors} files", -1)
            else:
                self._report_progress(f"Conversion completed with {warning_count} warnings", 100)
    
    def convert_cartridge_with_hierarchy(self, cartridge_path: Path, output_dir: Path, limit: Optional[int] = None) -> Optional[HierarchyNode]:
        """Convert a cartridge file to hierarchical structure with DOCX files and return the hierarchy data.
        
        Args:
            cartridge_path: Path to the cartridge file
            output_dir: Path where the output should be created
            limit: Maximum number of assessments to process
            
        Returns:
            HierarchyNode object representing the hierarchy, or None if conversion failed
        """
        # Store the output directory for relative path logging
        self.output_dir = output_dir
        
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
            
            # Calculate total XML file sizes for progress tracking
            self._calculate_total_xml_size(zf)
            
            # Report initial progress if there are XML files to convert
            if self.total_xml_size > 0:
                self._report_progress(f"Starting DOCX conversion of {len(self.assessments_by_file)} XML files...", 0)
            
            # Create the directory structure and hierarchy
            hierarchy = self._create_directory_structure(organization, output_dir, zf, assessments)
            
            # Copy unreferenced resources to loose files directory
            self._copy_loose_files(output_dir, zf, loose_files)
            
            return hierarchy
    
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
                                  zf: zipfile.ZipFile, assessments: List[Any]) -> HierarchyNode:
        """Create the directory structure based on the organization and return hierarchy."""
        # Create the root hierarchy node
        root_node = HierarchyNode(
            id=organization.identifier,
            title=organization.title,
            type='folder',
            path=''
        )
        
        # Process children recursively
        for child in organization.children:
            child_node = self._process_organization_item(child, output_dir, zf, assessments)
            if child_node:
                root_node.children.append(child_node)
        
        return root_node
    
    def _process_organization_item(self, item: OrganizationItem, parent_dir: Path, 
                                 zf: zipfile.ZipFile, assessments: List[Any]) -> Optional[HierarchyNode]:
        """Process a single organization item and return hierarchy node."""
        if item.identifierref:
            # This item references a resource
            return self._process_resource_item(item, parent_dir, zf, assessments)
        else:
            # This item is a container (folder)
            return self._process_container_item(item, parent_dir, zf, assessments)
    
    def _process_resource_item(self, item: OrganizationItem, parent_dir: Path, 
                             zf: zipfile.ZipFile, assessments: List[Any]) -> Optional[HierarchyNode]:
        """Process an item that references a resource."""
        resource = self.resources.get(item.identifierref)
        if not resource:
            warning_msg = f"Resource {item.identifierref} not found"
            self._add_warning('missing_resource', warning_msg)
            return None
        
        # Mark this resource as processed
        self.processed_resources.add(item.identifierref)
        
        # Create a files subdirectory if it doesn't exist
        files_dir = parent_dir / "files"
        files_dir.mkdir(exist_ok=True)
        
        # Create hierarchy node for this resource
        node = HierarchyNode(
            id=item.identifier,
            title=item.title,
            type='file',
            path=str(parent_dir.relative_to(self.output_dir)) if parent_dir != self.output_dir else ''
        )
        
        # Copy the resource files and convert XML to DOCX
        for file_path in resource.files:
            # Check if the file actually exists in the zip before trying to copy it
            if file_path not in zf.namelist():
                warning_msg = f"Resource file {file_path} referenced in manifest but not found in archive"
                self._add_warning('missing_file', warning_msg, file_path)
                continue
                
            try:
                with zf.open(file_path) as source_file:
                    # Use just the filename, not the full path
                    dest_path = files_dir / Path(file_path).name
                    
                    # Write the file
                    with open(dest_path, 'wb') as dest_file:
                        dest_file.write(source_file.read())
                    
                    # If it's an XML file, also convert to DOCX
                    if file_path.lower().endswith('.xml'):
                        docx_conversion_successful = False
                        try:
                            # Find the assessment that corresponds to this file
                            assessment = self.assessments_by_file.get(file_path)
                            
                            if assessment:
                                # Get file size for progress tracking
                                file_size = 0
                                try:
                                    file_info = zf.getinfo(file_path)
                                    file_size = file_info.file_size
                                except Exception:
                                    file_size = 10000  # Default estimate
                                
                                # Create regular DOCX
                                # Use assessment title instead of XML filename
                                sanitized_title = self._sanitize_filename(assessment.title)
                                docx_filename = f"{sanitized_title}.docx"
                                docx_path = dest_path.parent / docx_filename
                                convert_assessment_to_docx(assessment, docx_path, zf, self.font_mapping, is_answer_key=False, template_path=self.template_path, input_xml_path=file_path, output_dir=self.output_dir)
                                
                                # Add DOCX file info to hierarchy node
                                docx_file_info = {
                                    'name': docx_filename,
                                    'path': str(docx_path.relative_to(self.output_dir)),
                                    'type': 'docx',
                                    'title': assessment.title
                                }
                                node.files.append(docx_file_info)
                                
                                # Update progress after first DOCX conversion
                                self.processed_xml_size += file_size / 2
                                progress = min(100, (self.processed_xml_size / self.total_xml_size) * 100)
                                self._report_progress(f"Converting {Path(file_path).name} to DOCX...", progress)
                                
                                # Create answer key DOCX - use assessment title
                                key_filename = f"{sanitized_title}_key.docx"
                                key_path = dest_path.parent / key_filename
                                convert_assessment_to_docx(assessment, key_path, zf, self.font_mapping, is_answer_key=True, template_path=self.template_path, input_xml_path=file_path, output_dir=self.output_dir)
                                
                                # Add answer key file info to hierarchy node
                                key_file_info = {
                                    'name': key_filename,
                                    'path': str(key_path.relative_to(self.output_dir)),
                                    'type': 'answer_key',
                                    'title': f"{assessment.title} (Answer Key)"
                                }
                                node.files.append(key_file_info)
                                
                                # Update progress after second DOCX conversion
                                self.processed_xml_size += file_size / 2  # Complete progress for this file
                                progress = min(100, (self.processed_xml_size / self.total_xml_size) * 100)
                                self._report_progress(f"Converting {Path(file_path).name} to answer key...", progress)
                                
                                # Mark DOCX conversion as successful
                                docx_conversion_successful = True
                        except Exception as e:
                            error_msg = f"Could not convert XML file {file_path}: {e}"
                            self._add_error('docx_conversion', error_msg, file_path)
                        
                        # Only add XML file to hierarchy if DOCX conversion failed
                        if not docx_conversion_successful:
                            file_info = {
                                'name': Path(file_path).name,
                                'path': str(dest_path.relative_to(self.output_dir)),
                                'type': 'original'
                            }
                            node.files.append(file_info)
                    else:
                        # For non-XML files, always add to hierarchy
                        file_info = {
                            'name': Path(file_path).name,
                            'path': str(dest_path.relative_to(self.output_dir)),
                            'type': 'original'
                        }
                        node.files.append(file_info)
            except Exception as e:
                error_msg = f"Could not process file {file_path}: {e}"
                self._add_error('file_processing', error_msg, file_path)
        
        return node
    
    def _process_container_item(self, item: OrganizationItem, parent_dir: Path, 
                              zf: zipfile.ZipFile, assessments: List[Any]) -> HierarchyNode:
        """Process an item that is a container (folder)."""
        # Create the directory
        item_dir = parent_dir / self._sanitize_filename(item.title)
        item_dir.mkdir(exist_ok=True)
        
        # Create hierarchy node for this container
        node = HierarchyNode(
            id=item.identifier,
            title=item.title,
            type='folder',
            path=str(item_dir.relative_to(self.output_dir)) if item_dir != self.output_dir else ''
        )
        
        # Process children
        for child in item.children:
            child_node = self._process_organization_item(child, item_dir, zf, assessments)
            if child_node:
                node.children.append(child_node)
        
        return node
    
    def _copy_loose_files(self, output_dir: Path, zf: zipfile.ZipFile, loose_files: List[str]) -> None:
        """Copy unreferenced resources to a loose files directory."""
        # Use shared loose files directory if provided, otherwise use local one
        if self.shared_loose_files_dir is not None:
            loose_dir = self.shared_loose_files_dir
        else:
            loose_dir = output_dir / "loose_files"
        
        loose_dir.mkdir(parents=True, exist_ok=True)
        
        # Get cartridge name for prefixing files to avoid conflicts
        cartridge_name = output_dir.name if self.shared_loose_files_dir is not None else ""
        
        # Copy files that are not referenced by any resource
        for file_path in loose_files:
            # Check if the file actually exists in the zip before trying to copy it
            if file_path in zf.namelist():
                try:
                    with zf.open(file_path) as source_file:
                        # Create unique filename to avoid conflicts
                        original_filename = Path(file_path).name
                        if cartridge_name:
                            # Add cartridge prefix to avoid conflicts in shared directory
                            dest_filename = f"{cartridge_name}_{original_filename}"
                        else:
                            dest_filename = original_filename
                        
                        dest_path = loose_dir / dest_filename
                        with open(dest_path, 'wb') as dest_file:
                            dest_file.write(source_file.read())
                except Exception as e:
                    error_msg = f"Could not copy loose file {file_path}: {e}"
                    self._add_error('loose_file_copy', error_msg, file_path)
            else:
                warning_msg = f"Loose file {file_path} referenced in manifest but not found in archive"
                self._add_warning('missing_loose_file', warning_msg, file_path)
        
        # Also copy resources that are not referenced in the organization AND not processed
        for identifier, resource in self.resources.items():
            if identifier not in self.referenced_resources and identifier not in self.processed_resources:
                # This is a truly loose resource
                for file_path in resource.files:
                    # Check if the file actually exists in the zip before trying to copy it
                    if file_path in zf.namelist():
                        try:
                            with zf.open(file_path) as source_file:
                                # Create unique filename to avoid conflicts
                                original_filename = Path(file_path).name
                                if cartridge_name:
                                    # Add cartridge prefix to avoid conflicts in shared directory
                                    dest_filename = f"{cartridge_name}_{original_filename}"
                                else:
                                    dest_filename = original_filename
                                
                                dest_path = loose_dir / dest_filename
                                with open(dest_path, 'wb') as dest_file:
                                    dest_file.write(source_file.read())
                        except Exception as e:
                            error_msg = f"Could not copy unreferenced file {file_path}: {e}"
                            self._add_error('unreferenced_file_copy', error_msg, file_path)
    
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
                    
                    # Try multiple matching strategies
                    matched = False
                    
                    # Strategy 1: Exact title match
                    if assessment.title in xml_content:
                        self.assessments_by_file[xml_file] = assessment
                        matched = True
                        break
                    
                    # Strategy 2: ID match (extract ID from XML and compare with assessment ID)
                    import re
                    # Look for ident="..." in the XML
                    id_match = re.search(r'ident="([^"]+)"', xml_content)
                    if id_match and id_match.group(1) == assessment.ident:
                        self.assessments_by_file[xml_file] = assessment
                        matched = True
                        break
                    
                    # Strategy 3: Case-insensitive title match
                    if assessment.title.lower() in xml_content.lower():
                        self.assessments_by_file[xml_file] = assessment
                        matched = True
                        break
                    
                    # Strategy 4: Partial title match (first 20 characters)
                    title_start = assessment.title[:20]
                    if title_start in xml_content:
                        self.assessments_by_file[xml_file] = assessment
                        matched = True
                        break
                        
                except Exception as e:
                    warning_msg = f"Could not read XML file {xml_file} for assessment mapping: {e}"
                    self._add_warning('xml_reading', warning_msg, xml_file)
                    continue
            
            # If no match found, log it
            if not any(xml_file in self.assessments_by_file for xml_file in xml_files):
                warning_msg = f"Could not find XML file for assessment '{assessment.title}' (ID: {assessment.ident})"
                self._add_warning('assessment_mapping', warning_msg)
    
    def _create_hierarchy_json(self, output_dir: Path, hierarchy: HierarchyNode) -> None:
        """Create a hierarchy.json file with the complete structure."""
        try:
            # Convert hierarchy to dictionary
            hierarchy_dict = self._hierarchy_node_to_dict(hierarchy)
            
            # Write to JSON file
            json_path = output_dir / "hierarchy.json"
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(hierarchy_dict, f, indent=2, ensure_ascii=False)
        except Exception as e:
            error_msg = f"Failed to create hierarchy.json: {str(e)}"
            self._add_error('hierarchy_creation', error_msg)
            self.hierarchy_creation_error = error_msg
            print(f"Error creating hierarchy.json: {e}")
            print(f"Hierarchy type: {type(hierarchy)}")
            if hasattr(hierarchy, 'path'):
                print(f"Path type: {type(hierarchy.path)}")
                print(f"Path value: {hierarchy.path}")
            raise
    
    def _hierarchy_node_to_dict(self, node: HierarchyNode) -> Dict[str, Any]:
        """Convert a HierarchyNode to a dictionary for JSON serialization."""
        # Ensure all fields are JSON serializable
        result = {
            'id': str(node.id),
            'title': str(node.title),
            'type': str(node.type),
            'path': str(node.path) if node.path is not None else ''
        }
        
        if node.children:
            result['children'] = [self._hierarchy_node_to_dict(child) for child in node.children]
        
        if node.files:
            # Ensure all file info is also JSON serializable
            serializable_files = []
            for file_info in node.files:
                serializable_file = {}
                for key, value in file_info.items():
                    serializable_file[key] = str(value) if value is not None else ''
                serializable_files.append(serializable_file)
            result['files'] = serializable_files
        
        return result
    
    def _calculate_total_xml_size(self, zf: zipfile.ZipFile) -> None:
        """Calculate the total size of XML files that will be converted to DOCX."""
        self.total_xml_size = 0
        self.processed_xml_size = 0
        
        # Get all XML files that have corresponding assessments
        for file_path in zf.namelist():
            if file_path.lower().endswith('.xml') and file_path in self.assessments_by_file:
                try:
                    file_info = zf.getinfo(file_path)
                    self.total_xml_size += file_info.file_size
                except Exception:
                    # If we can't get file size, estimate based on file count
                    self.total_xml_size += 10000  # Default estimate of 10KB per file
        
        if self.total_xml_size == 0:
            # Fallback: if no XML files found, set a default
            self.total_xml_size = 1 