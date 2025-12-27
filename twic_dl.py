#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import sys
import time
import zipfile
from pathlib import Path

import requests


def head_ok(session: requests.Session, url: str, timeout: int) -> tuple[bool, int]:
    """Check if the file exists using HEAD request. Returns (ok, status_code)."""
    try:
        r = session.head(url, allow_redirects=True, timeout=timeout)
        return (r.status_code == 200, r.status_code)
    except requests.RequestException:
        return (False, -1)


def download(session: requests.Session, url: str, dest: Path, timeout: int) -> tuple[bool, int]:
    """Download URL to destination path (streamed). Returns (ok, status_code)."""
    try:
        with session.get(url, stream=True, timeout=timeout, allow_redirects=True) as r:
            if r.status_code != 200:
                return (False, r.status_code)

            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest.with_suffix(dest.suffix + ".part")
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 256):
                    if chunk:
                        f.write(chunk)
            tmp.replace(dest)
            return (True, r.status_code)
    except requests.RequestException:
        return (False, -1)


def extract_pgn(zip_path: Path, out_dir: Path) -> list[Path]:
    """Extract only .pgn files from a zip archive into out_dir."""
    out_dir.mkdir(parents=True, exist_ok=True)
    extracted: list[Path] = []
    with zipfile.ZipFile(zip_path, "r") as z:
        for name in z.namelist():
            if name.lower().endswith(".pgn"):
                target = out_dir / Path(name).name
                with z.open(name) as src, open(target, "wb") as dst:
                    dst.write(src.read())
                extracted.append(target)
    return extracted


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download TWIC PGN zip files (twic{num}g.zip) and optionally merge PGNs."
    )
    parser.add_argument("--start", type=int, required=True, help="Starting TWIC number, e.g. 1600")
    parser.add_argument("--end", type=int, default=None, help="Ending TWIC number (if omitted: continue until 404)")
    parser.add_argument("--out", type=Path, default=Path("twic_download"), help="Output directory")
    parser.add_argument("--sleep", type=float, default=1.0, help="Delay between requests (seconds)")
    parser.add_argument("--max-misses", type=int, default=3, help="Consecutive 404 responses treated as end")
    parser.add_argument("--no-head", action="store_true", help="Do not use HEAD before GET")
    parser.add_argument("--extract", action="store_true", help="Extract PGN files from zip archives")
    parser.add_argument("--merge", type=Path, default=None, help="Output PGN file path (merge extracted PGNs)")

    # NEW: minimal progress logging knobs
    parser.add_argument("--log-every", type=int, default=10,
                        help="Print a progress line every N iterations (default: 10)")
    parser.add_argument("--timeout", type=int, default=60,
                        help="HTTP timeout in seconds for both HEAD and GET (default: 60)")

    args = parser.parse_args()

    base = "https://theweekinchess.com/zips"
    out_zip = args.out / "zips"
    out_pgn = args.out / "pgn"

    session = requests.Session()
    session.headers.update({
        "User-Agent": "twic-downloader/1.0 (+https://theweekinchess.com/twic)"
    })

    print("[INFO] TWIC downloader starting")
    print(f"[INFO] start={args.start} end={args.end} out={args.out} "
          f"sleep={args.sleep}s max_misses={args.max_misses} "
          f"extract={args.extract} merge={args.merge} no_head={args.no_head} "
          f"timeout={args.timeout}s log_every={args.log_every}")

    extracted_all: list[Path] = []
    downloaded = 0
    skipped = 0
    failed = 0

    misses = 0
    n = args.start
    iter_count = 0
    t0 = time.time()

    while True:
        if args.end is not None and n > args.end:
            break

        iter_count += 1
        if args.log_every > 0 and (iter_count == 1 or iter_count % args.log_every == 0):
            elapsed = int(time.time() - t0)
            print(f"[PROG] n={n} downloaded={downloaded} skipped={skipped} failed={failed} "
                  f"misses={misses}/{args.max_misses} elapsed={elapsed}s")

        url = f"{base}/twic{n}g.zip"
        dest = out_zip / f"twic{n}g.zip"

        # Skip download if file already exists
        if dest.exists() and dest.stat().st_size > 0:
            skipped += 1
            print(f"[SKIP] {dest.name} (already exists)")
            ok = True
        else:
            ok = False

            if not args.no_head:
                print(f"[HEAD] {n} -> checking availability")
                ok_head, code = head_ok(session, url, timeout=args.timeout)
                if not ok_head:
                    if code == 404:
                        misses += 1
                        print(f"[MISS] {n} -> 404 ({misses}/{args.max_misses})")
                    else:
                        print(f"[WARN] {n} -> HEAD status {code}, will try GET…")
                    ok = False
                else:
                    ok = True

            if ok or args.no_head:
                print(f"[GET ] {n} -> downloading {url}")
                ok_get, code_get = download(session, url, dest, timeout=args.timeout)
                if not ok_get:
                    failed += 1
                    # Try to determine whether this is the end
                    if not args.no_head:
                        _, code2 = head_ok(session, url, timeout=args.timeout)
                    else:
                        code2 = -1

                    if code2 == 404:
                        misses += 1
                        print(f"[MISS] {n} -> 404 after GET ({misses}/{args.max_misses})")
                    else:
                        print(f"[FAIL] {n} -> download failed (status={code_get})")
                    ok = False
                else:
                    downloaded += 1
                    misses = 0  # reset after success
                    size_kb = int(dest.stat().st_size / 1024) if dest.exists() else -1
                    print(f"[OK  ] {n} -> saved {dest.name} ({size_kb} KB)")
                    ok = True

        if ok and args.extract:
            try:
                extracted = extract_pgn(dest, out_pgn)
                if extracted:
                    print(f"[PGN ] {n} -> extracted {len(extracted)} file(s)")
                else:
                    print(f"[PGN ] {n} -> no .pgn found in zip?")
                extracted_all.extend(extracted)
            except zipfile.BadZipFile:
                failed += 1
                print(f"[BAD ] {n} -> corrupted ZIP: {dest.name}")

        # If --end is not provided, stop after too many misses
        if args.end is None and misses >= args.max_misses:
            print("[DONE] Reached the end of available TWIC issues.")
            break

        n += 1
        time.sleep(max(0.0, args.sleep))

    if args.merge:
        if not args.extract:
            print("[INFO] --merge requires --extract (PGN files must exist).", file=sys.stderr)
            return 2

        extracted_all = sorted(set(extracted_all), key=lambda p: p.name.lower())
        args.merge.parent.mkdir(parents=True, exist_ok=True)

        print(f"[MERGE] Merging {len(extracted_all)} PGN file(s) into {args.merge}")
        with open(args.merge, "wb") as out:
            for pgn in extracted_all:
                out.write(pgn.read_bytes())
                out.write(b"\n")
        print(f"[MERGE] Written: {args.merge}")

    elapsed = int(time.time() - t0)
    print(f"[INFO] Finished. downloaded={downloaded} skipped={skipped} failed={failed} elapsed={elapsed}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
