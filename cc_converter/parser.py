import zipfile
import re
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from typing import List, Tuple
from .models import Document, Question, Answer, TextRun

QTI_NS = "http://www.imsglobal.org/xsd/ims_qtiasiv1p2"
NS = {"qti": QTI_NS}

class _HTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.runs: List[TextRun] = []
        self.images: List[str] = []
        self.stack: List[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in ("sup", "sub"):
            self.stack.append(tag)
        elif tag == "img":
            attrs_dict = dict(attrs)
            src = attrs_dict.get("src")
            if src:
                self.images.append(src)
        elif tag == "br":
            self.runs.append(TextRun("\n"))

    def handle_endtag(self, tag):
        if tag in ("sup", "sub") and self.stack and self.stack[-1] == tag:
            self.stack.pop()
        elif tag == "p":
            self.runs.append(TextRun("\n"))

    def handle_data(self, data):
        if not data:
            return
        run = TextRun(
            data,
            superscript="sup" in self.stack,
            subscript="sub" in self.stack,
        )
        self.runs.append(run)


def _parse_html(text: str) -> Tuple[List[TextRun], List[str]]:
    parser = _HTMLParser()
    parser.feed(text)
    return parser.runs, parser.images


def _sanitize_src(src: str) -> str:
    if src.startswith("$IMS-CC-FILEBASE$"):
        return src.replace("$IMS-CC-FILEBASE$", "").lstrip("./")
    return src


def _parse_question(item: ET.Element) -> Question:
    mat = item.find(
        ".//qti:presentation/qti:material/qti:mattext", NS
    )
    text_html = mat.text if mat is not None else ""
    runs, images = _parse_html(text_html)
    images = [_sanitize_src(s) for s in images]

    question = Question(text=runs, images=images)

    resp_lid = item.find(".//qti:response_lid", NS)
    resp_str = item.find(".//qti:response_str", NS)
    if resp_lid is not None:
        question.qtype = "multiple_choice"
        id_to_answer = {}
        for label in resp_lid.findall("qti:response_label", NS):
            ident = label.get("ident")
            m = label.find("qti:material/qti:mattext", NS)
            label_text = m.text if m is not None else ""
            aruns, aimgs = _parse_html(label_text)
            ans = Answer(text=aruns, images=[_sanitize_src(s) for s in aimgs])
            id_to_answer[ident] = ans
            question.answers.append(ans)

        for rc in item.findall("qti:respcondition", NS):
            var = rc.find("qti:conditionvar/qti:varequal", NS)
            if var is not None and var.text in id_to_answer:
                id_to_answer[var.text].correct = True
    elif resp_str is not None:
        question.qtype = "free_answer"
    else:
        question.qtype = "unknown"

    return question


def parse_assessment(xml_text: str) -> Document:
    xml_text = xml_text.replace("&rarr;", "->")
    root = ET.fromstring(xml_text)
    assessment = root.find("qti:assessment", NS)
    title = assessment.get("title") if assessment is not None else "assessment"
    document = Document(title=title)

    for item in root.findall(".//qti:item", NS):
        document.questions.append(_parse_question(item))

    return document


def parse_cartridge(cartridge_path) -> List[Document]:
    """Return list of Documents parsed from ``cartridge_path``."""
    docs = []
    with zipfile.ZipFile(cartridge_path, "r") as zf:
        with zf.open("imsmanifest.xml") as manifest_file:
            tree = ET.parse(manifest_file)
        manifest_root = tree.getroot()
        ns = {"ns": manifest_root.tag.split("}")[0].strip("{")}
        for res in manifest_root.findall(".//ns:resource", ns):
            href_elem = res.find("ns:file", ns)
            if href_elem is None:
                continue
            href = href_elem.get("href")
            if not href:
                continue
            with zf.open(href) as f:
                xml_text = f.read().decode("utf-8")
            docs.append(parse_assessment(xml_text))
    return docs
