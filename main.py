#!/usr/bin/env python3

"""
Extract and decompile code.ccp into a clean Python source tree.
Saves intermediate .pyj and decompressed_output files for debugging.
"""

import argparse
import json
import logging
import zipfile
import zlib
from concurrent.futures import ProcessPoolExecutor, as_completed
from io import BytesIO, StringIO
from pathlib import Path
from typing import List, Tuple

import xdis
from uncompyle6.main import decompile as uncompyle6_decompile

logger = logging.getLogger("deccp")
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(message)s")


def _unzip_zlib_stream(blob: bytes, source_file_name: str = "unknown.pyj") -> bytes:
    """
    Locate & decompress the first valid zlib stream in `blob`.
    """

    decompressed_data = zlib.decompress(blob)
    logger.info(f"[{source_file_name}] Direct zlib decompression successful.")
    return decompressed_data


def decompile_pyj_blob(
    blob: bytes,
    source_file: str = "unknown.pyj",
) -> str:
    """
    Decompress and decompile a .pyj blob to Python source code.
    Args:
        blob: The compressed .pyj file contents.
        py_version_hint: Python version string (e.g. '2.7').
        source_file: Name for logging context.
        logger: Optional logger to use.
    Returns:
        Decompiled Python source code as a string.
    Raises:
        RuntimeError: If code object extraction fails.
    """

    data = _unzip_zlib_stream(blob, source_file)
    fp = BytesIO(data)
    logger.info(f"[{source_file}] xdis.load_module_from_file_object")

    try:
        version, ts, magic, code, is_pypy, src_size, _ = (
            xdis.load.load_module_from_file_object(fp, filename=source_file)
        )
    except Exception as e:
        raise RuntimeError(f"[{source_file}] Failed to load code object: {e}") from e

    if not code:
        raise RuntimeError(f"[{source_file}] No code object found.")

    out = StringIO()
    logger.info(f"[{source_file}] Decompiling (Python {version})")
    uncompyle6_decompile(
        code,
        bytecode_version=version,
        out=out,
        is_pypy=is_pypy,
        magic_int=magic,
        timestamp=ts,
        source_size=src_size,
    )
    return out.getvalue()


def process_pyj_member(args: Tuple[str, bytes]) -> Tuple[str, str, str]:
    """
    Decompile a single .pyj member. Returns (member_name_in_zip, decompiled_source_code, error_message).
    Only one of decompiled_source_code or error_message will be non-empty.
    """
    member_name_in_zip, raw_pyj_blob_from_zip = args
    try:
        source = decompile_pyj_blob(
            raw_pyj_blob_from_zip, source_file=member_name_in_zip
        )
        return (member_name_in_zip, source, "")
    except Exception as e:
        return (member_name_in_zip, "", str(e))


def main():
    parser = argparse.ArgumentParser(
        description="Extract & decompile code.ccp (de-ccp)."
    )
    parser.add_argument(
        "zipfile", type=Path, help="Path to code.ccp (a ZIP of .pyj blobs)"
    )
    parser.add_argument(
        "-o",
        "--out",
        type=Path,
        help="Directory in which to create client_code/ (default: same dir as ZIP)",
    )
    parser.add_argument(
        "-j",
        "--jobs",
        type=int,
        default=4,
        help="Number of parallel processes (default: 4)",
    )
    args = parser.parse_args()

    zip_path = args.zipfile.resolve()
    output_base_dir = args.out.resolve() if args.out else zip_path.parent
    client_code_dir = output_base_dir / "client_code"
    client_code_dir.mkdir(parents=True, exist_ok=True)

    work: List[Tuple[str, bytes]] = []
    with zipfile.ZipFile(zip_path, "r") as zf:
        for member_name_in_zip in zf.namelist():
            if not member_name_in_zip.endswith(".pyj"):
                continue
            out_path = (client_code_dir / member_name_in_zip).with_suffix(".py")
            if out_path.exists():
                logger.info(f"Skip: {out_path.relative_to(output_base_dir)}")
                continue
            raw_pyj_blob_from_zip = zf.read(member_name_in_zip)
            work.append((member_name_in_zip, raw_pyj_blob_from_zip))

    if not work:
        logger.info("Nothing to do.")
        return

    logger.info(f"Processing {len(work)} files with {args.jobs} workers...")
    errors = {}
    with ProcessPoolExecutor(max_workers=args.jobs) as executor:
        future_to_member = {executor.submit(process_pyj_member, w): w[0] for w in work}
        for future in as_completed(future_to_member):
            member_name_in_zip = future_to_member[future]
            out_path = (client_code_dir / member_name_in_zip).with_suffix(".py")
            try:
                member, source, error = future.result()
                if error:
                    logger.error(f"Error: {member}: {error}")
                    errors[member] = error
                else:
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    out_path.write_text(source, encoding="utf-8")
                    logger.info(f"Decompiled: {out_path.relative_to(output_base_dir)}")
            except Exception as e:
                logger.error(f"Error: {member_name_in_zip}: {e}")
                errors[member_name_in_zip] = str(e)

    if errors:
        errors_path = output_base_dir / "decompile_errors.json"
        with open(errors_path, "w", encoding="utf-8") as f:
            json.dump(errors, f, indent=2, ensure_ascii=False)
        logger.info(
            f"Wrote errors to {errors_path.relative_to(output_base_dir)} ({len(errors)} files)"
        )


if __name__ == "__main__":
    main()
