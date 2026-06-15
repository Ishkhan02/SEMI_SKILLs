#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Analyze STDF test log files and produce yield/failure summary
"""

import argparse
import math
import json
import re
from io import StringIO
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

# Configuration
DEFAULT_INPUT_FILE = Path(r"C:\Users\igevorgy\Desktop\SEMI_SKILLs\File\1YUSK83G_001_S11P_N_20260526194205_M6251A0022AKX12NIA_T4C03.std")
TOP_N = 10


def parse_float(value: object) -> float:
    if value is None or value == "":
        return math.nan
    try:
        return float(str(value).strip())
    except:
        return math.nan


def parse_int(value: object) -> Optional[int]:
    f = parse_float(value)
    if math.isnan(f):
        return None
    return int(round(f))


def parse_coordinate_value(value: object) -> Optional[float]:
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(str(value).strip())
    except Exception:
        return None


def parse_coordinate_string(field_text: str) -> Dict[str, Optional[float]]:
    coords = {"row": None, "col": None, "die": None, "x": None, "y": None}
    if not field_text or not isinstance(field_text, str):
        return coords

    text = field_text.strip()
    patterns = {
        "row": re.compile(r"\b(?:row|row_num|rowid|r)\b[:=]?\s*([+-]?\d+)", re.IGNORECASE),
        "col": re.compile(r"\b(?:col|col_num|column|c)\b[:=]?\s*([+-]?\d+)", re.IGNORECASE),
        "die": re.compile(r"\b(?:die|die_num|dieid)\b[:=]?\s*([+-]?\d+)", re.IGNORECASE),
        "x": re.compile(r"\b(?:x|x_coord|xcoordinate|xpos)\b[:=]?\s*([+-]?\d+\.?\d*)", re.IGNORECASE),
        "y": re.compile(r"\b(?:y|y_coord|ycoordinate|ypos)\b[:=]?\s*([+-]?\d+\.?\d*)", re.IGNORECASE),
    }

    for name, regex in patterns.items():
        match = regex.search(text)
        if match:
            coords[name] = parse_coordinate_value(match.group(1))

    # Detect row/col pairs in compact form like R3C2 or R3 C2
    match = re.search(r"\bR(\d+)\s*[Cc](\d+)\b", text, re.IGNORECASE)
    if match:
        coords["row"] = parse_coordinate_value(match.group(1))
        coords["col"] = parse_coordinate_value(match.group(2))

    # Detect XY pairs in a single string
    match = re.search(r"\bX[:=\s]*([+-]?\d+\.?\d*)[\s,;]+Y[:=\s]*([+-]?\d+\.?\d*)\b", text, re.IGNORECASE)
    if match:
        coords["x"] = parse_coordinate_value(match.group(1))
        coords["y"] = parse_coordinate_value(match.group(2))

    return coords


def extract_coordinates_from_payload(payload: List[str]) -> Dict[str, Optional[float]]:
    coords = {"row": None, "col": None, "die": None, "x": None, "y": None}

    for i, field in enumerate(payload):
        if isinstance(field, str):
            parsed = parse_coordinate_string(field)
            for name, value in parsed.items():
                if value is not None:
                    coords[name] = value

        next_value = None
        if i + 1 < len(payload) and isinstance(payload[i + 1], str):
            next_value = parse_coordinate_value(payload[i + 1])

        field_lower = str(field).strip().lower()
        if next_value is not None:
            if field_lower in {"row", "row_num", "rowid", "r"}:
                coords["row"] = next_value
            elif field_lower in {"col", "col_num", "column", "c"}:
                coords["col"] = next_value
            elif field_lower in {"die", "die_num", "dieid"}:
                coords["die"] = next_value
            elif field_lower in {"x", "x_coord", "xcoordinate", "xpos"}:
                coords["x"] = next_value
            elif field_lower in {"y", "y_coord", "ycoordinate", "ypos"}:
                coords["y"] = next_value

    return coords


def detect_coordinate_fields(lines: List[str]) -> Dict[str, object]:
    coordinate_name_patterns = re.compile(r"\b(x|y|row|col|coordinate|coord|site|die)\b", re.IGNORECASE)
    coordinate_names = set()
    coordinate_records = 0

    for line in lines:
        if "|" not in line:
            continue
        fields = line.split("|")
        # Detect coordinate-related field names in record payloads
        for field in fields:
            if coordinate_name_patterns.search(field):
                coordinate_names.add(field.strip())

        # Recognize coordinate-like numeric pairs in PTR/FTR/PRR records
        rec_type = fields[0].strip().upper()
        if rec_type in {"PTR", "FTR", "PRR", "PIR"}:
            numeric_fields = []
            for f in fields[1:]:
                try:
                    numeric_fields.append(float(f))
                except Exception:
                    numeric_fields.append(None)
            for i in range(len(numeric_fields) - 1):
                a = numeric_fields[i]
                b = numeric_fields[i + 1]
                if a is None or b is None:
                    continue
                if -10000.0 < a < 10000.0 and -10000.0 < b < 10000.0:
                    if abs(a) >= 0.01 or abs(b) >= 0.01:
                        coordinate_records += 1
                        break

    return {
        "coordinate_detected": bool(coordinate_names),
        "coordinate_names": sorted(coordinate_names),
        "coordinate_records": coordinate_records,
    }


def collect_coordinate_stats(rows: List[Dict]) -> Dict[str, object]:
    coordinate_names = set()
    coordinate_records = 0

    for row in rows:
        has_any = False
        if row.get("coord_row") is not None:
            coordinate_names.add("ROW")
            has_any = True
        if row.get("coord_col") is not None:
            coordinate_names.add("COL")
            has_any = True
        if row.get("coord_die") is not None:
            coordinate_names.add("DIE")
            has_any = True
        if row.get("coord_x") is not None:
            coordinate_names.add("X_COORD")
            has_any = True
        if row.get("coord_y") is not None:
            coordinate_names.add("Y_COORD")
            has_any = True
        if has_any:
            coordinate_records += 1

    return {
        "coordinate_detected": bool(coordinate_names),
        "coordinate_names": sorted(coordinate_names),
        "coordinate_records": coordinate_records,
    }


def parse_stdf(stdf_path: Path) -> Tuple[pd.DataFrame, Dict]:
    """Parse STDF file using pystdf and return normalized dataframe"""
    from pystdf.IO import Parser
    from pystdf.Writers import TextWriter

    parser = Parser(inp=open(stdf_path, "rb"))
    buffer = StringIO()
    parser.addSink(TextWriter(buffer))
    parser.parse()
    atdf_text = buffer.getvalue()

    lines = [line.strip() for line in atdf_text.splitlines() if line.strip()]

    active_part_by_site: Dict[str, str] = {}
    rows: List[Dict] = []
    bin_names: Dict[Tuple[str, int], str] = {}
    synthetic_part_counter = 0

    for line in lines:
        if "|" not in line:
            continue

        parts = line.split("|")
        if not parts:
            continue

        rec_type = parts[0].strip().upper()
        payload = parts[1:] if len(parts) > 1 else []

        # Parse HBR (Hard Bin Record)
        if rec_type == "HBR":
            site_num = payload[1] if len(payload) > 1 else "unknown"
            hbin_num = parse_int(payload[2] if len(payload) > 2 else None)
            hbin_nam = payload[5] if len(payload) > 5 else ""
            if hbin_num is not None:
                bin_names[(f"H{site_num}", hbin_num)] = hbin_nam
            continue

        # Parse SBR (Soft Bin Record)
        if rec_type == "SBR":
            site_num = payload[1] if len(payload) > 1 else "unknown"
            sbin_num = parse_int(payload[2] if len(payload) > 2 else None)
            sbin_nam = payload[5] if len(payload) > 5 else ""
            if sbin_num is not None:
                bin_names[(f"S{site_num}", sbin_num)] = sbin_nam
            continue

        # Parse PIR (Part Initial Record)
        if rec_type == "PIR":
            site_num = payload[1] if len(payload) > 1 else "unknown"
            synthetic_part_counter += 1
            active_part_by_site[site_num] = f"P{synthetic_part_counter:06d}"
            continue

        # Parse PRR (Part Results Record)
        if rec_type == "PRR":
            site_num = payload[1] if len(payload) > 1 else "unknown"
            part_flag = payload[2] if len(payload) > 2 else "0"
            num_test = parse_int(payload[3] if len(payload) > 3 else None)
            hard_bin = parse_int(payload[4] if len(payload) > 4 else None)
            soft_bin = parse_int(payload[5] if len(payload) > 5 else None)
            test_time = parse_float(payload[8] if len(payload) > 8 else None)
            part_id = payload[9] if len(payload) > 9 and payload[9] else None
            coords = extract_coordinates_from_payload(payload)
            explicit_x = parse_coordinate_value(payload[6] if len(payload) > 6 else None)
            explicit_y = parse_coordinate_value(payload[7] if len(payload) > 7 else None)
            if explicit_x is not None:
                coords["x"] = explicit_x
            if explicit_y is not None:
                coords["y"] = explicit_y

            if part_id is None or part_id == "":
                part_id = active_part_by_site.get(site_num)
            if part_id is None or part_id == "":
                synthetic_part_counter += 1
                part_id = f"P{synthetic_part_counter:06d}"

            # Determine pass/fail: typically hard_bin=1 is pass, others are fail/other bins
            status = "PASS" if hard_bin == 1 else "FAIL"

            rows.append({
                "part_id": str(part_id),
                "site_num": str(site_num),
                "test_num": None,
                "test_name": f"Part Result (HBin:{hard_bin}, SBin:{soft_bin})",
                "result": test_time,
                "lo_limit": 0.0 if num_test is not None else math.nan,
                "hi_limit": float(num_test) if num_test is not None else math.nan,
                "units": "tests" if num_test is not None else "ms",
                "hard_bin": hard_bin,
                "soft_bin": soft_bin,
                "status": status,
                "source_record": "PRR",
                "coord_row": coords.get("row"),
                "coord_col": coords.get("col"),
                "coord_die": coords.get("die"),
                "coord_x": coords.get("x"),
                "coord_y": coords.get("y"),
            })
            continue

        # Parse PTR (Parametric Test Record)
        if rec_type == "PTR":
            test_num = payload[0] if len(payload) > 0 else None
            site_num = payload[2] if len(payload) > 2 else "unknown"
            result = parse_float(payload[5] if len(payload) > 5 else None)
            test_name = payload[6] if len(payload) > 6 and payload[6] else f"TEST_{test_num or 'UNKNOWN'}"
            lo_limit = parse_float(payload[12] if len(payload) > 12 else None)
            hi_limit = parse_float(payload[13] if len(payload) > 13 else None)
            units = payload[14] if len(payload) > 14 else ""
            lo_spec = payload[18] if len(payload) > 18 else ""
            hi_spec = payload[19] if len(payload) > 19 else ""
            coords = extract_coordinates_from_payload(payload)

            part_id = active_part_by_site.get(site_num)
            if part_id is None:
                synthetic_part_counter += 1
                part_id = f"P{synthetic_part_counter:06d}"
                active_part_by_site[site_num] = part_id

            fail = False
            has_limits = not (math.isnan(lo_limit) or math.isnan(hi_limit))
            if lo_limit == 0.0 and hi_limit == 0.0 and lo_spec.strip() == "" and hi_spec.strip() == "":
                has_limits = False

            if has_limits and not math.isnan(result):
                if not math.isnan(lo_limit) and result < lo_limit:
                    fail = True
                if not math.isnan(hi_limit) and result > hi_limit:
                    fail = True

            rows.append({
                "part_id": str(part_id),
                "site_num": str(site_num),
                "test_num": str(test_num) if test_num else None,
                "test_name": str(test_name),
                "result": result,
                "lo_limit": lo_limit,
                "hi_limit": hi_limit,
                "units": str(units),
                "hard_bin": pd.NA,
                "soft_bin": pd.NA,
                "status": "FAIL" if fail else "PASS",
                "source_record": "PTR",
                "coord_row": coords.get("row"),
                "coord_col": coords.get("col"),
                "coord_die": coords.get("die"),
                "coord_x": coords.get("x"),
                "coord_y": coords.get("y"),
            })
            continue

        # Parse FTR (Functional Test Record)
        if rec_type == "FTR":
            test_num = payload[0] if len(payload) > 0 else None
            site_num = payload[2] if len(payload) > 2 else "unknown"
            test_name = payload[22] if len(payload) > 22 and payload[22] else f"FTR_{test_num or 'UNKNOWN'}"
            coords = extract_coordinates_from_payload(payload)
            explicit_x = parse_coordinate_value(payload[9] if len(payload) > 9 else None)
            explicit_y = parse_coordinate_value(payload[10] if len(payload) > 10 else None)
            if explicit_x is not None:
                coords["x"] = explicit_x
            if explicit_y is not None:
                coords["y"] = explicit_y

            part_id = active_part_by_site.get(site_num)
            if part_id is None:
                synthetic_part_counter += 1
                part_id = f"P{synthetic_part_counter:06d}"
                active_part_by_site[site_num] = part_id

            rows.append({
                "part_id": str(part_id),
                "site_num": str(site_num),
                "test_num": str(test_num) if test_num else None,
                "test_name": str(test_name),
                "result": math.nan,
                "lo_limit": math.nan,
                "hi_limit": math.nan,
                "units": "",
                "hard_bin": pd.NA,
                "soft_bin": pd.NA,
                "status": "FAIL",
                "source_record": "FTR",
                "coord_row": coords.get("row"),
                "coord_col": coords.get("col"),
                "coord_die": coords.get("die"),
                "coord_x": coords.get("x"),
                "coord_y": coords.get("y"),
            })
            continue

    if not rows:
        raise ValueError("No test data (PTR/FTR/PRR) extracted from STDF file")

    coord_info = collect_coordinate_stats(rows)
    norm_df = pd.DataFrame(rows)
    return norm_df, {
        "backend": "pystdf",
        "ignored_rows": len(lines) - len(rows),
        "coordinate_info": coord_info,
    }


def compute_metrics(df: pd.DataFrame) -> Dict:
    """Compute yield and failure metrics"""
    # For part-level metrics, only use PRR (Part Results Record) which has the final verdict
    prr_df = df[df["source_record"] == "PRR"].copy()
    
    # Get part-level status: for each part, get the last/final PRR status
    part_status = prr_df.groupby("part_id").agg({"status": "first", "hard_bin": "first"}).reset_index()
    
    total_parts = len(part_status)
    passing_parts = len(part_status[part_status["status"] == "PASS"])
    failing_parts = len(part_status[part_status["status"] == "FAIL"])
    yield_pct = (passing_parts / total_parts * 100.0) if total_parts > 0 else 0.0
    
    # Failed events from all test records (PTR/FTR)
    failed_events = len(df[df["status"] == "FAIL"])
    
    # Top failing tests (from PTR/FTR, not PRR)
    test_df = df[df["source_record"].isin(["PTR", "FTR"])]
    top_failing = (
        test_df[test_df["status"] == "FAIL"]
        .groupby("test_name")
        .size()
        .sort_values(ascending=False)
        .head(TOP_N)
    )
    
    # Site pattern (failures across all records)
    site_fail_count = df[df["status"] == "FAIL"].groupby("site_num").size().sort_values(ascending=False)
    
    return {
        "total_parts": int(total_parts),
        "passing_parts": int(passing_parts),
        "failing_parts": int(failing_parts),
        "yield_pct": round(yield_pct, 2),
        "failed_events": int(failed_events),
        "top_failing_tests": top_failing.to_dict() if not top_failing.empty else {},
        "site_failures": site_fail_count.to_dict() if not site_fail_count.empty else {},
        "unique_sites": int(df["site_num"].nunique()),
    }


def load_output_template() -> str:
    asset_path = Path(__file__).resolve().parents[1] / "assets" / "output-template.md"
    text = asset_path.read_text(encoding="utf-8")
    template, _, _ = text.partition("---")
    return template.strip() + "\n"


def format_fail_bullets(counter: Dict[str, int], max_items: int = TOP_N, site_mode: bool = False) -> str:
    if not counter:
        return "N/A"
    lines = []
    for i, (name, count) in enumerate(sorted(counter.items(), key=lambda x: x[1], reverse=True), 1):
        if site_mode:
            lines.append(f"  - Site {name}: {count} failures")
        else:
            lines.append(f"  - {name}: {count} failures")
        if i >= max_items:
            break
    return "\n".join(lines)


def build_top_level_interpretation(metrics: Dict) -> str:
    if metrics["total_parts"] == 0:
        return "- No parts or valid test records were detected, so a first-pass engineering interpretation is unavailable."

    lines = []
    if metrics["yield_pct"] >= 90.0:
        lines.append("- Yield remains high, so the issue is more likely localized rather than a broad product or lot problem.")
    elif metrics["yield_pct"] >= 60.0:
        lines.append("- Yield is moderate, indicating a meaningful fail population that needs focused site/test review.")
    else:
        lines.append("- Yield is low, so the failure pattern may reflect a significant test-program or product issue.")

    if metrics["site_failures"]:
        top_site, top_site_count = max(metrics["site_failures"].items(), key=lambda x: x[1])
        total_fails = sum(metrics["site_failures"].values())
        if top_site_count / total_fails >= 0.6:
            lines.append(f"- Failures are concentrated on Site {top_site}, which suggests a site hardware/contact/socket/loadboard issue.")
        else:
            lines.append("- Failures are distributed across multiple sites, which suggests a shared test hardware, program, or process/product condition.")

    if metrics["top_failing_tests"]:
        top_test, top_count = max(metrics["top_failing_tests"].items(), key=lambda x: x[1])
        if top_count / max(1, metrics["failed_events"]) >= 0.4:
            lines.append(f"- One dominant failing test ({top_test}) accounts for a large share of failures, so check test method, limits, and instrument path for that test.")
        else:
            lines.append("- Multiple failing tests contribute to the fail population, so inspect shared equipment, program flow, and general part/test stability.")

    return "\n".join(lines)


def build_potential_causes(metrics: Dict) -> str:
    if metrics["total_parts"] == 0:
        return "- N/A"

    lines = []
    if metrics["site_failures"]:
        top_site, top_site_count = max(metrics["site_failures"].items(), key=lambda x: x[1])
        total_fails = sum(metrics["site_failures"].values())
        if top_site_count / total_fails >= 0.6:
            lines.append("- Site concentration suggests socket/contact, loadboard, or site-specific hardware/path issues.")
        else:
            lines.append("- Multi-site failures suggest a shared test system, program, or product/process issue.")

    if metrics["top_failing_tests"]:
        top_test, top_count = max(metrics["top_failing_tests"].items(), key=lambda x: x[1])
        lines.append(f"- Dominant failing test {top_test} suggests limits, test method, or instrument path issues for that measurement.")

    if not lines:
        lines.append("- No strong failure pattern could be computed from the available records.")

    return "\n".join(lines)


def build_coordinate_pattern_analysis(metrics: Dict, info: Dict) -> str:
    coord_info = info.get("coordinate_info", {})
    lines: List[str] = []

    if coord_info.get("coordinate_detected"):
        lines.append("- Coordinate fields were detected in the STDF file.")
        coordinate_names = coord_info.get("coordinate_names", [])
        if coordinate_names:
            lines.append(f"- Coordinate-related fields found: {', '.join(coordinate_names)}.")

        if metrics["site_failures"]:
            top_site, top_site_count = max(metrics["site_failures"].items(), key=lambda x: x[1])
            total_fails = sum(metrics["site_failures"].values())
            if top_site_count / total_fails >= 0.6:
                lines.append(f"- Failures are concentrated at Site {top_site}, suggesting a local coordinate/site cluster.")
            else:
                lines.append("- Failures are spread across multiple sites, suggesting a broader or scattered coordinate pattern.")
        else:
            lines.append("- No failing-site pattern could be derived from the available records.")

        if coord_info.get("coordinate_records", 0) > 0:
            lines.append(f"- {coord_info['coordinate_records']} coordinate-like records were observed during parsing.")

        return "\n".join(lines)

    # Fallback to site-level pattern analysis when explicit coordinate fields are absent.
    if metrics["site_failures"]:
        total_fails = sum(metrics["site_failures"].values())
        top_site, top_site_count = max(metrics["site_failures"].items(), key=lambda x: x[1])
        trend = (
            f"- Failures are concentrated at Site {top_site}, indicating a local site/hardware cluster."
            if top_site_count / total_fails >= 0.6
            else "- Failures are distributed across multiple sites, indicating a broader or scattered spatial pattern."
        )
        lines.append("- No explicit X/Y coordinate fields were detected in this STDF file.")
        lines.append(trend)
        lines.append("- Site-level failure distribution is the available spatial pattern for this data.")
        return "\n".join(lines)

    return "- Coordinate analysis unavailable. No coordinate or site spatial data is available in this STDF file."


def build_first_checks(metrics: Dict) -> str:
    if metrics["total_parts"] == 0:
        return "- N/A"

    lines = [
        "- Re-run a known-good part on the most failure-heavy site.",
        "- Compare the same failing tests across sites to isolate site-specific versus shared issues.",
        "- Verify test limits, program version, and instrument configuration for the top failing tests.",
        "- Check socket/contact/loadboard/instrument path if one site or a small set of sites dominates failures.",
    ]
    return "\n".join(lines)


def build_next_actions(metrics: Dict) -> str:
    if metrics["total_parts"] == 0:
        return "- N/A"

    lines = [
        "- If one site dominates, isolate and inspect the suspect site hardware or loadboard path.",
        "- If one test dominates, review the test method, limits, and measurement instrument path.",
        "- Trend the same failing tests across more logs to see whether the issue is persistent or lot-specific.",
        "- Use the normalized CSV output for deeper correlation and site-level follow-up.",
    ]
    return "\n".join(lines)


def build_assumptions(metrics: Dict, info: Dict) -> str:
    lines = [
        "- This is a first-pass analysis based on parsed STDF records and inferred pass/fail status.",
        "- Part-level yield is derived from PRR records and PTR/FTR fail events where available.",
        "- If limits are missing or bins are nonstandard, some status labels may be approximate.",
        f"- Parser backend used: {info['backend']}.",
        f"- {info['ignored_rows']} non-test records were ignored or unparseable.",
    ]
    return "\n".join(lines)


def generate_report(df: pd.DataFrame, metrics: Dict, info: Dict, input_file: Path) -> str:
    """Generate report using the output template"""
    template = load_output_template()
    top_failing_tests_bullets = format_fail_bullets(metrics.get("top_failing_tests", {}))
    site_failure_bullets = format_fail_bullets(metrics.get("site_failures", {}), site_mode=True)

    report = template
    report = report.replace("{{total_parts}}", str(metrics.get("total_parts", "N/A")))
    report = report.replace("{{yield_percent}}", str(metrics.get("yield_pct", "N/A")))
    report = report.replace("{{passing_parts}}", str(metrics.get("passing_parts", "N/A")))
    report = report.replace("{{failing_parts}}", str(metrics.get("failing_parts", "N/A")))
    report = report.replace("{{top_failing_tests_bullets}}", top_failing_tests_bullets)
    report = report.replace("{{top_failing_sites_bullets}}", site_failure_bullets)
    report = report.replace("{{coordinate_pattern_analysis}}", build_coordinate_pattern_analysis(metrics, info))

    report = report + "\n"
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze a semiconductor STDF file and generate a summary report.")
    parser.add_argument(
        "input_file",
        nargs="?",
        default=str(DEFAULT_INPUT_FILE),
        help="Path to the STDF file to analyze.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    input_file = Path(args.input_file)
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    df, info = parse_stdf(input_file)
    metrics = compute_metrics(df)
    report = generate_report(df, metrics, info, input_file)

    csv_path = input_file.parent / f"{input_file.stem}_normalized.csv"
    df.to_csv(csv_path, index=False)
    print(report)


if __name__ == "__main__":
    main()