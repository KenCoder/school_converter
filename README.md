# Common Cartridge Format Converter

A tool to convert 1EdTech Common Cartridge (.imscc) files to DOCX format.

## Features

- Converts Common Cartridge assessments to DOCX format
- Preserves question formatting and structure
- Handles multiple choice and essay questions
- Supports images and other resources
- Processes entire cartridges or individual XML files

## Installation

```bash
pip install cc-converter
```

## Usage

### Basic Usage

Convert a cartridge file to DOCX:

```bash
cc-convert input.imscc output_directory
```

Convert a single XML file:

```bash
cc-convert assessment.xml output.docx
```

### Options

- `--font-map`: Path to JSON file with font mapping
- `--limit`: Maximum number of assessments to process

Example with font mapping:

```bash
cc-convert quiz.imscc --font-map fonts.json
```

## Development

Run tests with:

```bash
python -m unittest discover -s tests -v
```
