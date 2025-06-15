from pathlib import Path
from typing import Dict, Optional, List, Union
import json
import os
import zipfile

from .models import Assessment, TextRun, ImageInfo, QuestionType


class GoogleFormsConverter:
    """Converter for Assessment objects to Google Forms compatible format."""

    def __init__(self):
        """Initialize the converter."""
        pass

    def convert_assessment(
        self, assessment: Assessment, output_path: Path,
        resource_zip: Optional[zipfile.ZipFile] = None
    ):
        """Convert an Assessment object to a Google Forms compatible JSON file.

        Args:
            assessment: The Assessment object to convert.
            output_path: The path where the JSON file will be saved.
            resource_zip: An optional zipfile containing resources such as images.
        """
        forms_data = {
            "formTitle": assessment.title,
            "formDescription": assessment.metadata.get("description", ""),
            "items": []
        }

        # Process each section
        for section_idx, section in enumerate(assessment.sections):
            # Add section header if multiple sections
            if len(assessment.sections) > 1:
                forms_data["items"].append({
                    "title": f"Section {section_idx}",
                    "description": "",
                    "questionType": "SECTION_HEADER"
                })

            # Process each item/question
            for item in section.items:
                question_item = self._convert_item(item, resource_zip)
                forms_data["items"].append(question_item)

        # Create output directory if it doesn't exist
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Save the JSON file
        with open(output_path, 'w') as f:
            json.dump(forms_data, f, indent=2)

    def _convert_item(self, item, resource_zip):
        """Convert an Assessment Item to a Google Forms question item."""
        # Convert text content to plain text (with placeholders for images)
        question_text = self._content_to_text(item.text)
        
        # Base question structure
        question = {
            "title": question_text,
            "required": True
        }
        
        # Handle different question types
        if item.question_type == QuestionType.MULTIPLE_CHOICE:
            question["questionType"] = "MULTIPLE_CHOICE"
            question["choices"] = []
            
            # Add options
            for option in item.response_options:
                option_text = self._content_to_text(option.text)
                question["choices"].append({
                    "value": option_text,
                    "isCorrect": option.ident == item.correct_response
                })
                
            # Set answer key if available
            if item.correct_response:
                for idx, option in enumerate(item.response_options):
                    if option.ident == item.correct_response:
                        question["correctAnswer"] = idx
                        break
                
        elif item.question_type == QuestionType.ESSAY:
            question["questionType"] = "PARAGRAPH_TEXT"
        
        return question

    def _content_to_text(self, content_list) -> str:
        """Convert a list of TextContent objects to a plain text representation."""
        result = []
        
        for content in content_list:
            if isinstance(content, TextRun):
                result.append(content.text)
            elif isinstance(content, ImageInfo):
                # For Google Forms, we can't directly embed images in the JSON
                # Instead add a placeholder that can be manually replaced
                result.append(f"[IMAGE: {os.path.basename(content.src)}]")
        
        return "".join(result)


def convert_assessment_to_google_forms(
    assessment: Assessment,
    output_path: Union[str, Path],
    resource_zip: Optional[Union[str, zipfile.ZipFile]] = None
):
    """Convert an assessment to a Google Forms compatible JSON file.
    
    Args:
        assessment: The Assessment object to convert.
        output_path: Path where the output JSON file should be saved.
        resource_zip: Path to or instance of a ZIP file containing resources 
            (like images) referenced in the assessment.
    """
    # Convert path strings to Path objects
    if isinstance(output_path, str):
        output_path = Path(output_path)
    
    # Open the resource zip if a path was provided
    zip_obj = None
    if resource_zip is not None and isinstance(resource_zip, str):
        zip_obj = zipfile.ZipFile(resource_zip, 'r')
    else:
        zip_obj = resource_zip
    
    try:
        # Perform the conversion
        converter = GoogleFormsConverter()
        converter.convert_assessment(assessment, output_path, zip_obj)
    finally:
        # Close the zip file if we opened it
        if zip_obj is not None and isinstance(resource_zip, str):
            zip_obj.close()


def convert_cartridge_to_google_forms(
    cartridge_path: Union[str, Path],
    output_dir: Union[str, Path],
    limit: Optional[int] = None
):
    """Convert all assessments in a Common Cartridge file to Google Forms format.
    
    Args:
        cartridge_path: Path to the .imscc file.
        output_dir: Directory where the output JSON files should be saved.
        limit: Maximum number of assessments to process (default: all).
        
    Returns:
        int: The number of files created.
    """
    from .xml_parser import parse_cartridge
    
    # Convert path strings to Path objects
    if isinstance(cartridge_path, str):
        cartridge_path = Path(cartridge_path)
    if isinstance(output_dir, str):
        output_dir = Path(output_dir)
    
    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Parse the cartridge file
    assessments = parse_cartridge(cartridge_path, limit=limit)
    
    # Open the cartridge as a zip file for resource extraction
    with zipfile.ZipFile(cartridge_path, 'r') as resource_zip:
        count = 0
        
        # Convert each assessment
        for assessment in assessments:
            # Create a safe filename from the assessment title
            safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in assessment.title)
            safe_name = safe_name.strip().replace(" ", "_")
            output_file = output_dir / f"{safe_name}.json"
            
            # Perform the conversion
            convert_assessment_to_google_forms(assessment, output_file, resource_zip)
            count += 1
    
    return count 