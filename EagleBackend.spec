from pathlib import Path
from PyInstaller.utils.hooks import collect_all

root = Path(SPECPATH)
datas = [(str(root / name), name) for name in ('Backgrounds', 'Fonts', 'Logos', 'Top_Layer')]
binaries = []
hiddenimports = ['gsheets', 'gspread', 'google.oauth2.service_account', 'rawpy']
for package in ('rembg', 'onnxruntime'):
    package_datas, package_binaries, package_imports = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_imports
a = Analysis([str(root / 'generate.py')], pathex=[str(root)], datas=datas,
             binaries=binaries, hiddenimports=hiddenimports,
             excludes=['tkinter', 'matplotlib', 'pytest', 'IPython'])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='EagleBackend', console=True)
coll = COLLECT(exe, a.binaries, a.datas, name='EagleBackend')
