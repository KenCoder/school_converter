import argparse
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Convert 1EdTech Common Cartridge files to doc files"
    )
    parser.add_argument("cartridge", type=Path, help="Path to .imscc file")
    parser.add_argument(
        "output", type=Path, help="Directory to write output document", nargs="?", default=Path("output")
    )
    return parser.parse_args(argv)


def _create_docx(doc_path: Path, text: str) -> None:
    """Create a minimal docx file containing ``text``."""

    document_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>{text}</w:t></w:r></w:p>
  </w:body>
</w:document>"""

    content_types = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
"""

    rels = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
"""

    with zipfile.ZipFile(doc_path, "w") as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("word/document.xml", document_xml)


def convert_cartridge_to_doc(cartridge: Path, output_dir: Path):
    """Convert ``cartridge`` into one docx per resource in ``output_dir``."""

    output_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(cartridge, "r") as zf:
        with zf.open("imsmanifest.xml") as manifest_file:
            tree = ET.parse(manifest_file)

        root = tree.getroot()
        ns = {"ns": root.tag.split("}")[0].strip("{")}
        resources = root.findall(".//ns:resource", ns)

        for res in resources:
            identifier = res.get("identifier")
            if not identifier:
                continue
            doc_path = output_dir / f"{identifier}.docx"
            _create_docx(doc_path, identifier)

    print(f"Created {len(resources)} docx files in {output_dir}")


def main(argv=None):
    args = parse_args(argv)
    convert_cartridge_to_doc(args.cartridge, args.output)


if __name__ == "__main__":  # pragma: no cover
    main()
