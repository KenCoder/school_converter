from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class TextRun:
    text: str
    superscript: bool = False
    subscript: bool = False

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
