#!/usr/bin/env python3
"""
Launcher script for the Schoology Converter GUI.
"""

import sys
from cc_converter.gui import main

if __name__ == '__main__':
    # Pass through command line arguments
    sys.argv[0] = 'cc_converter.gui'  # Update script name for better error messages
    main() 