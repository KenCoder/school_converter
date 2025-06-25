# Common Cartridge Format Converter

A tool to convert 1EdTech Common Cartridge (.imscc) files to DOCX format.

## Features

- Converts Common Cartridge assessments to DOCX format
- Preserves question formatting and structure
- Handles multiple choice and essay questions
- Supports images and other resources
- Processes entire cartridges or individual XML files
- **NEW**: GUI application for easy file conversion

## Installation

```bash
pip install cc-converter
```

## Usage

### GUI Application (Recommended)

For the easiest experience, use the GUI application:

```bash
python run_gui.py
```

The GUI provides:
- Drag-and-drop file selection
- Visual progress tracking
- Preview of converted files
- Easy access to converted content

### Command Line Interface

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

## Building Executables

### GUI Application Build

The project includes automated builds for the GUI application:

#### Local Build
```bash
python build_gui.py
```

#### GitHub Actions
- Automatic builds for Windows and macOS on push to main/master
- Automatic release creation when tags are pushed
- See [BUILD_INSTRUCTIONS.md](BUILD_INSTRUCTIONS.md) for details

### CLI Application Build

To create a standalone CLI executable using PyInstaller:

1. Install PyInstaller:
   ```bash
   pip install pyinstaller
   ```

2. Build the executable:
   ```bash
   pyinstaller cli.spec
   ```

3. The executable will be created in the `dist/cc_converter/` directory.

4. Run the executable:
   ```bash
   ./dist/cc_converter/cc_converter input.imscc output_directory
   ```

**Note**: The package has been configured to work with PyInstaller by using absolute imports instead of relative imports.

## Development

Run tests with:

```bash
python -m unittest discover -s tests -v
```
