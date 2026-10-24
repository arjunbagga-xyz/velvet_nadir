"""
Payload Builder (Sprint 24)

Compiles the Velvet core into a standalone executable ZIP archive (.pyz)
using Python's zipapp module. This payload can be distributed over the Zenoh
mesh for seeding new devices.
"""

import sys
import zipapp
from pathlib import Path
from loguru import logger

def build_payload(source_dir: str = "velvet", target_file: str = "velvet.pyz", main_module: str = "velvet.main:main"):
    """
    Build the standalone .pyz payload.
    """
    src_path = Path(source_dir)
    if not src_path.exists() or not src_path.is_dir():
        logger.error(f"[PayloadBuilder] Source directory {source_dir} not found.")
        return False
        
    out_path = Path(target_file)
    logger.info(f"[PayloadBuilder] Building payload from {src_path} -> {out_path}...")
    
    try:
        zipapp.create_archive(
            source=src_path,
            target=out_path,
            interpreter="/usr/bin/env python3",
            main=main_module,
            compressed=True
        )
        logger.info(f"[PayloadBuilder] Successfully built {out_path} ({out_path.stat().st_size / 1024 / 1024:.2f} MB)")
        return True
    except Exception as e:
        logger.error(f"[PayloadBuilder] Failed to build payload: {e}")
        return False

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Build velvet.pyz payload")
    parser.add_argument("--source", default="velvet", help="Source directory (default: velvet)")
    parser.add_argument("--target", default="velvet.pyz", help="Target output file (default: velvet.pyz)")
    parser.add_argument("--main", default="velvet.main:main", help="Main module entry point")
    
    args = parser.parse_args()
    success = build_payload(args.source, args.target, args.main)
    sys.exit(0 if success else 1)
