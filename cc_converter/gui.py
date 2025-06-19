import webview
import os
import sys
import json
import threading
import subprocess
import webbrowser
from pathlib import Path
from typing import Dict, Any, Optional
import logging
from datetime import datetime

from cc_converter.enhanced_converter import EnhancedConverter


class ConverterAPI:
    def __init__(self):
        self.conversion_thread = None
        self.current_output_dir = None
        self.log_file_path = None
        self.progress_callback = None
        
    def select_folder(self) -> Dict[str, Any]:
        """Open folder selection dialog and return selected path."""
        try:
            result = webview.windows[0].create_file_dialog(
                webview.FOLDER_DIALOG,
                directory='',
                allow_multiple=False
            )
            if result:
                return {"success": True, "path": result[0]}
            else:
                return {"success": False, "message": "No folder selected"}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    def select_output_folder(self) -> Dict[str, Any]:
        """Open folder selection dialog for output directory."""
        try:
            result = webview.windows[0].create_file_dialog(
                webview.FOLDER_DIALOG,
                directory='',
                allow_multiple=False
            )
            if result:
                return {"success": True, "path": result[0]}
            else:
                return {"success": False, "message": "No folder selected"}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    def start_conversion(self, input_path: str, output_path: str, font_map_path: str = None, limit: int = None) -> Dict[str, Any]:
        """Start the conversion process in a background thread."""
        if self.conversion_thread and self.conversion_thread.is_alive():
            return {"success": False, "message": "Conversion already in progress"}
        
        # Setup logging
        self.log_file_path = Path(output_path) / f"conversion_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.log_file_path),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        self.current_output_dir = Path(output_path)
        
        # Start conversion in background thread
        self.conversion_thread = threading.Thread(
            target=self._run_conversion,
            args=(input_path, output_path, font_map_path, limit)
        )
        self.conversion_thread.daemon = True
        self.conversion_thread.start()
        
        return {"success": True, "message": "Conversion started"}
    
    def _run_conversion(self, input_path: str, output_path: str, font_map_path: str = None, limit: int = None):
        """Run the actual conversion process."""
        try:
            # Load font mapping if provided
            font_mapping = None
            if font_map_path and os.path.exists(font_map_path):
                with open(font_map_path, 'r') as f:
                    font_mapping = json.load(f)
            
            # Create converter and run conversion
            converter = EnhancedConverter(font_mapping)
            
            # Set up progress callback
            def progress_callback(message: str, progress: float = None):
                if self.progress_callback:
                    self.progress_callback(message, progress)
                logging.info(message)
            
            converter.set_progress_callback(progress_callback)
            
            # Run conversion
            input_files = list(Path(input_path).glob("*.imscc"))
            if not input_files:
                progress_callback("No .imscc files found in input directory")
                return
            
            for i, input_file in enumerate(input_files):
                progress_callback(f"Processing {input_file.name}...", (i / len(input_files)) * 100)
                cartridge_output = Path(output_path) / input_file.stem
                cartridge_output.mkdir(parents=True, exist_ok=True)
                converter.convert_cartridge(input_file, cartridge_output, limit)
            
            progress_callback("Conversion completed successfully!", 100)
            
        except Exception as e:
            error_msg = f"Conversion failed: {str(e)}"
            logging.error(error_msg)
            if self.progress_callback:
                self.progress_callback(error_msg, -1)
    
    def get_conversion_status(self) -> Dict[str, Any]:
        """Get the current status of the conversion process."""
        if not self.conversion_thread:
            return {"status": "idle"}
        
        if self.conversion_thread.is_alive():
            return {"status": "running"}
        else:
            return {"status": "completed"}
    
    def open_log_file(self) -> Dict[str, Any]:
        """Open the log file in the default text editor."""
        if not self.log_file_path or not self.log_file_path.exists():
            return {"success": False, "message": "No log file available"}
        
        try:
            if sys.platform == "win32":
                os.startfile(self.log_file_path)
            elif sys.platform == "darwin":
                subprocess.run(["open", str(self.log_file_path)])
            else:
                subprocess.run(["xdg-open", str(self.log_file_path)])
            return {"success": True, "message": "Log file opened"}
        except Exception as e:
            return {"success": False, "message": f"Failed to open log file: {str(e)}"}
    
    def open_converted_site(self) -> Dict[str, Any]:
        """Open the root index.html file in the default browser."""
        if not self.current_output_dir:
            return {"success": False, "message": "No converted site available"}
        
        index_path = self.current_output_dir / "index.html"
        if not index_path.exists():
            return {"success": False, "message": "index.html not found"}
        
        try:
            webbrowser.open(f"file://{index_path.absolute()}")
            return {"success": True, "message": "Site opened in browser"}
        except Exception as e:
            return {"success": False, "message": f"Failed to open site: {str(e)}"}
    
    def open_existing_folder(self) -> Dict[str, Any]:
        """Open an existing converted folder."""
        try:
            result = webview.windows[0].create_file_dialog(
                webview.FOLDER_DIALOG,
                directory='',
                allow_multiple=False
            )
            if result:
                folder_path = Path(result[0])
                index_path = folder_path / "index.html"
                if index_path.exists():
                    webbrowser.open(f"file://{index_path.absolute()}")
                    return {"success": True, "message": "Existing site opened"}
                else:
                    return {"success": False, "message": "No index.html found in selected folder"}
            else:
                return {"success": False, "message": "No folder selected"}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    def set_progress_callback(self, callback):
        """Set the progress callback function."""
        self.progress_callback = callback


def create_html_content():
    """Create the HTML content for the GUI."""
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Common Cartridge Converter</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 800px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
            font-weight: 300;
        }
        
        .header p {
            font-size: 1.1em;
            opacity: 0.9;
        }
        
        .content {
            padding: 40px;
        }
        
        .section {
            margin-bottom: 40px;
            padding: 25px;
            border: 2px solid #f0f0f0;
            border-radius: 10px;
            background: #fafafa;
        }
        
        .section h2 {
            color: #333;
            margin-bottom: 20px;
            font-size: 1.5em;
            border-bottom: 2px solid #4facfe;
            padding-bottom: 10px;
        }
        
        .instructions {
            background: #e3f2fd;
            border-left: 4px solid #2196f3;
            padding: 20px;
            margin-bottom: 30px;
            border-radius: 5px;
        }
        
        .instructions h3 {
            color: #1976d2;
            margin-bottom: 15px;
        }
        
        .instructions ol {
            margin-left: 20px;
        }
        
        .instructions li {
            margin-bottom: 8px;
            line-height: 1.5;
        }
        
        .form-group {
            margin-bottom: 20px;
        }
        
        .form-group label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: #333;
        }
        
        .input-group {
            display: flex;
            gap: 10px;
            align-items: center;
        }
        
        .input-group input[type="text"] {
            flex: 1;
            padding: 12px;
            border: 2px solid #ddd;
            border-radius: 8px;
            font-size: 14px;
            transition: border-color 0.3s;
        }
        
        .input-group input[type="text"]:focus {
            outline: none;
            border-color: #4facfe;
        }
        
        .btn {
            padding: 12px 24px;
            border: none;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
            text-decoration: none;
            display: inline-block;
            text-align: center;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            color: white;
        }
        
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(79, 172, 254, 0.4);
        }
        
        .btn-secondary {
            background: #6c757d;
            color: white;
        }
        
        .btn-secondary:hover {
            background: #5a6268;
            transform: translateY(-2px);
        }
        
        .btn-success {
            background: #28a745;
            color: white;
        }
        
        .btn-success:hover {
            background: #218838;
            transform: translateY(-2px);
        }
        
        .btn-warning {
            background: #ffc107;
            color: #212529;
        }
        
        .btn-warning:hover {
            background: #e0a800;
            transform: translateY(-2px);
        }
        
        .progress-container {
            margin-top: 20px;
            display: none;
        }
        
        .progress-bar {
            width: 100%;
            height: 20px;
            background: #e9ecef;
            border-radius: 10px;
            overflow: hidden;
            margin-bottom: 10px;
        }
        
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #4facfe 0%, #00f2fe 100%);
            width: 0%;
            transition: width 0.3s;
        }
        
        .progress-text {
            text-align: center;
            font-weight: 600;
            color: #333;
        }
        
        .status {
            padding: 15px;
            border-radius: 8px;
            margin-top: 20px;
            display: none;
        }
        
        .status.success {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        
        .status.error {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        
        .status.info {
            background: #d1ecf1;
            color: #0c5460;
            border: 1px solid #bee5eb;
        }
        
        .actions {
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
            margin-top: 20px;
        }
        
        .disabled {
            opacity: 0.6;
            cursor: not-allowed;
        }
        
        .disabled:hover {
            transform: none !important;
            box-shadow: none !important;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Common Cartridge Converter</h1>
            <p>Convert Schoology Common Cartridge files to readable documents</p>
        </div>
        
        <div class="content">
            <div class="instructions">
                <h3>How to download files from Schoology:</h3>
                <ol>
                    <li><strong>PLACEHOLDER:</strong> Instructions for downloading Common Cartridge files from Schoology will be provided here.</li>
                    <li>Once downloaded, select the folder containing your .imscc files below.</li>
                    <li>Choose an output folder for the converted documents.</li>
                    <li>Click "Start Conversion" to begin the process.</li>
                </ol>
            </div>
            
            <div class="section">
                <h2>Convert Files</h2>
                
                <div class="form-group">
                    <label for="inputPath">Input Folder (containing .imscc files):</label>
                    <div class="input-group">
                        <input type="text" id="inputPath" placeholder="Select folder containing .imscc files..." readonly>
                        <button class="btn btn-secondary" onclick="selectInputFolder()">Browse</button>
                    </div>
                </div>
                
                <div class="form-group">
                    <label for="outputPath">Output Folder:</label>
                    <div class="input-group">
                        <input type="text" id="outputPath" placeholder="Select output folder..." readonly>
                        <button class="btn btn-secondary" onclick="selectOutputFolder()">Browse</button>
                    </div>
                </div>
                
                <div class="form-group">
                    <label for="fontMapPath">Font Mapping File (optional):</label>
                    <div class="input-group">
                        <input type="text" id="fontMapPath" placeholder="Select font mapping JSON file..." readonly>
                        <button class="btn btn-secondary" onclick="selectFontMapFile()">Browse</button>
                    </div>
                </div>
                
                <div class="form-group">
                    <label for="limit">Maximum Assessments (optional):</label>
                    <input type="number" id="limit" placeholder="Leave empty for all assessments" min="1">
                </div>
                
                <button class="btn btn-primary" onclick="startConversion()" id="convertBtn">Start Conversion</button>
                
                <div class="progress-container" id="progressContainer">
                    <div class="progress-bar">
                        <div class="progress-fill" id="progressFill"></div>
                    </div>
                    <div class="progress-text" id="progressText">Preparing conversion...</div>
                </div>
                
                <div class="status" id="status"></div>
                
                <div class="actions" id="actions" style="display: none;">
                    <button class="btn btn-warning" onclick="openLogFile()">View Log File</button>
                    <button class="btn btn-success" onclick="openConvertedSite()">View Converted Site</button>
                </div>
            </div>
            
            <div class="section">
                <h2>Open Existing Conversion</h2>
                <p>Open a previously converted folder to browse the documents.</p>
                <button class="btn btn-secondary" onclick="openExistingFolder()">Browse Existing Folder</button>
            </div>
        </div>
    </div>
    
    <script>
        let conversionInProgress = false;
        
        function showStatus(message, type = 'info') {
            const status = document.getElementById('status');
            status.textContent = message;
            status.className = `status ${type}`;
            status.style.display = 'block';
        }
        
        function hideStatus() {
            document.getElementById('status').style.display = 'none';
        }
        
        async function selectInputFolder() {
            try {
                const result = await pywebview.api.select_folder();
                if (result.success) {
                    document.getElementById('inputPath').value = result.path;
                    hideStatus();
                } else {
                    showStatus(result.message, 'error');
                }
            } catch (error) {
                showStatus('Error selecting folder: ' + error.message, 'error');
            }
        }
        
        async function selectOutputFolder() {
            try {
                const result = await pywebview.api.select_output_folder();
                if (result.success) {
                    document.getElementById('outputPath').value = result.path;
                    hideStatus();
                } else {
                    showStatus(result.message, 'error');
                }
            } catch (error) {
                showStatus('Error selecting folder: ' + error.message, 'error');
            }
        }
        
        async function selectFontMapFile() {
            try {
                const result = await pywebview.api.select_file();
                if (result.success) {
                    document.getElementById('fontMapPath').value = result.path;
                    hideStatus();
                } else {
                    showStatus(result.message, 'error');
                }
            } catch (error) {
                showStatus('Error selecting file: ' + error.message, 'error');
            }
        }
        
        async function startConversion() {
            if (conversionInProgress) {
                showStatus('Conversion already in progress', 'error');
                return;
            }
            
            const inputPath = document.getElementById('inputPath').value;
            const outputPath = document.getElementById('outputPath').value;
            const fontMapPath = document.getElementById('fontMapPath').value;
            const limit = document.getElementById('limit').value;
            
            if (!inputPath || !outputPath) {
                showStatus('Please select both input and output folders', 'error');
                return;
            }
            
            try {
                const result = await pywebview.api.start_conversion(inputPath, outputPath, fontMapPath || null, limit || null);
                
                if (result.success) {
                    conversionInProgress = true;
                    document.getElementById('convertBtn').textContent = 'Converting...';
                    document.getElementById('convertBtn').classList.add('disabled');
                    document.getElementById('progressContainer').style.display = 'block';
                    document.getElementById('actions').style.display = 'none';
                    hideStatus();
                    
                    // Start polling for status
                    pollConversionStatus();
                } else {
                    showStatus(result.message, 'error');
                }
            } catch (error) {
                showStatus('Error starting conversion: ' + error.message, 'error');
            }
        }
        
        async function pollConversionStatus() {
            const interval = setInterval(async () => {
                try {
                    const status = await pywebview.api.get_conversion_status();
                    
                    if (status.status === 'completed') {
                        clearInterval(interval);
                        conversionInProgress = false;
                        document.getElementById('convertBtn').textContent = 'Start Conversion';
                        document.getElementById('convertBtn').classList.remove('disabled');
                        document.getElementById('progressContainer').style.display = 'none';
                        document.getElementById('actions').style.display = 'flex';
                        showStatus('Conversion completed successfully!', 'success');
                    }
                } catch (error) {
                    console.error('Error polling status:', error);
                }
            }, 1000);
        }
        
        async function openLogFile() {
            try {
                const result = await pywebview.api.open_log_file();
                if (result.success) {
                    showStatus(result.message, 'success');
                } else {
                    showStatus(result.message, 'error');
                }
            } catch (error) {
                showStatus('Error opening log file: ' + error.message, 'error');
            }
        }
        
        async function openConvertedSite() {
            try {
                const result = await pywebview.api.open_converted_site();
                if (result.success) {
                    showStatus(result.message, 'success');
                } else {
                    showStatus(result.message, 'error');
                }
            } catch (error) {
                showStatus('Error opening site: ' + error.message, 'error');
            }
        }
        
        async function openExistingFolder() {
            try {
                const result = await pywebview.api.open_existing_folder();
                if (result.success) {
                    showStatus(result.message, 'success');
                } else {
                    showStatus(result.message, 'error');
                }
            } catch (error) {
                showStatus('Error opening folder: ' + error.message, 'error');
            }
        }
        
        // Add file selection method to API
        pywebview.api.select_file = async function() {
            try {
                const result = await pywebview.windows[0].create_file_dialog(
                    pywebview.OPEN_DIALOG,
                    directory='',
                    allow_multiple=False,
                    file_types=('JSON files', '*.json')
                );
                if (result) {
                    return {"success": True, "path": result[0]};
                } else {
                    return {"success": False, "message": "No file selected"};
                }
            } catch (e) {
                return {"success": False, "message": str(e)};
            }
        };
    </script>
</body>
</html>
"""


def main():
    """Main function to start the GUI application."""
    api = ConverterAPI()
    
    # Create the webview window
    window = webview.create_window(
        'Common Cartridge Converter',
        html=create_html_content(),
        js_api=api,
        width=900,
        height=800,
        resizable=True,
        min_size=(800, 600)
    )
    
    # Start the application
    webview.start(debug=True)


if __name__ == '__main__':
    main() 