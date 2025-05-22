# School Converter

This repository contains a minimal command line application for converting
1EdTech Common Cartridge (`.imscc`) files to document files. The conversion
logic is not fully implemented; currently the application extracts the
`imsmanifest.xml` from the cartridge as a placeholder.

## Usage

```bash
cc-convert sample1.imscc output_dir
```

This command will extract the `imsmanifest.xml` from `sample1.imscc` into
`output_dir`.

## Development

Run tests with:

```bash
python -m unittest discover -s tests -v
```
