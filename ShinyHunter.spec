# ShinyHunter.spec
# PyInstaller build spec for Shiny Hunter — Universal Edition
#
# Run with:  pyinstaller ShinyHunter.spec
# Or use:    build_exe.bat  (does the same thing)
#
# Output:  dist/ShinyHunter.exe  (~15-20MB, under GitHub 25MB limit)
# numpy and scipy are intentionally excluded — replaced with pure Pillow.

block_cipher = None

a = Analysis(
    ['shiny_hunter.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('updater.py',      '.'),
        ('shiny_scanner.py','.'),
    ],
    hiddenimports=[
        'PIL._tkinter_finder',
        'pynput.keyboard._win32',
        'pynput.mouse._win32',
    ],
    hookspath=[],
    runtime_hooks=[],
    # Explicitly exclude heavy packages not used by the app
    excludes=[
        'numpy',
        'scipy',
        'matplotlib',
        'pandas',
        'tkinter.test',
        'unittest',
        'email',
        'http',
        'xmlrpc',
        'ftplib',
        'imaplib',
        'poplib',
        'smtplib',
    ],
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ShinyHunter',
    debug=False,
    strip=False,
    upx=True,
    console=False,     # GUI app — no console window
    # icon='assets/icon.ico',  # uncomment once you have an icon
)
