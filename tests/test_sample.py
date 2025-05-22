import unittest
from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET

SAMPLE = Path(__file__).resolve().parent.parent / "sample1.imscc"


class TestSampleCartridge(unittest.TestCase):
    def test_sample_has_six_resources(self):
        self.assertTrue(SAMPLE.exists(), f"{SAMPLE} missing")
        with zipfile.ZipFile(SAMPLE, 'r') as zf:
            with zf.open('imsmanifest.xml') as manifest_file:
                tree = ET.parse(manifest_file)
        root = tree.getroot()
        ns = {'ns': root.tag.split('}')[0].strip('{')}
        resources = root.findall('.//ns:resource', ns)
        self.assertEqual(6, len(resources))

    def test_converter_creates_docx_files(self):
        """convert_cartridge_to_doc should create one docx per resource."""

        from tempfile import TemporaryDirectory
        import cc_converter.cli as cli
        from cc_converter.cli import convert_cartridge_to_doc

        try:
            from docx import Document  # noqa: F401
            patch_create = False
        except Exception:
            patch_create = True

        def fake_create_docx(doc_path: Path, document, zf):
            document_xml = f"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\">
  <w:body>
    <w:p><w:r><w:t>{document.title}</w:t></w:r></w:p>
  </w:body>
</w:document>"""

            content_types = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\">
  <Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/>
  <Default Extension=\"xml\" ContentType=\"application/xml\"/>
  <Override PartName=\"/word/document.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml\"/>
</Types>
"""

            rels = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">
  <Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" Target=\"word/document.xml\"/>
</Relationships>
"""

            with zipfile.ZipFile(doc_path, "w") as zf:
                zf.writestr("[Content_Types].xml", content_types)
                zf.writestr("_rels/.rels", rels)
                zf.writestr("word/document.xml", document_xml)

        if patch_create:
            original = cli._create_docx
            cli._create_docx = fake_create_docx

        try:
            with TemporaryDirectory() as tmpdir:
                output_dir = Path(tmpdir)
                convert_cartridge_to_doc(SAMPLE, output_dir)
                docs = sorted(output_dir.glob("*.docx"))
                self.assertEqual(6, len(docs))
                for doc in docs:
                    with zipfile.ZipFile(doc, "r") as zf:
                        self.assertIn("word/document.xml", zf.namelist())
        finally:
            if patch_create:
                cli._create_docx = original

    def test_parse_all_documents(self):
        import cc_converter.parser as parser
        with zipfile.ZipFile(SAMPLE, 'r') as zf:
            with zf.open('imsmanifest.xml') as manifest_file:
                tree = ET.parse(manifest_file)
            root = tree.getroot()
            ns = {'ns': root.tag.split('}')[0].strip('{')}
            for res in root.findall('.//ns:resource', ns):
                href = res.find('ns:file', ns).get('href')
                with zf.open(href) as f:
                    xml_text = f.read().decode('utf-8')
                doc = parser.parse_assessment(xml_text)
                self.assertTrue(doc.questions)


if __name__ == "__main__":
    unittest.main()
