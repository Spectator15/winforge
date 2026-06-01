"""WinForge — entry point"""
import sys, os

# Add project root to path so core/ui packages resolve correctly
# This is needed both for running directly and when bundled by PyInstaller
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ui.app import main

if __name__ == "__main__":
    main()
