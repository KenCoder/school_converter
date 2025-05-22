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
    """Create a docx file containing ``text`` using ``python-docx``."""

    try:
        from docx import Document
    except Exception as exc:  # pragma: no cover - raises when dependency missing
        raise ImportError(
            "The 'python-docx' package is required to create docx files"
        ) from exc

    doc = Document()
    doc.add_paragraph(text)
    doc.save(doc_path)


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
