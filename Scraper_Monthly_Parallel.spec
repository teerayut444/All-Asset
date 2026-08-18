# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['Monthly all new/run_parallel_monthly.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['pandas', 'requests', 'bs4', 'openpyxl', 'pyarrow', 'scrape_baania_monthly', 'scrape_bam_monthly', 'scrape_ddproperty_monthly', 'scrape_sam_monthly', 'scrape_taladnudbaan_monthly', 'scrape_zmyhome_monthly', 'scrape_chayo555_monthly', 'scrape_nayoo_monthly', 'merge_csv_monthly'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Scraper_Monthly_Parallel',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
