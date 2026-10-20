#!/usr/bin/env python3
"""Parse the JSON in the LLM output files (after the first ``` if there is one) and
add one CSV row per frequency band, in the satellite database format.

Library use:   from satellite_pipeline import merge
CLI use:
  python -m satellite_pipeline.insert database.csv out/ --backup
  python -m satellite_pipeline.insert database.csv out/file.txt --source FCC --plain-bw
"""
import argparse
import csv
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

FENCE = "```"
NONE = "None"
C_ID, C_NAME, C_FREQ, C_BW = "ID", "Name", "Frequency [MHz]", "Bandwidth [kHz]/Baud"
C_STATUS, C_DESC, C_SRC, C_ORBIT = "Status", "Description", "Source", "Orbit"
DEFAULT_COLS = ["", C_ID, C_NAME, C_FREQ, C_BW, C_STATUS, C_DESC, C_SRC, C_ORBIT]
INVALID = {"", "none", "null", "n/a", "na", "nan", "unknown", "-", "--",
           "not specified", "not available", "unspecified", "undefined"}
UNIT = {"hz": 1e-6, "khz": 1e-3, "mhz": 1.0, "ghz": 1e3}   # to MHz
FREQ_KEYS = ("frequency_ranges", "all_frequencies")        # gemma_workflow writes the first


def norm(v):
    return re.sub(r"\s+", " ", str(v if v is not None else "")).strip().casefold()


def clean(v):
    """Return a trimmed string, or 'None' for empty/placeholder values."""
    return NONE if norm(v) in INVALID else str(v).strip()


def num(s):
    m = re.match(r"\s*(\d+(?:\.\d+)?)", str(s or ""))
    return round(float(m.group(1)), 4) if m else None


def extract_json(text):
    start = text.find(FENCE)
    pos = 0
    if start != -1:
        pos = start + len(FENCE)
        nl = text.find("\n", pos)
        pos = nl + 1 if nl != -1 else pos          # skip a "json" tag
    brace = min((i for i in (text.find("{", pos), text.find("[", pos)) if i != -1),
                default=-1)
    if brace == -1:
        raise ValueError("no JSON found after the ``` marker")
    data, _ = json.JSONDecoder().raw_decode(text[brace:])
    return [d for d in (data if isinstance(data, list) else [data]) if isinstance(d, dict)]


def parse_band(s):
    """'5925 6425' -> (center_mhz, bandwidth_khz). One number -> (value, None)."""
    s = str(s)
    nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", s)]
    m = re.search(r"(ghz|mhz|khz|hz)", s.lower())
    nums = [n * (UNIT[m.group(1)] if m else 1.0) for n in nums]
    if len(nums) >= 2:
        lo, hi = sorted(nums[:2])
        return round((lo + hi) / 2, 4), (round((hi - lo) * 1000, 4) or None)
    if len(nums) == 1:
        return round(nums[0], 4), None
    return None


def collect_files(inputs):
    files = []
    for item in inputs:
        p = Path(item)
        if p.is_dir():
            files += sorted(p.glob("*.txt"))
        elif p.is_file():
            files.append(p)
        else:
            print(f"[WARN] not found: {item}", file=sys.stderr)
    return files


def _frequencies(rec):
    for key in FREQ_KEYS:
        freqs = rec.get(key)
        if freqs:
            return [freqs] if isinstance(freqs, str) else list(freqs)
    return []


def merge_into_csv(csv_file, inputs, company=None, plain_bw=False, create=True, backup=True):
    """Merge LLM output files into the CSV, one row per frequency band.

    company  - fixed value for the Source column instead of the one in the JSON
    plain_bw - write bandwidth as a bare number without ' kHz'
    create   - False: only fill gaps in existing rows, never add new ones
    backup   - copy the CSV to <csv>.bak before overwriting it

    Returns {"added": n, "filled": n, "skipped": n, "failed": n}.
    """
    path = Path(csv_file)
    if path.exists():
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            fields = list(reader.fieldnames or DEFAULT_COLS)
            rows = list(reader)
    else:
        fields, rows = list(DEFAULT_COLS), []

    index = {(norm(r.get(C_NAME)), num(r.get(C_FREQ)), num(r.get(C_BW))): i
             for i, r in enumerate(rows)}
    added = filled = skipped = failed = 0

    for fp in collect_files(inputs):
        try:
            records = extract_json(fp.read_text(encoding="utf-8", errors="replace"))
            if not records:
                raise ValueError("no JSON object found")
        except (ValueError, json.JSONDecodeError) as e:
            print(f"[FAIL] {fp.name}: {e}", file=sys.stderr)
            failed += 1
            continue

        for rec in records:
            name = clean(rec.get("satellite_name"))
            if name == NONE:
                print(f"[SKIP] {fp.name}: invalid satellite_name", file=sys.stderr)
                skipped += 1
                continue

            bands = [b for b in (parse_band(x) for x in _frequencies(rec)) if b] or [(None, None)]

            for center, bw in bands:
                row = {
                    C_ID: NONE, C_NAME: name,
                    C_FREQ: repr(center) if center is not None else NONE,
                    C_BW: NONE if bw is None else (repr(bw) if plain_bw else f"{bw!r} kHz"),
                    C_STATUS: clean(rec.get("active_or_inactive")),
                    C_DESC: NONE,
                    C_SRC: company or clean(rec.get("source_or_company_origin")),
                    C_ORBIT: clean(rec.get("orbit_type")),
                }
                key = (norm(name), center, bw)
                i = index.get(key)
                if i is None:
                    if not create:
                        skipped += 1
                        continue
                    rows.append(row)
                    index[key] = len(rows) - 1
                    added += 1
                    print(f"[NEW ] {name} | {row[C_FREQ]} MHz | {row[C_BW]}")
                else:                              # same band exists: only fill gaps
                    for col in (C_STATUS, C_SRC, C_ORBIT):
                        if norm(rows[i].get(col)) in INVALID and row[col] != NONE:
                            rows[i][col] = row[col]
                            filled += 1

    if backup and path.exists():
        shutil.copy2(path, str(path) + ".bak")
    for n, r in enumerate(rows):
        if "" in fields:
            r[""] = str(n)                          # renumber the unnamed index column
    fd, tmp = tempfile.mkstemp(dir=path.resolve().parent, suffix=".tmp")
    with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, restval=NONE)
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, path)
    print(f"\nDone: {added} rows added, {filled} cells filled, {skipped} skipped, {failed} failed")
    return {"added": added, "filled": filled, "skipped": skipped, "failed": failed}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv_file")
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("--source", help="fixed value for Source (e.g. FCC) instead of the JSON value")
    ap.add_argument("--plain-bw", action="store_true", help="write bandwidth as a number without ' kHz'")
    ap.add_argument("--no-create", action="store_true", help="don't add new rows, only fill existing ones")
    ap.add_argument("--backup", action="store_true")
    a = ap.parse_args(argv)
    merge_into_csv(a.csv_file, a.inputs, company=a.source, plain_bw=a.plain_bw,
                   create=not a.no_create, backup=a.backup)


if __name__ == "__main__":
    main()