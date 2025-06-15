#!/usr/bin/env python3
"""
Test script for the enhanced Google Docs converter with image handling.
This script creates a simple assessment with images and converts it to Google Docs.
"""

from cc_converter.models import Assessment, Section, Item, QuestionType, TextRun, ImageInfo, ResponseOption
from cc_converter.google_docs_converter import convert_assessment_to_google_docs

def create_test_assessment():
    """Create a test assessment with images."""
    
    # Create a simple multiple choice question with an image
    question_text = [
        TextRun("What is shown in this image? "),
        ImageInfo(src="https://via.placeholder.com/300x200.png?text=Test+Image", width=300, height=200),
        TextRun(" Select the correct answer.")
    ]
    
    # Create response options
    options = [
        ResponseOption(ident="A", text=[TextRun("Option A")]),
        ResponseOption(ident="B", text=[TextRun("Option B - Correct")]),
        ResponseOption(ident="C", text=[TextRun("Option C")]),
        ResponseOption(ident="D", text=[TextRun("Option D")])
    ]
    
    # Create the question item
    question_item = Item(
        ident="q1",
        question_type=QuestionType.MULTIPLE_CHOICE,
        text=question_text,
        response_options=options,
        correct_response="B"
    )
    
    # Create a section
    section = Section(ident="section1", items=[question_item])
    
    # Create the assessment
    assessment = Assessment(
        ident="test_assessment",
        title="Test Assessment with Images",
        sections=[section]
    )
    
    return assessment

def main():
    """Main test function."""
    print("Creating test assessment with images...")
    assessment = create_test_assessment()
    
    print("Converting to Google Docs...")
    try:
        # Note: You'll need to have credentials.json and authenticate
        document_id, document_url = convert_assessment_to_google_docs(
            assessment,
            "Test Assessment with Images",
            storage_folder="CC_Converter_Test"  # Store images in organized folder
        )
        
        print(f"Success! Document created:")
        print(f"Document ID: {document_id}")
        print(f"Document URL: {document_url}")
        
    except Exception as e:
        print(f"Error: {e}")
        print("Make sure you have:")
        print("1. credentials.json file in the current directory")
        print("2. Proper Google API access enabled")
        print("3. Internet connection for image download")

if __name__ == "__main__":
    main() 