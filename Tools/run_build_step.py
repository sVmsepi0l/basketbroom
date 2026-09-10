"""Reload local authoring modules and run one explicitly named build stage."""
import importlib
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
for name in ('bp_graph','build_gameplay'):
    importlib.reload(importlib.import_module(name))
name=globals().get('BRIDGE_ARGS',{}).get('step')
if name not in {'build_audio','build_arena','build_hud','stage_game','build_bots','stage_bots','polish_scene'}:
    raise ValueError('Unknown Basketbroom build step')
module=importlib.reload(importlib.import_module(name))
result=module.build()
RESULT=result.get_path_name() if hasattr(result,'get_path_name') else result
