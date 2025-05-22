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


if __name__ == "__main__":
    unittest.main()
