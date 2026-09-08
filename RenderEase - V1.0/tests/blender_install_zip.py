"""Install the actual ZIP in an isolated Blender profile; no renders."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parents[1]
blender = sys.argv[1] if len(sys.argv) > 1 else r'C:\Program Files\Blender Foundation\Blender 4.3\blender.exe'
with tempfile.TemporaryDirectory(prefix='renderease-install-') as directory:
    profile = Path(directory)
    environment = os.environ.copy()
    for variable, folder in [('BLENDER_USER_SCRIPTS', 'scripts'),
                             ('BLENDER_USER_CONFIG', 'config'),
                             ('BLENDER_USER_EXTENSIONS', 'extensions')]:
        target = profile / folder
        target.mkdir()
        environment[variable] = str(target)
    script = profile / 'install_test.py'
    script.write_text('''import bpy
import addon_utils
from pathlib import Path
archive = ARCHIVE
result = bpy.ops.preferences.addon_install(filepath=archive, overwrite=True)
assert result == {'FINISHED'}, result
bpy.utils.refresh_script_paths()
addon_utils.modules_refresh()
result = bpy.ops.preferences.addon_enable(module='renderease')
assert result == {'FINISHED'}, result
import renderease
assert Path(renderease.__file__).is_relative_to(Path(PROFILE))
assert renderease._registered
from renderease import scheduler
assert scheduler.recovery_pending
scheduler.tick()
assert not scheduler.recovery_pending
print('ZIP INSTALL AND ENABLE OK:', renderease.__file__)
bpy.ops.preferences.addon_disable(module='renderease')
print('DISABLE OK; no renders performed')
'''.replace('ARCHIVE', repr(str(root / 'dist' / 'renderease.zip')))
       .replace('PROFILE', repr(str(profile))), encoding='utf-8')
    result = subprocess.run([blender, '--background', '--factory-startup',
                             '--python-exit-code', '1', '--python', str(script)],
                            cwd=directory, env=environment, capture_output=True, text=True)
    print(result.stdout)
    print(result.stderr)
    sys.exit(result.returncode)
