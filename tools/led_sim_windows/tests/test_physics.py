import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame; pygame.init()
from ledsim import physcheck
r = physcheck.run(); print("\n".join(r)); sys.exit(0 if r[-1].startswith("ВСЕ") else 1)
