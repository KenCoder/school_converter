#!/bin/bash
# macOS Installation Helper Script for Schoology Converter

set -e

echo "Schoology Converter - macOS Installation Helper"
echo "================================================"

# Check if we're on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo "Error: This script is for macOS only."
    exit 1
fi

# Check if the app bundle exists
if [ ! -d "SchoologyConverter.app" ]; then
    echo "Error: SchoologyConverter.app not found in current directory."
    echo "Please make sure you've extracted the zip file and are running this script from the same directory."
    exit 1
fi

echo "Setting up Schoology Converter..."

# Set proper permissions
echo "Setting file permissions..."
chmod +x "SchoologyConverter.app/Contents/MacOS/SchoologyConverter"
chmod -R 755 "SchoologyConverter.app"

# Check if the app is already in Applications
if [ -d "/Applications/SchoologyConverter.app" ]; then
    echo "Removing existing installation..."
    rm -rf "/Applications/SchoologyConverter.app"
fi

# Copy to Applications
echo "Installing to Applications folder..."
cp -R "SchoologyConverter.app" "/Applications/"

# Set permissions on the installed app
chmod +x "/Applications/SchoologyConverter.app/Contents/MacOS/SchoologyConverter"
chmod -R 755 "/Applications/SchoologyConverter.app"

echo ""
echo "Installation complete!"
echo ""
echo "To run Schoology Converter:"
echo "1. Open Finder"
echo "2. Go to Applications"
echo "3. Double-click on 'Schoology Converter'"
echo ""
echo "If you see a security warning:"
echo "1. Go to System Preferences > Security & Privacy"
echo "2. Click 'Open Anyway' next to Schoology Converter"
echo "3. Or right-click the app and select 'Open'"
echo ""
echo "To run with debug mode (for troubleshooting):"
echo "open -a Terminal"
echo "/Applications/SchoologyConverter.app/Contents/MacOS/SchoologyConverter --debug"
echo ""
echo "To run without debug mode:"
echo "/Applications/SchoologyConverter.app/Contents/MacOS/SchoologyConverter --no-debug" 