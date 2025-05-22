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


def convert_cartridge_to_doc(cartridge: Path, output_dir: Path):
    """Placeholder converter that verifies the cartridge can be read.

    The actual conversion to a doc file is not implemented. Instead, the
    imsmanifest.xml is extracted to the output directory.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(cartridge, 'r') as zf:
        zf.extract('imsmanifest.xml', path=output_dir)
    print(f"Extracted imsmanifest.xml to {output_dir}")


def main(argv=None):
    args = parse_args(argv)
    convert_cartridge_to_doc(args.cartridge, args.output)


if __name__ == "__main__":  # pragma: no cover
    main()
