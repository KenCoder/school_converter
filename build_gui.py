#!/usr/bin/env python3
"""
Build script for the Schoology Converter GUI application.
This script can be used to build the application locally using PyInstaller.
"""

import os
import sys
import subprocess
import platform
from pathlib import Path

def main():
    """Build the GUI application using PyInstaller."""
    
    # Check if PyInstaller is installed
    try:
        import PyInstaller
        print(f"PyInstaller version: {PyInstaller.__version__}")
    except ImportError:
        print("PyInstaller not found. Installing...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
    
    # Install project dependencies
    print("Installing project dependencies...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-e", "."], check=True)
    
    # Build the application
    print("Building GUI application...")
    
    if platform.system() == "Windows":
        # Windows build
        cmd = [
            "pyinstaller",
            "--onefile",
            "--windowed",
            "--name", "SchoologyConverter",
            "--add-data", "cc_converter/template.docx;cc_converter",
            "--add-data", "cc_converter/templates;cc_converter/templates",
            "--add-data", "cc_converter/file_handler.html;cc_converter",
            "run_gui.py"
        ]
    else:
        # macOS/Linux build
        cmd = [
            "pyinstaller",
            "--onefile",
            "--windowed",
            "--name", "SchoologyConverter",
            "--add-data", "cc_converter/template.docx:cc_converter",
            "--add-data", "cc_converter/templates:cc_converter/templates",
            "--add-data", "cc_converter/file_handler.html:cc_converter",
            "run_gui.py"
        ]
    
    try:
        subprocess.run(cmd, check=True)
        print("Build completed successfully!")
        print(f"Executable location: {Path('dist') / 'SchoologyConverter'}")
    except subprocess.CalledProcessError as e:
        print(f"Build failed with error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 