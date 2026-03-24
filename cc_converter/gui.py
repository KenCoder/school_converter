import webview
import os
import sys
import json
import threading
import argparse
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging
from datetime import datetime
import zipfile
import html

from cc_converter.hierarchy_converter import HierarchyConverter


def parse_gui_args():
    """Parse command line arguments for the GUI."""
    parser = argparse.ArgumentParser(
        description="Schoology Converter GUI",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        '--debug', 
        action='store_true',
        help='Enable debug mode with devtools'
    )
    parser.add_argument(
        '--no-debug',
        action='store_true', 
        help='Disable debug mode (overrides --debug)'
    )
    return parser.parse_args()


# Utility functions to reduce duplication
def create_error_response(message: str) -> Dict[str, Any]:
    """Create a standardized error response."""
    return {"success": False, "message": message}

def create_success_response(message: str, **kwargs) -> Dict[str, Any]:
    """Create a standardized success response."""
    response = {"success": True, "message": message}
    response.update(kwargs)
    return response

def open_file_with_default_app(file_path: Path) -> Dict[str, Any]:
    """Open a file using the operating system's default application."""
    try:
        import subprocess
        import platform
        
        # Check if file exists
        if not file_path.exists():
            return create_error_response(f"File not found: {file_path}")
        
        # Open file using OS default application
        system = platform.system()
        
        if system == "Windows":
            os.startfile(str(file_path))
        elif system == "Darwin":  # macOS
            subprocess.run(["open", str(file_path)], check=True)
        else:  # Linux
            subprocess.run(["xdg-open", str(file_path)], check=True)
        
        return create_success_response(f"Opened {file_path.name}")
        
    except Exception as e:
        return create_error_response(f"Failed to open file: {str(e)}")

def open_url_in_browser(url: str) -> Dict[str, Any]:
    """Open a URL in the user's default browser."""
    try:
        import subprocess
        import platform
        
        system = platform.system()
        
        if system == "Windows":
            os.startfile(url)
        elif system == "Darwin":  # macOS
            subprocess.run(["open", url], check=True)
        else:  # Linux
            subprocess.run(["xdg-open", url], check=True)
        
        return create_success_response(f"Opened URL in browser")
        
    except Exception as e:
        return create_error_response(f"Failed to open URL: {str(e)}")

def create_webview_window(title: str, html_content: str, js_api: Any, 
                         width: int = 1200, height: int = 800) -> Any:
    """Create a standardized webview window."""
    return webview.create_window(
        title,
        html=html_content,
        js_api=js_api,
        width=width,
        height=height,
        resizable=True,
        min_size=(800, 600)
    )


class LogCapture:
    """Capture stdout and stderr to a file while also displaying in console."""
    
    def __init__(self, log_file_path: Path):
        self.log_file_path = log_file_path
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr
        self.log_file = open(log_file_path, 'w', encoding='utf-8', buffering=1)  # Line buffered
        
    def __enter__(self):
        # Create a custom stream that writes to both file and original stream
        class DualStream:
            def __init__(self, original_stream, log_file):
                self.original_stream = original_stream
                self.log_file = log_file
                
            def write(self, text):
                self.original_stream.write(text)
                self.log_file.write(text)
                self.log_file.flush()
                
            def flush(self):
                self.original_stream.flush()
                self.log_file.flush()
                
            def __getattr__(self, attr):
                return getattr(self.original_stream, attr)
        
        sys.stdout = DualStream(self.original_stdout, self.log_file)
        sys.stderr = DualStream(self.original_stderr, self.log_file)
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout = self.original_stdout
        sys.stderr = self.original_stderr
        self.log_file.close()


class ConverterAPI:
    def __init__(self):
        """Initialize the ConverterAPI."""
        self.current_output_dir = None
        self.current_cartridge_path = None
        self.conversion_status = {"status": "idle", "message": "", "progress": 0}
        self.progress_callback = None
        self.conversion_thread = None
        self.log_file_path = None
        self.log_capture = None
        self._window = None  # Make window private to avoid JavaScript API exposure
        
        # Conversion results tracking
        self.last_conversion_summary = None
        
        # Load saved paths
        self.config_file = Path.home() / '.cc_converter_config.json'
        self.saved_paths = self._load_saved_paths()
        
    def _load_saved_paths(self) -> Dict[str, str]:
        """Load saved paths from config file."""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Warning: Could not load saved paths: {e}")
        return {}
    
    def _save_paths(self):
        """Save current paths to config file."""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.saved_paths, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save paths: {e}")
    
    def get_saved_paths(self) -> Dict[str, Any]:
        """Get saved paths for the frontend."""
        return {
            "success": True,
            "cartridge_path": self.saved_paths.get('cartridge_path', '')
        }
        
    def select_cartridge_file(self) -> Dict[str, Any]:
        """Open file selection dialog for cartridge file."""
        try:
            # Use last cartridge path's directory as default if available
            default_dir = ''
            if 'cartridge_path' in self.saved_paths:
                cartridge_path = Path(self.saved_paths['cartridge_path'])
                if cartridge_path.exists():
                    default_dir = str(cartridge_path.parent)
            
            result = webview.windows[0].create_file_dialog(
                webview.OPEN_DIALOG,
                directory=default_dir,
                allow_multiple=False,
                file_types=('IMS Common Cartridge (*.imscc)',)
            )
            if result:
                selected_path = result[0]
                # Save the selected path
                self.saved_paths['cartridge_path'] = selected_path
                self._save_paths()
                
                # Calculate default output path
                cartridge = Path(selected_path)
                default_output = cartridge.parent / cartridge.stem
                
                return create_success_response("Cartridge file selected", 
                                             path=selected_path,
                                             default_output=str(default_output))
            else:
                return create_error_response("No file selected")
        except Exception as e:
            return create_error_response(str(e))
    
    
    def start_conversion(self, cartridge_path: str) -> Dict[str, Any]:
        """Start the conversion process in a background thread."""
        if self.conversion_thread and self.conversion_thread.is_alive():
            return create_error_response("Conversion already in progress")
        
        # Clear previous conversion summary
        self.last_conversion_summary = None
        
        # Calculate output directory from cartridge path
        cartridge = Path(cartridge_path)
        output_path = cartridge.parent / cartridge.stem
        
        # Setup logging with full stdout/stderr capture
        output_path.mkdir(parents=True, exist_ok=True)
        self.log_file_path = output_path / f"conversion_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        
        # Create log capture context manager
        self.log_capture = LogCapture(self.log_file_path)
        
        # Setup basic logging configuration
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.log_file_path),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        self.current_output_dir = output_path
        self.current_cartridge_path = cartridge
        
        # Set up progress callback to update the webview
        def progress_callback(message: str, progress: float = None):
            try:
                # Update the webview's progress bar
                if hasattr(self, '_window') and self._window:
                    # Escape single quotes for JavaScript
                    escaped_message = message.replace("'", "\\'")
                    progress_value = 'null' if progress is None else str(progress)
                    self._window.evaluate_js(f"""
                        updateProgress('{escaped_message}', {progress_value});
                    """)
            except Exception as e:
                print(f"Error updating progress: {e}")
        
        self.progress_callback = progress_callback
        
        # Start conversion in background thread
        self.conversion_thread = threading.Thread(
            target=self._run_conversion,
            args=(cartridge_path, str(output_path))
        )
        self.conversion_thread.daemon = True
        self.conversion_thread.start()
        
        return create_success_response("Conversion started", output_dir=str(output_path))
    
    def _run_conversion(self, cartridge_path: str, output_path: str):
        """Run the actual conversion process."""
        try:
            # Use log capture to capture all stdout/stderr
            with self.log_capture:
                print(f"=== Conversion started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
                print(f"Cartridge: {cartridge_path}")
                print(f"Output directory: {output_path}")
                print("=" * 60)
                
                # Create converter for this cartridge (uses built-in template)
                converter = HierarchyConverter()
                
                # Set the progress callback for the converter
                converter.set_progress_callback(self.progress_callback)
                
                # Convert the cartridge directly into the output directory
                input_file = Path(cartridge_path)
                self.progress_callback(f"Converting {input_file.name}...", 0)
                
                # Convert the cartridge
                converter.convert_cartridge_with_hierarchy(input_file, Path(output_path))
                
                # Get conversion summary
                summary = converter.get_conversion_summary()
                
                # Provide final summary to user
                if summary['success']:
                    if summary['total_warnings'] > 0:
                        final_message = f"Conversion completed with {summary['total_warnings']} warnings across {summary['files_with_warnings']} files!"
                        self.progress_callback(final_message, 100)
                    else:
                        final_message = "Conversion completed successfully!"
                        self.progress_callback(final_message, 100)
                else:
                    error_count = summary['total_errors']
                    warning_count = summary['total_warnings']
                    files_with_errors = summary['files_with_errors']
                    
                    error_message = f"Conversion completed with {error_count} errors affecting {files_with_errors} files"
                    if warning_count > 0:
                        error_message += f" and {warning_count} warnings"
                    if summary['hierarchy_creation_error']:
                        error_message += " (hierarchy creation error)"
                    error_message += "!"
                    self.progress_callback(error_message, -1)
                
                print(f"\n=== Conversion completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
                print(f"Total errors: {summary['total_errors']}")
                print(f"Total warnings: {summary['total_warnings']}")
                print(f"Files with errors: {summary['files_with_errors']}")
                print(f"Files with warnings: {summary['files_with_warnings']}")
                if summary['hierarchy_creation_error']:
                    print(f"Hierarchy creation error: {summary['hierarchy_creation_error']}")
                
                # Store the conversion summary for UI access
                self.last_conversion_summary = {
                    'total_errors': summary['total_errors'],
                    'total_warnings': summary['total_warnings'],
                    'total_files_with_errors': summary['files_with_errors'],
                    'total_files_with_warnings': summary['files_with_warnings'],
                    'all_errors': summary['errors'],
                    'all_warnings': summary['warnings'],
                    'hierarchy_creation_error': summary['hierarchy_creation_error'],
                    'success': summary['success'],
                    'timestamp': datetime.now().isoformat()
                }
                
        except Exception as e:
            error_msg = f"Conversion failed: {str(e)}"
            print(f"ERROR: {error_msg}")
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
        """Open the log file using the default .log viewer on the user's computer."""
        if not self.log_file_path or not self.log_file_path.exists():
            return create_error_response("No log file available")
        
        try:
            return open_file_with_default_app(self.log_file_path)
        except Exception as e:
            return create_error_response(f"Failed to open log file: {str(e)}")
    
    def open_output_folder(self) -> Dict[str, Any]:
        """Open the output folder in the system file explorer."""
        if not self.current_output_dir:
            return create_error_response("No output folder available")
        
        try:
            import subprocess
            import platform
            
            system = platform.system()
            
            if system == "Windows":
                os.startfile(str(self.current_output_dir))
            elif system == "Darwin":  # macOS
                subprocess.run(["open", str(self.current_output_dir)], check=True)
            else:  # Linux
                subprocess.run(["xdg-open", str(self.current_output_dir)], check=True)
            
            return create_success_response(f"Opened {self.current_output_dir}")
            
        except Exception as e:
            return create_error_response(f"Failed to open folder: {str(e)}")
    
    def set_progress_callback(self, callback):
        """Set the progress callback function."""
        self.progress_callback = callback
    
    def save_current_paths(self, cartridge_path: str = None) -> Dict[str, Any]:
        """Save current paths to config file."""
        try:
            if cartridge_path is not None:
                self.saved_paths['cartridge_path'] = cartridge_path
            
            self._save_paths()
            return create_success_response("Paths saved")
        except Exception as e:
            return create_error_response(str(e))
    
    def cleanup(self):
        """Clean up resources when the application is closing."""
        pass
    
    def get_conversion_summary(self) -> Dict[str, Any]:
        """Get the summary of the last conversion run."""
        if self.last_conversion_summary is None:
            return create_error_response("No conversion summary available")
        
        return {
            "success": True,
            "summary": self.last_conversion_summary
        }
    
    def open_url_in_browser(self, url: str) -> Dict[str, Any]:
        """Open a URL in the user's default browser."""
        return open_url_in_browser(url)


def create_html_content():
    """Create the HTML content for the GUI."""
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Schoology Converter</title>
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
            max-width: 1200px;
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
        
        .main-sections {
            display: flex;
            gap: 30px;
            margin-top: 30px;
        }
        
        .section {
            flex: 1;
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
            <h1>Schoology Converter</h1>
            <p>Convert Schoology files to word documents</p>
        </div>
        
        <div class="content">
            <div class="instructions">
                <h3>See this <button class="btn btn-primary" onclick="openGoogleDoc()" style="background: none; border: none; color: #1976d2; text-decoration: underline; cursor: pointer; font-size: inherit; padding: 0; margin: 0;">Google Doc</button> for instructions</h3>
            </div>
            
            <div class="main-sections">
                <div class="section">
                    <h2>File Selection</h2>
                    
                    <div class="form-group">
                        <label for="cartridgePath">Cartridge File (.imscc):</label>
                        <div class="input-group">
                            <input type="text" id="cartridgePath" placeholder="Select cartridge file..." readonly>
                            <button class="btn btn-secondary" onclick="selectCartridgeFile()">Browse</button>
                        </div>
                        <div style="margin-top: 8px; color: #666; font-size: 13px;">
                            Output will be created in a folder next to the cartridge with the same name
                        </div>
                    </div>
                    
                </div>
                
                <div class="section">
                    <h2>Conversion Controls</h2>
                    
                    <button class="btn btn-primary" onclick="startConversion()" id="convertBtn">Start Conversion</button>
                    
                    <div class="progress-container" id="progressContainer">
                        <div class="progress-bar">
                            <div class="progress-fill" id="progressFill"></div>
                        </div>
                        <div class="progress-text" id="progressText">Preparing conversion...</div>
                    </div>
                    
                    <div class="status" id="status"></div>
                    
                    <div class="actions" id="actions" style="display: none;">
                        <button class="btn btn-warning" onclick="viewLogFile()">View Log File</button>
                        <button class="btn btn-success" onclick="openOutputFolder()">Open Output Folder</button>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        let conversionInProgress = false;
        let saveTimeout = null;
        
        // Initialize the application
        function initializeApp() {
            loadSavedPaths();
            setupEventListeners();
        }
        
        // Setup event listeners for input fields
        function setupEventListeners() {
            const cartridgePath = document.getElementById('cartridgePath');
            
            // Add event listeners to save paths when user types
            cartridgePath.addEventListener('input', () => debouncedSavePaths());
        }
        
        // Debounced function to save paths
        function debouncedSavePaths() {
            if (saveTimeout) {
                clearTimeout(saveTimeout);
            }
            saveTimeout = setTimeout(saveCurrentPaths, 500);
        }
        
        // Save current paths
        async function saveCurrentPaths() {
            try {
                const cartridgePath = document.getElementById('cartridgePath').value;
                
                await pywebview.api.save_current_paths(cartridgePath);
            } catch (error) {
                console.error('Error saving paths:', error);
            }
        }
        
        // Load saved paths when page loads
        async function loadSavedPaths() {
            let retries = 0;
            const maxRetries = 10;
            
            async function tryLoadPaths() {
                try {
                    const result = await pywebview.api.get_saved_paths();
                    if (result.success) {
                        if (result.cartridge_path) {
                            document.getElementById('cartridgePath').value = result.cartridge_path;
                        }
                        console.log('Saved paths loaded successfully');
                    }
                } catch (error) {
                    console.error('Error loading saved paths:', error);
                    retries++;
                    if (retries < maxRetries) {
                        // Retry after a short delay
                        setTimeout(tryLoadPaths, 200);
                    }
                }
            }
            
            // Start trying to load paths
            tryLoadPaths();
        }
        
        // Initialize when the page is ready and API is available
        if (typeof pywebview !== 'undefined' && pywebview.api) {
            initializeApp();
        } else {
            // Wait for pywebview to be available
            document.addEventListener('DOMContentLoaded', () => {
                // Try to initialize immediately
                if (typeof pywebview !== 'undefined' && pywebview.api) {
                    initializeApp();
                } else {
                    // If not available, wait a bit and try again
                    setTimeout(() => {
                        if (typeof pywebview !== 'undefined' && pywebview.api) {
                            initializeApp();
                        } else {
                            // Final fallback - try to initialize anyway
                            initializeApp();
                        }
                    }, 100);
                }
            });
        }
        
        function showStatus(message, type = 'info') {
            const status = document.getElementById('status');
            status.textContent = message;
            status.className = `status ${type}`;
            status.style.display = 'block';
        }
        
        function hideStatus() {
            document.getElementById('status').style.display = 'none';
        }
        
        async function selectCartridgeFile() {
            try {
                const result = await pywebview.api.select_cartridge_file();
                if (result.success) {
                    document.getElementById('cartridgePath').value = result.path;
                    // Save the path immediately
                    await saveCurrentPaths();
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
            
            const cartridgePath = document.getElementById('cartridgePath').value;
            
            if (!cartridgePath) {
                showStatus('Please select a cartridge file', 'error');
                return;
            }
            
            try {
                const result = await pywebview.api.start_conversion(cartridgePath);
                
                if (result.success) {
                    conversionInProgress = true;
                    document.getElementById('convertBtn').textContent = 'Converting...';
                    document.getElementById('convertBtn').classList.add('disabled');
                    document.getElementById('progressContainer').style.display = 'block';
                    
                    // Initialize progress bar
                    updateProgress('Preparing conversion...', 0);
                    
                    // Show the log file button immediately when conversion starts
                    const actionsDiv = document.getElementById('actions');
                    actionsDiv.innerHTML = '<button class="btn btn-warning" onclick="viewLogFile()">View Log File</button>';
                    actionsDiv.style.display = 'flex';
                    
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
                        
                        // Reset progress bar
                        updateProgress('Conversion completed!', 100);
                        
                        // Add the "Open Output Folder" button when conversion completes
                        const actionsDiv = document.getElementById('actions');
                        actionsDiv.innerHTML = '<button class="btn btn-warning" onclick="viewLogFile()">View Log File</button><button class="btn btn-success" onclick="openOutputFolder()">Open Output Folder</button>';
                        
                        showStatus('Conversion completed successfully!', 'success');
                    }
                } catch (error) {
                    console.error('Error polling status:', error);
                }
            }, 1000);
        }
        
        async function viewLogFile() {
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
        
        async function openOutputFolder() {
            try {
                const result = await pywebview.api.open_output_folder();
                if (result.success) {
                    showStatus(result.message, 'success');
                } else {
                    showStatus(result.message, 'error');
                }
            } catch (error) {
                showStatus('Error opening folder: ' + error.message, 'error');
            }
        }
        
        // Function to update the progress bar
        function updateProgress(message, progress) {
            const progressContainer = document.getElementById('progressContainer');
            const progressFill = document.getElementById('progressFill');
            const progressText = document.getElementById('progressText');
            
            // Show the progress container if it's hidden
            progressContainer.style.display = 'block';
            
            // Update the progress text
            progressText.textContent = message;
            
            // Update the progress bar fill
            if (progress !== null && progress !== undefined) {
                const percentage = Math.max(0, Math.min(100, progress));
                progressFill.style.width = percentage + '%';
            }
        }
        
        async function openGoogleDoc() {
            try {
                const url = 'https://docs.google.com/document/d/11uTui0vwrKt9avcPnxDyWZezZm2Swo7jLBLG1vaySXE/edit';
                const result = await pywebview.api.open_url_in_browser(url);
                if (result.success) {
                    showStatus(result.message, 'success');
                } else {
                    showStatus(result.message, 'error');
                }
            } catch (error) {
                showStatus('Error opening Google Doc: ' + error.message, 'error');
            }
        }
    </script>
</body>
</html>
"""


def main():
    """Main function to start the GUI application."""
    # Parse command line arguments
    args = parse_gui_args()
    
    # Determine debug mode
    debug_mode = False
    
    # Check if running as built executable (PyInstaller)
    is_built_executable = getattr(sys, 'frozen', False)
    
    # Priority order: --no-debug > --debug > environment variable > default
    if args.no_debug:
        debug_mode = False
    elif args.debug:
        debug_mode = True
    elif os.environ.get('CC_CONVERTER_DEBUG', '').lower() in ('true', '1', 'yes'):
        debug_mode = True
    else:
        # Default: enable debug for development, disable for built executables
        debug_mode = not is_built_executable
    
    api = ConverterAPI()
    
    # Create the webview window
    window = webview.create_window(
        'Schoology Converter',
        html=create_html_content(),
        js_api=api,
        width=1200,
        height=1050,
        resizable=True,
        min_size=(1000, 900)
    )
    
    # Store the window reference in the API for progress updates
    api._window = window
    
    try:
        # Start the application with determined debug mode
        webview.start(debug=debug_mode)
    finally:
        # Clean up resources when the application closes
        api.cleanup()


if __name__ == '__main__':
    main() 