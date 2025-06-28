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
    
    system = platform.system()
    
    if system == "Windows":
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
    elif system == "Darwin":  # macOS
        # macOS build - use the spec file for proper .app bundle
        cmd = [
            "pyinstaller",
            "SchoologyConverter.spec"
        ]
    else:  # Linux
        # Linux build
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
        
        if system == "Darwin":
            # For macOS, the output is a .app bundle
            app_path = Path('dist') / 'SchoologyConverter.app'
            print(f"macOS app bundle location: {app_path}")
            
            # Set proper permissions
            print("Setting proper permissions...")
            subprocess.run(["chmod", "+x", str(app_path / "Contents" / "MacOS" / "SchoologyConverter")], check=True)
            subprocess.run(["chmod", "-R", "755", str(app_path)], check=True)
            
            # Create a zip archive for distribution
            print("Creating zip archive...")
            subprocess.run(["cd", "dist", "&&", "zip", "-r", "SchoologyConverter-macOS.zip", "SchoologyConverter.app"], shell=True, check=True)
            print(f"macOS zip archive: {Path('dist') / 'SchoologyConverter-macOS.zip'}")
        else:
            # For Windows and Linux, the output is an executable
            exe_name = "SchoologyConverter.exe" if system == "Windows" else "SchoologyConverter"
            print(f"Executable location: {Path('dist') / exe_name}")
            
    except subprocess.CalledProcessError as e:
        print(f"Build failed with error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 