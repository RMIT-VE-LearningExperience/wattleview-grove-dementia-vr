import json

import unreal


saved = unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
world = unreal.get_editor_subsystem(
    unreal.UnrealEditorSubsystem
).get_editor_world()
print("CODEX_EDITOR_SHUTDOWN=" + json.dumps({"saved": bool(saved)}))
unreal.SystemLibrary.execute_console_command(world, "QUIT_EDITOR")
