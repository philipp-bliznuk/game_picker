import sys

from cx_Freeze import setup, Executable


base = None
if sys.platform == 'win32':
    base = 'Win32GUI'


executables = [Executable('game_picker.py', base=base, targetName='game_picker.exe')]
packages = ['asyncio', 'aiohttp']
options = {
    'build_exe': {
        'packages': packages,
    },

}

setup_options = {
    'name': 'Steam game picker',
    'options': options,
    'version': '0.0.1',
    'description': 'New twist in game-choosing world.',
    'executables': executables,
}

setup(**setup_options)
