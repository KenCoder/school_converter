from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple, Union
from enum import Enum


class QuestionType(Enum):
    MULTIPLE_CHOICE = "multiple_choice"
    ESSAY = "essay"
    # We could add more types later
    # FREE_ANSWER = "free_answer"
    # Fill in types as needed


@dataclass
class TextStyle:
    """Represents text styling information for docx conversion."""
    font_family: Optional[str] = None
    font_size: Optional[float] = None
    bold: bool = False
    color: Optional[str] = None
    superscript: bool = False
    subscript: bool = False
    image: Optional['ImageInfo'] = None  # Reference to an image within the text


@dataclass
class TextRun:
    """Represents a run of text with consistent styling."""
    text: str
    style: TextStyle = field(default_factory=TextStyle)
    # For backward compatibility
    @property
    def superscript(self) -> bool:
        return self.style.superscript
    
    @property
    def subscript(self) -> bool:
        return self.style.subscript


@dataclass
class ImageInfo:
    """Represents an image in the assessment."""
    src: str
    width: Optional[int] = None
    height: Optional[int] = None


# Define a TextContent type that can be either a TextRun or an ImageInfo
TextContent = Union[TextRun, ImageInfo]


@dataclass
class ResponseOption:
    """Represents a response option in a multiple choice question."""
    ident: str
    text: List[TextContent]  # Changed from List[TextRun] to List[TextContent]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Item:
    """Represents a question/item in the assessment."""
    ident: str
    question_type: QuestionType
    text: List[TextContent]  # Changed from List[TextRun] to List[TextContent]
    response_options: List[ResponseOption] = field(default_factory=list)
    correct_response: Optional[str] = None  # Identifier of the correct response
    metadata: Dict[str, Any] = field(default_factory=dict)
    # Removed the images field since images are now inlined in the text


@dataclass
class Section:
    """Represents a section in the assessment containing items."""
    ident: str
    items: List[Item] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Assessment:
    """Represents a complete assessment."""
    ident: str
    title: str
    sections: List[Section] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


# Keep the old models for backward compatibility
@dataclass
class Answer:
    text: List[TextRun]
    correct: bool = False
    images: List[str] = field(default_factory=list)


@dataclass
class Question:
    text: List[TextRun]
    answers: List[Answer] = field(default_factory=list)
    qtype: Optional[str] = None
    images: List[str] = field(default_factory=list)


@dataclass
class Document:
    title: str
    questions: List[Question] = field(default_factory=list)
    images: List[str] = field(default_factory=list)
    
    @classmethod
    def from_assessment(cls, assessment: Assessment) -> 'Document':
        """Convert new Assessment model to the old Document model for compatibility."""
        doc = cls(title=assessment.title)
        
        for section in assessment.sections:
            for item in section.items:
                question = Question(
                    text=item.text,
                    qtype=item.question_type.value if item.question_type else None,
                    images=[img.src for img in item.images]
                )
                
                for option in item.response_options:
                    answer = Answer(
                        text=option.text,
                        correct=option.ident == item.correct_response,
                        images=[img.src for img in option.images]
                    )
                    question.answers.append(answer)
                
                doc.questions.append(question)
        
        return doc
