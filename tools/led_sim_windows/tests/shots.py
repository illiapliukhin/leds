"""Scripted screenshots of every view (used on Linux/Wine to verify the build)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ledsim import selftest
selftest.run(sys.argv[1] if len(sys.argv) > 1 else 'shots')
