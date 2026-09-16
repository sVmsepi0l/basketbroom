"""Read-only installed-engine names used by gameplay acceptance fixtures."""
import unreal
RESULT = {'collision_channels':[n for n in dir(unreal.CollisionChannel) if n.isupper()],
          'collision_responses':[n for n in dir(unreal.CollisionResponse) if n.isupper()],
          'play_settings_available':hasattr(unreal, 'LevelEditorPlaySettings')}
