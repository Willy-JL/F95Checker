# -*- mode: python ; coding: utf-8 -*-

block_cipher = None


a = Analysis(['F95Checker.py'],
             pathex=['C:\\WillyJL\\Python\\!Projects\\F95Checker'],
             binaries=[],
             datas=[( 'resources', 'resources' )],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=['bz2', 'decimal', 'lzma', 'multiprocessing', 'pyexpat', 'xml'],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          [],
          exclude_binaries=True,
          name='F95Checker',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=False,
          uac_admin=True,
          icon='resources/icons/icon.ico')
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               upx_exclude=[],
               name='F95Checker')
