# Schoology Converter GUI

The Schoology Converter GUI provides a user-friendly interface for converting Schoology cartridge files to hierarchical structures with DOCX files.

## Running the GUI

### Development Mode
```bash
# Run with debug tools enabled (default for development)
python run_gui.py

# Explicitly enable debug mode
python run_gui.py --debug

# Disable debug mode
python run_gui.py --no-debug
```

### Built Executable

#### Windows
```bash
# Run built executable (debug disabled by default)
SchoologyConverter.exe

# Enable debug mode for built executable
SchoologyConverter.exe --debug

# Force disable debug mode
SchoologyConverter.exe --no-debug
```

#### macOS
```bash
# Extract the downloaded zip file
unzip SchoologyConverter-macOS.zip

# Run the app bundle (debug disabled by default)
open SchoologyConverter.app

# Or run from terminal with debug mode
./SchoologyConverter.app/Contents/MacOS/SchoologyConverter --debug

# Force disable debug mode
./SchoologyConverter.app/Contents/MacOS/SchoologyConverter --no-debug
```

**Note for macOS users**: The first time you run the app, macOS may show a security warning. To allow the app to run:
1. Go to System Preferences > Security & Privacy
2. Click "Open Anyway" next to the Schoology Converter app
3. Or right-click the app and select "Open" from the context menu

#### Linux
```bash
# Run built executable (debug disabled by default)
./SchoologyConverter

# Enable debug mode for built executable
./SchoologyConverter --debug

# Force disable debug mode
./SchoologyConverter --no-debug
```

### Environment Variable
You can also control debug mode using an environment variable:
```bash
# Enable debug mode
export CC_CONVERTER_DEBUG=true
python run_gui.py

# Disable debug mode
export CC_CONVERTER_DEBUG=false
python run_gui.py
```

## Debug Mode

Debug mode controls whether the developer tools window is opened automatically when the GUI starts. This is useful for:

- **Development**: Inspecting HTML, debugging JavaScript, and monitoring network requests
- **Troubleshooting**: When users encounter issues and need to provide detailed error information

### Default Behavior

- **Development**: Debug mode is **enabled** by default when running from source
- **Built Executable**: Debug mode is **disabled** by default for end users

### Priority Order

The debug mode is determined in this priority order:
1. `--no-debug` flag (highest priority)
2. `--debug` flag
3. `CC_CONVERTER_DEBUG` environment variable
4. Default behavior based on whether it's a built executable

## Building the GUI

To build the GUI as a standalone executable:

```bash
python build_gui.py
```

This will create platform-specific output:
- **Windows**: `dist/SchoologyConverter.exe`
- **macOS**: `dist/SchoologyConverter.app` and `dist/SchoologyConverter-macOS.zip`
- **Linux**: `dist/SchoologyConverter`

### Platform-Specific Notes

#### macOS
- Creates a proper `.app` bundle that can be double-clicked
- Includes proper file permissions and bundle metadata
- Creates a zip archive for easy distribution
- Requires macOS 10.13 or later

#### Windows
- Creates a single `.exe` file
- Includes all dependencies and resources

#### Linux
- Creates a single binary file
- May require additional dependencies depending on the target system

## Features

- Drag-and-drop file selection
- Progress tracking during conversion
- Log file viewing
- Hierarchical output structure
- DOCX file generation
- Template customization
- Cross-platform support (Windows, macOS, Linux)

## Installation

1. Install the required dependencies:
```bash
pip install -e .
```

2. Run the GUI application:
```bash
python run_gui.py
```

Or use the command line entry point:
```bash
cc-gui
```

## Usage

### Converting Files

1. **Download from Schoology**: Follow the instructions in the GUI (placeholder for now)
2. **Select Input Folder**: Click "Browse" to select the folder containing your .imscc files
3. **Select Output Folder**: Choose where to save the converted documents
4. **Optional Settings**:
   - Template DOCX File: Select a custom DOCX template for consistent formatting
5. **Start Conversion**: Click "Start Conversion" and monitor progress
6. **View Results**: Use the "View Converted Site" button to browse documents

### Opening Existing Conversions

- Click "Browse Existing Folder" to open a previously converted folder
- Navigate through the web interface to find your documents
- Click on DOCX files to open them in Microsoft Word

### Log Files

- Click "View Log File" to open the conversion log in your default text editor
- Logs include detailed information about the conversion process
- Each conversion creates a timestamped log file

## File Handling

- **DOCX Files**: Automatically open in Microsoft Word when clicked
- **HTML Files**: Open in your default web browser
- **Other Files**: Open with their default applications

## Troubleshooting

### Common Issues

1. **Conversion Fails**: Check the log file for detailed error messages
2. **Files Don't Open**: Ensure you have the appropriate applications installed (Word for DOCX files)
3. **GUI Won't Start**: Make sure all dependencies are installed correctly

### System Requirements

- Python 3.7 or higher
- Microsoft Word (for DOCX file viewing)
- Web browser (for HTML file viewing)
- Sufficient disk space for converted files

## Technical Details

The GUI is built using Pywebview, which provides a native desktop application experience using web technologies. The application:

- Runs conversions in background threads to keep the UI responsive
- Creates a hierarchical web interface for browsing converted documents
- Uses JavaScript to handle file opening with appropriate applications
- Provides detailed logging for troubleshooting
- Supports custom DOCX templates for consistent document formatting

## Command Line Alternative

If you prefer command line usage, you can also use:
```bash
cc-convert convert <input_folder> <output_folder> [options]
```

See the main README.md for command line usage details. 