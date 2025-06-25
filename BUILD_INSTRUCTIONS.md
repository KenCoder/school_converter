# Building the Schoology Converter GUI

This document explains how to build the GUI application for distribution.

## Prerequisites

- Python 3.7 or higher
- pip
- PyInstaller (will be installed automatically)

## Local Build

### Quick Build
Run the build script:
```bash
python build_gui.py
```

### Manual Build
1. Install dependencies:
   ```bash
   pip install -e .
   pip install pyinstaller
   ```

2. Build using PyInstaller:
   ```bash
   pyinstaller SchoologyConverter.spec
   ```

The executable will be created in the `dist/` directory.

## GitHub Actions Build

The project includes GitHub Actions workflows that automatically build the application for Windows and macOS when:

- Code is pushed to `main` or `master` branch
- A tag starting with `v` is pushed (creates a release)

### Workflow Details

1. **Windows Build**: Creates `SchoologyConverter.exe`
2. **macOS Build**: Creates `SchoologyConverter` (executable)
3. **Release Creation**: When a tag is pushed, automatically creates a GitHub release with both executables

### Triggering a Release

To create a new release:

1. Create and push a tag:
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

2. The workflow will automatically:
   - Build both Windows and macOS versions
   - Create a GitHub release
   - Upload the executables as release assets

## Build Configuration

### PyInstaller Spec File

The `SchoologyConverter.spec` file contains the build configuration:

- **Entry point**: `run_gui.py`
- **Output name**: `SchoologyConverter`
- **Window mode**: GUI application (no console)
- **Single file**: All dependencies bundled into one executable
- **Data files**: Includes template files and HTML templates

### Included Files

The build includes:
- `cc_converter/template.docx` - Word template
- `cc_converter/templates/` - HTML templates
- `cc_converter/file_handler.html` - File handler interface

## Troubleshooting

### Common Issues

1. **Missing dependencies**: Ensure all requirements are installed
2. **File not found errors**: Check that data files are in the correct locations
3. **Import errors**: Verify that all modules are properly imported in the spec file

### Debug Build

To create a debug build with console output:
```bash
pyinstaller --onefile --name "SchoologyConverter" run_gui.py
```

### Testing the Build

After building, test the executable:
1. Navigate to the `dist/` directory
2. Run the executable
3. Verify that the GUI opens and functions correctly

## Distribution

### Windows
- The `.exe` file can be distributed directly
- No additional dependencies required

### macOS
- The executable can be distributed directly
- Users may need to allow execution in Security & Privacy settings
- Consider creating a `.dmg` file for easier distribution

### Code Signing

For production releases, consider code signing:
- **Windows**: Use a code signing certificate
- **macOS**: Use Apple Developer certificate for notarization 