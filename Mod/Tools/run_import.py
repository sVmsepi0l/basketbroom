"""creator kit python commandlet entry point for the checked source importer."""
from pathlib import path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import import_sources
import_sources.build()
