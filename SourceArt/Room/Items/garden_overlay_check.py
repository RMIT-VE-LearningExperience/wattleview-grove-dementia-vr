"""Overlay-inclusive room assembly check (garden group helper, read only on placement.json).

Runs Tools/assemble_room.py unchanged except that memory-scene overlay pieces are NOT skipped, so the
tomato stakes, basil pots, hose and fig are tested against the room and the props they appear with.
  blender -b --factory-startup --python garden_overlay_check.py -- [--render] --out <dir>
"""
import os
import sys

TOOL = r"D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Tools\assemble_room.py"
src = open(TOOL, encoding="utf-8").read()
old = 'SKIP_KINDS = {"overlay", "sky"}'
assert old in src, "assemble_room.py changed: SKIP_KINDS line not found"
src = src.replace(old, 'SKIP_KINDS = {"sky"}')
exec(compile(src, TOOL, "exec"), {"__name__": "__main__", "__file__": TOOL})
