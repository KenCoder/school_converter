# Common Cartridge Converter GUI

A user-friendly graphical interface for converting Schoology Common Cartridge files to readable documents.

## Features

- **Easy File Selection**: Browse and select folders containing .imscc files
- **Progress Tracking**: Real-time progress bar during conversion
- **Log Viewing**: View detailed conversion logs
- **Document Browsing**: Browse converted documents through a web interface
- **Word Integration**: DOCX files automatically open in Microsoft Word
- **Existing Folder Support**: Open previously converted folders
- **Template Support**: Use custom DOCX templates for consistent formatting

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