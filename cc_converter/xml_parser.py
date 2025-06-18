import re
import zipfile
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from typing import List, Dict, Any, Tuple, Optional
import html
from copy import deepcopy

from cc_converter.models import (
    Assessment, Section, Item, ResponseOption, 
    TextRun, TextStyle, QuestionType, ImageInfo, TextContent
)

# Define XML namespaces
QTI_NS = "http://www.imsglobal.org/xsd/ims_qtiasiv1p2"
NS = {"qti": QTI_NS}

class ParserError(Exception):
    """Exception raised for parser errors"""
    pass

class HTMLStyleParser(HTMLParser):
    """Parses HTML content and extracts text with styling information."""
    
    def __init__(self):
        super().__init__()
        self.runs = []  # This will contain both TextRun and ImageInfo objects
        self.stack = []
        self.current_style = TextStyle()
    
    def _rebuild_current_style(self):
        """Rebuild the current style based on the tag stack."""
        style = TextStyle()
        
        for context in self.stack:
            # Handle font family
            if "font-family" in context:
                style.font_family = context["font-family"]
            
            # Handle font size
            if "font-size" in context:
                style.font_size = context["font-size"]
            
            # Handle bold
            if "bold" in context:
                style.bold = context["bold"]
            
            # Handle color
            if "color" in context:
                style.color = context["color"]

            if "vertical-align" in context:
                if context["vertical-align"] == "sub":
                    style.subscript = True
                elif context["vertical-align"] == "super":
                    style.superscript = True
            
            # Handle superscript/subscript
            if context.get("tag") == "sup":
                style.superscript = True
            elif context.get("tag") == "sub":
                style.subscript = True
        
        self.current_style = style
    
    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        
        # Create a context for this tag
        context = {"tag": tag}
        
        # Handle style attribute
        if "style" in attrs_dict:
            # Parse inline styles
            style_str = attrs_dict["style"]
            style_parts = [p.strip() for p in style_str.split(";") if p.strip()]
            
            for part in style_parts:
                if ":" in part:
                    prop, value = part.split(":", 1)
                    prop = prop.strip().lower()
                    value = value.strip()
                    
                    if prop == "font-family":
                        context["font-family"] = value.strip("'\"")
                    elif prop == "font-size":
                        try:
                            # Try to convert to numeric value
                            if value.endswith("pt"):
                                context["font-size"] = float(value[:-2])
                            elif value.endswith("px"):
                                # Convert px to pt (approx)
                                context["font-size"] = float(value[:-2]) * 0.75
                        except ValueError:
                            pass
                    elif prop == "color":
                        context["color"] = value
                    elif prop == "font-weight" and value in ("bold", "700", "800", "900"):
                        context["bold"] = True
                    elif prop == "vertical-align":
                        context["vertical-align"] = value
        
        # Handle font tag
        if tag == "font":
            if "face" in attrs_dict:
                context["font-family"] = attrs_dict["face"]
            if "color" in attrs_dict:
                context["color"] = attrs_dict["color"]
            if "size" in attrs_dict:
                try:
                    size = attrs_dict["size"]
                    if size.startswith("+"):
                        # Relative size, convert to approx pt
                        context["font-size"] = 12 + int(size[1:]) * 2
                    elif size.startswith("-"):
                        # Relative size, convert to approx pt
                        context["font-size"] = 12 - int(size[1:]) * 2
                    else:
                        # Absolute size, convert to approx pt
                        sizes = [8, 10, 12, 14, 18, 24, 36]
                        try:
                            idx = int(size) - 1
                            if 0 <= idx < len(sizes):
                                context["font-size"] = sizes[idx]
                        except ValueError:
                            pass
                except (ValueError, IndexError):
                    pass
        
        # Handle bold tag
        elif tag in ("b", "strong"):
            context["bold"] = True
        
        # Handle image tag
        elif tag == "img":
            src = attrs_dict.get("src")
            if src:
                # Create an ImageInfo object and add it directly to runs
                width = None
                height = None
                
                # Extract width and height if available
                if "width" in attrs_dict:
                    try:
                        width = int(attrs_dict["width"])
                    except ValueError:
                        pass
                
                if "height" in attrs_dict:
                    try:
                        height = int(attrs_dict["height"])
                    except ValueError:
                        pass
                
                img_info = ImageInfo(src=sanitize_src(src), width=width, height=height)
                self.runs.append(img_info)
        
        # Handle line break
        elif tag == "br":
            self.runs.append(TextRun("\n", style=TextStyle()))
        
        # Push current context to stack
        self.stack.append(context)
        
        # Update current style
        self._rebuild_current_style()
    
    def handle_endtag(self, tag):
        if not self.stack:
            return
        
        # Pop the context
        context = self.stack.pop()
        if context["tag"] != tag:
            # Mismatched tags, try to recover
            # Find the matching tag in the stack
            for i in range(len(self.stack)-1, -1, -1):
                if self.stack[i]["tag"] == tag:
                    # Remove all contexts up to and including this one
                    for _ in range(len(self.stack) - i):
                        self.stack.pop()
                    break
        
        # Reset current style based on the remaining stack
        self._rebuild_current_style()
        
        # Add paragraph break for paragraph end
        if tag == "p":
            self.runs.append(TextRun("\n", style=TextStyle()))
    
    def handle_data(self, data):
        if data:
            # Create a TextRun with the current style
            run = TextRun(data, style=deepcopy(self.current_style))
            self.runs.append(run)


def parse_html_content(html_content: str) -> List[TextContent]:
    """Parse HTML content into a list of TextRun and ImageInfo objects."""
    # First decode HTML entities
    decoded_html = html.unescape(html_content)
    
    # Parse the HTML
    parser = HTMLStyleParser()
    parser.feed(decoded_html)
    
    return parser.runs


def sanitize_src(src: str) -> str:
    """Sanitize image source paths."""
    if src.startswith("$IMS-CC-FILEBASE$"):
        return src.replace("$IMS-CC-FILEBASE$", "").lstrip("./")
    return src


class XMLParser:
    """Parser for QTI XML assessment files."""
    
    def __init__(self, font_mapping: Optional[Dict[str, str]] = None):
        self.font_mapping = font_mapping or {}
        self.allowed_tags = {
            "assessment", "section", "item", "itemmetadata", 
            "qtimetadata", "qtimetadatafield", "fieldlabel", "fieldentry",
            "presentation", "material", "mattext", 
            "response_lid", "render_choice", "response_label",
            "response_str", "render_fib",
            "resprocessing", "outcomes", "decvar", "respcondition", 
            "conditionvar", "varequal", "setvar"
        }
    
    def parse_assessment_xml(self, xml_text: str) -> Assessment:
        """Parse assessment XML into an Assessment object."""
        # Replace HTML entities
        xml_text = re.sub(r"&(?!amp;|lt;|gt;|quot;|apos;)[a-zA-Z]+;", "", xml_text)
        
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as e:
            raise ParserError(f"Failed to parse XML: {str(e)}")
        
        # Check for questestinterop root
        if not root.tag.endswith("questestinterop"):
            raise ParserError(f"Expected questestinterop root element, got {root.tag}")
        
        # Find assessment element
        assessment_elem = root.find(".//qti:assessment", NS)
        if assessment_elem is None:
            raise ParserError("Assessment element not found")
        
        assessment_id = assessment_elem.get("ident", "")
        assessment_title = assessment_elem.get("title", "Untitled Assessment")
        
        # Create assessment
        assessment = Assessment(
            ident=assessment_id,
            title=assessment_title,
            metadata=self._parse_metadata(assessment_elem)
        )
        
        # Find sections
        for section_elem in assessment_elem.findall(".//qti:section", NS):
            section = self._parse_section(section_elem)
            assessment.sections.append(section)
        
        return assessment
    
    def _parse_section(self, section_elem: ET.Element) -> Section:
        """Parse a section element."""
        section_id = section_elem.get("ident", "")
        
        section = Section(
            ident=section_id,
            metadata=self._parse_metadata(section_elem)
        )
        
        # Find items
        for item_elem in section_elem.findall("qti:item", NS):
            try:
                item = self._parse_item(item_elem)
                section.items.append(item)
            except Exception as e:
                # We'll log the error but continue with other items
                print(f"Error parsing item {item_elem.get('ident', '')}: {str(e)}")
        
        return section
    
    def _parse_item(self, item_elem: ET.Element) -> Item:
        """Parse an item element."""
        item_id = item_elem.get("ident", "")
        
        # Parse item metadata to determine type
        metadata = self._parse_metadata(item_elem)
        
        try:
            question_type = self._determine_question_type(metadata)
        except ParserError:
            # Fallback to ESSAY for unknown types
            print(f"Using ESSAY type as fallback for item {item_id}")
            question_type = QuestionType.ESSAY
        
        # Parse presentation
        presentation = item_elem.find("qti:presentation", NS)
        if presentation is None:
            raise ParserError(f"Presentation element not found for item {item_id}")
        
        # Parse material
        material = presentation.find("qti:material", NS)
        if material is None:
            raise ParserError(f"Material element not found for item {item_id}")
        
        mattext = material.find("qti:mattext", NS)
        html_content = ""
        if mattext is not None:
            html_content = mattext.text or ""
        
        text_runs = parse_html_content(html_content)
        
        # Create a combined content list with both text runs and images
        content = []
        content.extend(text_runs)
        
        # Create item
        item = Item(
            ident=item_id,
            question_type=question_type,
            text=content,  # Use the combined content list
            metadata=metadata
        )
        
        # Parse response options for multiple choice
        if question_type == QuestionType.MULTIPLE_CHOICE:
            self._parse_response_options(item, presentation, item_elem)
        
        return item
    
    def _parse_metadata(self, elem: ET.Element) -> Dict[str, Any]:
        """Parse metadata from an element."""
        metadata = {}
        
        metadata_elem = elem.find(".//qti:itemmetadata", NS)
        if metadata_elem is None:
            return metadata
        
        qti_metadata = metadata_elem.find(".//qti:qtimetadata", NS)
        if qti_metadata is not None:
            for field_elem in qti_metadata.findall(".//qti:qtimetadatafield", NS):
                label_elem = field_elem.find("qti:fieldlabel", NS)
                entry_elem = field_elem.find("qti:fieldentry", NS)
                
                if label_elem is not None and entry_elem is not None:
                    label = label_elem.text
                    entry = entry_elem.text
                    if label and entry:
                        metadata[label] = entry
        
        return metadata
    
    def _determine_question_type(self, metadata: Dict[str, Any]) -> QuestionType:
        """Determine the question type from metadata."""
        cc_profile = metadata.get("cc_profile", "")
        
        if "multiple_choice" in cc_profile:
            return QuestionType.MULTIPLE_CHOICE
        elif "essay" in cc_profile:
            # Support essay question type
            return QuestionType.ESSAY
        
        # For unsupported types, use ESSAY as a fallback
        print(f"Unsupported question type: {cc_profile}, treating as essay")
        return QuestionType.ESSAY
    
    def _parse_response_options(self, item: Item, presentation: ET.Element, item_elem: ET.Element):
        """Parse response options for a multiple choice item."""
        # Find the response_lid element
        response_lid = presentation.find(".//qti:response_lid", NS)
        if response_lid is None:
            return
        
        # Find all render_choice elements
        render_choice = response_lid.find("qti:render_choice", NS)
        if render_choice is None:
            return
        
        # Find all response_label elements
        for label_elem in render_choice.findall("qti:response_label", NS):
            label_id = label_elem.get("ident", "")
            
            # Parse material
            material = label_elem.find("qti:material", NS)
            if material is None:
                continue
            
            mattext = material.find("qti:mattext", NS)
            html_content = ""
            if mattext is not None:
                html_content = mattext.text or ""
            
            text_runs = parse_html_content(html_content)
            
            # Create a combined content list with both text runs and images
            content = []
            content.extend(text_runs)
            
            option = ResponseOption(
                ident=label_id,
                text=content  # Use the combined content list
            )
            
            item.response_options.append(option)
        
        # Parse the correct response if available
        resprocessing = item_elem.find("qti:resprocessing", NS)
        if resprocessing is not None:
            for respcondition in resprocessing.findall("qti:respcondition", NS):
                varequal = respcondition.find(".//qti:varequal", NS)
                if varequal is not None and varequal.text:
                    item.correct_response = varequal.text
                    break


def parse_cartridge(cartridge_path: str, font_mapping: Optional[Dict[str, str]] = None, limit: Optional[int] = None) -> List[Assessment]:
    """Parse a Common Cartridge file into a list of Assessment objects."""
    assessments = []
    parser = XMLParser(font_mapping)
    
    with zipfile.ZipFile(cartridge_path, "r") as zf:
        with zf.open("imsmanifest.xml") as manifest_file:
            tree = ET.parse(manifest_file)
        
        manifest_root = tree.getroot()
        ns = {"ns": manifest_root.tag.split("}")[0].strip("{")}
        
        for res in manifest_root.findall(".//ns:resource", ns):
            # Check if we've reached the limit
            if limit is not None and len(assessments) >= limit:
                break
                
            href_elem = res.find("ns:file", ns)
            if href_elem is None:
                continue
            
            href = href_elem.get("href")
            if not href:
                continue
            
            try:
                with zf.open(href) as f:
                    xml_text = f.read().decode("utf-8")
                
                assessment = parser.parse_assessment_xml(xml_text)
                assessments.append(assessment)
            except Exception as e:
                print(f"Error parsing resource {href}: {str(e)}")
    
    return assessments


def parse_extracted_file(file_path: str, font_mapping: Optional[Dict[str, str]] = None) -> Assessment:
    """Parse an extracted XML file into an Assessment object."""
    parser = XMLParser(font_mapping)
    
    with open(file_path, 'r', encoding='utf-8') as f:
        xml_text = f.read()
    
    return parser.parse_assessment_xml(xml_text) 