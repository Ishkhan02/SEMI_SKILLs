\
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Analyze STD/STDF and print a strict chat-only summary.
No files are written. Requires: pandas, pystdf.
"""

from __future__ import annotations

import argparse
import math
from io import StringIO
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd  # type: ignore
from pystdf.IO import Parser  # type: ignore
from pystdf.Writers import TextWriter  # type: ignore

TEMPLATE = """## Key findings:

- **Total parts:** {{total_parts}}
- **Yield:** {{yield_percent}}%
- **Passing parts:** {{passing_parts}}
- **Failing parts:** {{failing_parts}}
- **Top failing tests:**
{{top_failing_tests_bullets}}
- **Top failing sites:**
{{top_failing_sites_bullets}}

## Failed coordinate pattern analysis
{{coordinate_pattern_analysis}}
"""


def safe_str(value: object, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def to_float(value: object) -> float:
    try:
        if value is None or str(value).strip() == "":
            return math.nan
        return float(value)
    except Exception:
        return math.nan


def to_int(value: object) -> Optional[int]:
    try:
        if value is None or str(value).strip() == "":
            return None
        return int(float(value))
    except Exception:
        return None


def stdf_to_atdf_lines(stdf_path: Path) -> List[str]:
    parser = Parser(inp=open(stdf_path, "rb"))
    buffer = StringIO()
    parser.addSink(TextWriter(buffer))
    parser.parse()
    return [line.strip() for line in buffer.getvalue().splitlines() if line.strip()]


def parse_stdf(stdf_path: Path) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    lines = stdf_to_atdf_lines(stdf_path)

    active_part_by_site: Dict[str, str] = {}
    prr_rows: List[dict] = []
    ptr_rows: List[dict] = []
    ftr_rows: List[dict] = []
    next_part_num = 0

    def new_part_key() -> str:
        nonlocal next_part_num
        next_part_num += 1
        return f"PART_{next_part_num:06d}"

    for line in lines:
        if ":" not in line:
            continue

        rec_type, payload = line.split(":", 1)
        rec_type = rec_type.strip().upper()
        fields = payload.split("|") if payload else []

        if rec_type == "PIR":
            site_num = safe_str(fields[1] if len(fields) > 1 else "unknown", "unknown")
            active_part_by_site[site_num] = new_part_key()
            continue

        if rec_type == "PTR":
            site_num = safe_str(fields[2] if len(fields) > 2 else "unknown", "unknown")
            test_num = safe_str(fields[0] if len(fields) > 0 else "", "")
            test_name = safe_str(fields[6] if len(fields) > 6 else "", f"TEST_{test_num or 'UNKNOWN'}")
            result = to_float(fields[5] if len(fields) > 5 else None)
            lo_limit = to_float(fields[12] if len(fields) > 12 else None)
            hi_limit = to_float(fields[13] if len(fields) > 13 else None)

            part_key = active_part_by_site.get(site_num)
            if not part_key:
                part_key = new_part_key()
                active_part_by_site[site_num] = part_key

            is_fail = False
            if not math.isnan(result) and not math.isnan(lo_limit) and result < lo_limit:
                is_fail = True
            if not math.isnan(result) and not math.isnan(hi_limit) and result > hi_limit:
                is_fail = True

            ptr_rows.append({
                "part_key": part_key,
                "site_num": site_num,
                "test_num": test_num,
                "test_name": test_name,
                "is_fail": is_fail,
            })
            continue

        if rec_type == "FTR":
            site_num = safe_str(fields[2] if len(fields) > 2 else "unknown", "unknown")
            test_num = safe_str(fields[0] if len(fields) > 0 else "", "")
            test_name = safe_str(fields[22] if len(fields) > 22 else "", f"FTR_{test_num or 'UNKNOWN'}")

            part_key = active_part_by_site.get(site_num)
            if not part_key:
                part_key = new_part_key()
                active_part_by_site[site_num] = part_key

            ftr_rows.append({
                "part_key": part_key,
                "site_num": site_num,
                "test_num": test_num,
                "test_name": test_name,
                "is_fail": True,
            })
            continue

        if rec_type == "PRR":
            site_num = safe_str(fields[1] if len(fields) > 1 else "unknown", "unknown")
            part_flg = safe_str(fields[2] if len(fields) > 2 else "", "")
            hard_bin = to_int(fields[4] if len(fields) > 4 else None)
            soft_bin = to_int(fields[5] if len(fields) > 5 else None)
            x_coord = to_int(fields[6] if len(fields) > 6 else None)
            y_coord = to_int(fields[7] if len(fields) > 7 else None)
            part_id_text = safe_str(fields[9] if len(fields) > 9 else "", "")

            part_key = active_part_by_site.get(site_num)
            if not part_key:
                part_key = new_part_key()

            prr_fail: Optional[bool] = None
            if soft_bin is not None:
                prr_fail = soft_bin > 9
            elif hard_bin is not None:
                prr_fail = hard_bin > 9
            elif part_flg:
                prr_fail = None

            prr_rows.append({
                "part_key": part_key,
                "site_num": site_num,
                "part_id_text": part_id_text,
                "part_flg": part_flg,
                "hard_bin": hard_bin,
                "soft_bin": soft_bin,
                "x_coord": x_coord,
                "y_coord": y_coord,
                "prr_fail": prr_fail,
            })

            if site_num in active_part_by_site:
                del active_part_by_site[site_num]
            continue

    return pd.DataFrame(prr_rows), pd.DataFrame(ptr_rows), pd.DataFrame(ftr_rows)


def compute_summary(prr_df: pd.DataFrame, ptr_df: pd.DataFrame, ftr_df: pd.DataFrame, top_n: int) -> Dict[str, object]:
    if not prr_df.empty:
        total_parts = int(len(prr_df))
        part_table = prr_df.copy()
    else:
        event_parts = []
        if not ptr_df.empty:
            event_parts.append(ptr_df[["part_key"]].copy())
        if not ftr_df.empty:
            event_parts.append(ftr_df[["part_key"]].copy())
        if event_parts:
            parts = pd.concat(event_parts, ignore_index=True).drop_duplicates()
            total_parts = int(len(parts))
            part_table = parts.copy()
            part_table["prr_fail"] = pd.NA
            part_table["x_coord"] = pd.NA
            part_table["y_coord"] = pd.NA
            part_table["site_num"] = pd.NA
        else:
            total_parts = 0
            part_table = pd.DataFrame(columns=["part_key", "prr_fail", "x_coord", "y_coord", "site_num"])

    fail_event_frames = []
    if not ptr_df.empty:
        fail_event_frames.append(ptr_df[ptr_df["is_fail"] == True][["part_key", "site_num", "test_num", "test_name"]].copy())
    if not ftr_df.empty:
        fail_event_frames.append(ftr_df[ftr_df["is_fail"] == True][["part_key", "site_num", "test_num", "test_name"]].copy())

    fail_events_df = pd.concat(fail_event_frames, ignore_index=True) if fail_event_frames else pd.DataFrame(columns=["part_key", "site_num", "test_num", "test_name"])
    fail_part_keys_from_events = set(fail_events_df["part_key"].astype(str).tolist()) if not fail_events_df.empty else set()

    failing_mask = []
    for _, row in part_table.iterrows():
        part_key = safe_str(row.get("part_key"), "")
        prr_fail = row.get("prr_fail") if "prr_fail" in part_table.columns else pd.NA
        if pd.notna(prr_fail):
            part_is_fail = bool(prr_fail)
        else:
            part_is_fail = part_key in fail_part_keys_from_events
        failing_mask.append(part_is_fail)

    if len(part_table) > 0:
        part_table = part_table.copy()
        part_table["is_fail_final"] = failing_mask
        failing_parts = int(part_table["is_fail_final"].sum())
    else:
        failing_parts = 0

    passing_parts = max(total_parts - failing_parts, 0)
    yield_pct = round((passing_parts / total_parts * 100.0), 2) if total_parts else 0.0

    if not fail_events_df.empty:
        top_tests_df = (
            fail_events_df.groupby(["test_num", "test_name"], dropna=False)
            .size()
            .reset_index(name="fail_count")
            .sort_values(["fail_count", "test_name"], ascending=[False, True])
            .head(top_n)
        )
        top_sites_df = (
            fail_events_df.groupby(["site_num"], dropna=False)
            .size()
            .reset_index(name="fail_count")
            .sort_values(["fail_count", "site_num"], ascending=[False, True])
            .head(top_n)
        )
    else:
        top_tests_df = pd.DataFrame(columns=["test_num", "test_name", "fail_count"])
        top_sites_df = pd.DataFrame(columns=["site_num", "fail_count"])

    coord_analysis = build_coordinate_analysis(part_table)

    return {
        "total_parts": total_parts,
        "passing_parts": passing_parts,
        "failing_parts": failing_parts,
        "yield_percent": yield_pct,
        "top_tests_df": top_tests_df,
        "top_sites_df": top_sites_df,
        "coordinate_pattern_analysis": coord_analysis,
    }


def build_coordinate_analysis(part_table: pd.DataFrame) -> str:
    if part_table.empty or "is_fail_final" not in part_table.columns:
        return "- Coordinate analysis unavailable."

    fail_coords = part_table[part_table["is_fail_final"] == True].copy()
    if fail_coords.empty:
        return "- No failing parts were found, so there are no failing coordinates to analyze."

    fail_coords = fail_coords.dropna(subset=["x_coord", "y_coord"])
    if fail_coords.empty:
        return "- Coordinate analysis unavailable."

    coord_counts = (
        fail_coords.groupby(["x_coord", "y_coord"], dropna=False)
        .size()
        .reset_index(name="fail_count")
        .sort_values(["fail_count", "x_coord", "y_coord"], ascending=[False, True, True])
    )

    total_fail_coords = int(coord_counts["fail_count"].sum())
    top1_share = int(coord_counts.iloc[0]["fail_count"]) / total_fail_coords if total_fail_coords else 0.0
    top3_share = coord_counts.head(3)["fail_count"].sum() / total_fail_coords if total_fail_coords else 0.0

    lines: List[str] = [f"- Failing coordinate records with usable X/Y: {total_fail_coords}"]
    lines.append("- Most frequent failing coordinates:")
    for _, row in coord_counts.head(3).iterrows():
        x = int(row['x_coord'])
        y = int(row['y_coord'])
        c = int(row['fail_count'])
        lines.append(f"  - ({x}, {y}) — {c} failures")

    if top1_share >= 0.50 or top3_share >= 0.75:
        lines.append("- Pattern result: failures are concentrated in a small location set.")
    else:
        lines.append("- Pattern result: failures are scattered rather than concentrated in one dominant location.")
    return "\n".join(lines)


def bullets_for_top_tests(df: pd.DataFrame) -> str:
    if df.empty:
        return "  - N/A"
    return "\n".join(
        f"  - {safe_str(row.get('test_name'), 'UNKNOWN_TEST')} — {int(row.get('fail_count', 0))} failures"
        for _, row in df.iterrows()
    )


def bullets_for_top_sites(df: pd.DataFrame) -> str:
    if df.empty:
        return "  - N/A"
    return "\n".join(
        f"  - Site {safe_str(row.get('site_num'), 'N/A')}: {int(row.get('fail_count', 0))} failures"
        for _, row in df.iterrows()
    )


def render_output(metrics: Dict[str, object]) -> str:
    text = TEMPLATE
    replacements = {
        'total_parts': str(metrics['total_parts']),
        'yield_percent': f"{float(metrics['yield_percent']):.2f}",
        'passing_parts': str(metrics['passing_parts']),
        'failing_parts': str(metrics['failing_parts']),
        'top_failing_tests_bullets': bullets_for_top_tests(metrics['top_tests_df']),
        'top_failing_sites_bullets': bullets_for_top_sites(metrics['top_sites_df']),
        'coordinate_pattern_analysis': str(metrics['coordinate_pattern_analysis']),
    }
    for key, value in replacements.items():
        text = text.replace('{{' + key + '}}', value)
    return text


def main() -> int:
    parser = argparse.ArgumentParser(description='Analyze STD/STDF and print strict summary.')
    parser.add_argument('input_file', help='Path to .std / .stdf file')
    parser.add_argument('--top', type=int, default=5, help='Top N tests/sites to show')
    args = parser.parse_args()

    input_path = Path(args.input_file)
    if not input_path.exists():
        raise FileNotFoundError(f'Input file not found: {input_path}')
    if input_path.suffix.lower() not in {'.std', '.stdf'}:
        raise ValueError('Input file must be .std or .stdf')

    prr_df, ptr_df, ftr_df = parse_stdf(input_path)
    metrics = compute_summary(prr_df, ptr_df, ftr_df, top_n=max(1, args.top))
    print(render_output(metrics))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
