#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Analyze STDF test log files and produce yield/failure summary
"""

import math
import json
from io import StringIO
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

# Configuration
INPUT_FILE = Path(r"C:\Users\igevorgy\Desktop\SEMI_SKILLs\File\1YUSK83G_001_S11P_N_20260526194205_M6251A0022AKX12NIA_T4C03.std")
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
            })
            continue

        # Parse FTR (Functional Test Record)
        if rec_type == "FTR":
            test_num = payload[0] if len(payload) > 0 else None
            site_num = payload[2] if len(payload) > 2 else "unknown"
            test_name = payload[22] if len(payload) > 22 and payload[22] else f"FTR_{test_num or 'UNKNOWN'}"

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
            })
            continue

    if not rows:
        raise ValueError("No test data (PTR/FTR/PRR) extracted from STDF file")

    norm_df = pd.DataFrame(rows)
    return norm_df, {"backend": "pystdf", "ignored_rows": len(lines) - len(rows)}


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
    report = report.replace("{{failed_test_events}}", str(metrics.get("failed_events", "N/A")))
    report = report.replace("{{top_failing_tests_bullets}}", top_failing_tests_bullets)
    report = report.replace("{{site_failure_bullets}}", site_failure_bullets)
    report = report.replace("{{initial_interpretation}}", build_top_level_interpretation(metrics))
    report = report.replace("{{potential_causes}}", build_potential_causes(metrics))
    report = report.replace("{{first_checks}}", build_first_checks(metrics))
    report = report.replace("{{next_actions}}", build_next_actions(metrics))
    report = report.replace("{{assumptions_notes}}", build_assumptions(metrics, info))

    report = report + "\n"
    return report


def main():
    input_file = INPUT_FILE
    df, info = parse_stdf(input_file)
    metrics = compute_metrics(df)
    report = generate_report(df, metrics, info, input_file)

    csv_path = input_file.parent / f"{input_file.stem}_normalized.csv"
    df.to_csv(csv_path, index=False)
    print(report)


if __name__ == "__main__":
    main()