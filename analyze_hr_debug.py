#!/usr/bin/env python3
import argparse
import csv
from pathlib import Path
from statistics import mean


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def to_float(row: dict[str, str], key: str, default: float = 0.0) -> float:
    raw = row.get(key, "")
    if raw in ("", None):
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def to_int(row: dict[str, str], key: str, default: int = 0) -> int:
    raw = row.get(key, "")
    if raw in ("", None):
        return default
    try:
        return int(float(raw))
    except ValueError:
        return default


def merge_rows(
    hr_rows: list[dict[str, str]],
    dbg_rows: list[dict[str, str]],
) -> tuple[list[dict[str, float | int]], set[str]]:
    hr_by_key: dict[tuple[int, int], dict[str, str]] = {}
    for row in hr_rows:
        key = (to_int(row, "frame_number"), to_int(row, "subframe_number"))
        hr_by_key[key] = row

    available_debug_fields = set(dbg_rows[0].keys()) if dbg_rows else set()
    merged: list[dict[str, float | int]] = []
    for dbg in dbg_rows:
        key = (to_int(dbg, "frame_number"), to_int(dbg, "subframe_number"))
        hr = hr_by_key.get(key)
        if hr is None:
            continue

        coarse_peak_mag = to_float(dbg, "coarse_peak_mag")
        runner_up_peak_mag = to_float(dbg, "runner_up_peak_mag")
        runner_ratio = 0.0
        if coarse_peak_mag > 0.0:
            runner_ratio = runner_up_peak_mag / coarse_peak_mag

        merged.append(
            {
                "frame_number": key[0],
                "subframe_number": key[1],
                "valid": to_int(hr, "valid"),
                "bpm": to_float(hr, "heart_rate_bpm"),
                "confidence": to_float(hr, "confidence"),
                "guide_freq": to_float(dbg, "guide_freq"),
                "vme_guide_freq": to_float(dbg, "vme_guide_freq"),
                "coarse_freq": to_float(dbg, "coarse_freq"),
                "runner_up_freq": to_float(dbg, "runner_up_freq"),
                "fine_freq": to_float(dbg, "fine_freq"),
                "tracked_freq": to_float(dbg, "tracked_freq"),
                "guide_peak_mag": to_float(dbg, "guide_peak_mag"),
                "coarse_peak_mag": coarse_peak_mag,
                "runner_up_peak_mag": runner_up_peak_mag,
                "fine_peak_mag": to_float(dbg, "fine_peak_mag"),
                "tracked_peak_mag": to_float(dbg, "tracked_peak_mag"),
                "signal_power": to_float(dbg, "signal_power"),
                "sample_power_mean": to_float(dbg, "sample_power_mean"),
                "power_threshold": to_float(dbg, "power_threshold"),
                "selected_range_bin": to_int(dbg, "selected_range_bin", 0xFFFF),
                "best_range_bin": to_int(dbg, "best_range_bin", 0xFFFF),
                "selected_range_meters": to_float(dbg, "selected_range_meters"),
                "mti_alpha": to_float(dbg, "mti_alpha"),
                "vme_alpha": to_float(dbg, "vme_alpha"),
                "vme_last_rel_err": to_float(dbg, "vme_last_rel_err"),
                "vme_iterations": to_int(dbg, "vme_iterations"),
                "track_selected": to_int(dbg, "track_selected"),
                "step_limited": to_int(dbg, "step_limited"),
                "gate_changed": to_int(dbg, "gate_changed"),
                "runner_ratio": runner_ratio,
                "guide_vme_gap_bpm": abs(to_float(dbg, "guide_freq") - to_float(dbg, "vme_guide_freq")) * 60.0,
                "coarse_fine_gap_bpm": abs(to_float(dbg, "coarse_freq") - to_float(dbg, "fine_freq")) * 60.0,
                "tracked_fine_gap_bpm": abs(to_float(dbg, "tracked_freq") - to_float(dbg, "fine_freq")) * 60.0,
            }
        )

    return merged, available_debug_fields


def fmt_avg(rows: list[dict[str, float | int]], key: str) -> str:
    if not rows:
        return "n/a"
    return f"{mean(float(row[key]) for row in rows):.3f}"


def fmt_min_avg_max(rows: list[dict[str, float | int]], key: str) -> str:
    if not rows:
        return "n/a"
    values = [float(row[key]) for row in rows]
    return f"{min(values):.2f} / {mean(values):.2f} / {max(values):.2f}"


def has_fields(available_fields: set[str], *fields: str) -> bool:
    return all(field in available_fields for field in fields)


def find_windows(rows: list[dict[str, float | int]], predicate) -> list[list[dict[str, float | int]]]:
    windows: list[list[dict[str, float | int]]] = []
    current: list[dict[str, float | int]] = []
    previous_frame: int | None = None
    for row in rows:
        frame = int(row["frame_number"])
        if predicate(row):
            if current and previous_frame is not None and (frame - previous_frame) > 60:
                windows.append(current)
                current = []
            current.append(row)
        else:
            if current:
                windows.append(current)
                current = []
        previous_frame = frame
    if current:
        windows.append(current)
    return windows


def summarize_window(
    name: str,
    windows: list[list[dict[str, float | int]]],
    top_n: int,
    available_fields: set[str],
) -> None:
    print(f"  {name}: {len(windows)}")
    for window in windows[:top_n]:
        start = int(window[0]["frame_number"])
        end = int(window[-1]["frame_number"])
        avg_bpm = mean(float(row["bpm"]) for row in window if int(row["valid"]) == 1) if any(int(row["valid"]) == 1 for row in window) else 0.0
        parts = [f"    {start}-{end}: rows={len(window)} avgBpm={avg_bpm:.2f}"]
        if has_fields(available_fields, "runner_up_peak_mag"):
            avg_ratio = mean(float(row["runner_ratio"]) for row in window)
            parts.append(f"runnerRatio={avg_ratio:.3f}")
        if has_fields(available_fields, "step_limited"):
            step_hits = sum(int(row["step_limited"]) for row in window)
            parts.append(f"stepHits={step_hits}")
        if has_fields(available_fields, "track_selected"):
            track_hits = sum(int(row["track_selected"]) for row in window)
            parts.append(f"trackHits={track_hits}")
        print(" ".join(parts))


def print_segment_summary(
    rows: list[dict[str, float | int]],
    segment_frames: int,
    available_fields: set[str],
) -> None:
    if not rows:
        return
    start_frame = int(rows[0]["frame_number"])
    end_frame = int(rows[-1]["frame_number"])
    print("  segments:")
    segment_start = start_frame
    while segment_start <= end_frame:
        segment_end = segment_start + segment_frames - 1
        segment_rows = [row for row in rows if segment_start <= int(row["frame_number"]) <= segment_end]
        if segment_rows:
            valid_rows = [row for row in segment_rows if int(row["valid"]) == 1]
            avg_bpm = mean(float(row["bpm"]) for row in valid_rows) if valid_rows else 0.0
            avg_coarse = mean(float(row["coarse_freq"]) for row in segment_rows) * 60.0
            avg_fine = mean(float(row["fine_freq"]) for row in segment_rows) * 60.0
            parts = [
                f"    {segment_start}-{segment_end}: bpm={avg_bpm:.2f}",
                f"coarse={avg_coarse:.2f}",
                f"fine={avg_fine:.2f}",
            ]
            if has_fields(available_fields, "runner_up_peak_mag"):
                avg_runner_ratio = mean(float(row["runner_ratio"]) for row in segment_rows)
                parts.append(f"runnerRatio={avg_runner_ratio:.3f}")
            if has_fields(available_fields, "vme_iterations"):
                avg_vme_iter = mean(float(row["vme_iterations"]) for row in segment_rows)
                parts.append(f"vmeIter={avg_vme_iter:.2f}")
            if has_fields(available_fields, "vme_last_rel_err"):
                max_vme_err = max(float(row["vme_last_rel_err"]) for row in segment_rows)
                parts.append(f"vmeErrMax={max_vme_err:.6f}")
            if has_fields(available_fields, "step_limited"):
                step_hits = sum(int(row["step_limited"]) for row in segment_rows)
                parts.append(f"stepHits={step_hits}")
            if has_fields(available_fields, "track_selected"):
                track_hits = sum(int(row["track_selected"]) for row in segment_rows)
                parts.append(f"trackHits={track_hits}")
            print(" ".join(parts))
        segment_start += segment_frames


def print_top_rows(
    rows: list[dict[str, float | int]],
    runner_ratio_threshold: float,
    freq_gap_bpm_threshold: float,
    top_n: int,
    available_fields: set[str],
) -> None:
    suspects = [
        row
        for row in rows
        if (
            (has_fields(available_fields, "runner_up_peak_mag") and float(row["runner_ratio"]) >= runner_ratio_threshold)
            or (has_fields(available_fields, "step_limited") and int(row["step_limited"]) != 0)
            or (has_fields(available_fields, "track_selected") and int(row["track_selected"]) != 0)
            or float(row["coarse_fine_gap_bpm"]) >= freq_gap_bpm_threshold
        )
    ]
    suspects.sort(
        key=lambda row: (
            int(row["step_limited"]),
            int(row["track_selected"]),
            float(row["runner_ratio"]),
            float(row["coarse_fine_gap_bpm"]),
            float(row["confidence"]),
        ),
        reverse=True,
    )
    print(f"  suspicious rows: {len(suspects)}")
    for row in suspects[:top_n]:
        parts = [
            f"    frame={int(row['frame_number'])}",
            f"bpm={float(row['bpm']):.2f}",
            f"guide={float(row['guide_freq']) * 60.0:.2f}",
        ]
        if has_fields(available_fields, "vme_guide_freq"):
            parts.append(f"vmeGuide={float(row['vme_guide_freq']) * 60.0:.2f}")
        parts.append(f"coarse={float(row['coarse_freq']) * 60.0:.2f}")
        if has_fields(available_fields, "runner_up_freq"):
            parts.append(f"runner={float(row['runner_up_freq']) * 60.0:.2f}")
        parts.append(f"fine={float(row['fine_freq']) * 60.0:.2f}")
        if has_fields(available_fields, "tracked_freq"):
            parts.append(f"tracked={float(row['tracked_freq']) * 60.0:.2f}")
        if has_fields(available_fields, "runner_up_peak_mag"):
            parts.append(f"runnerRatio={float(row['runner_ratio']):.3f}")
        if has_fields(available_fields, "track_selected"):
            parts.append(f"trackSel={int(row['track_selected'])}")
        if has_fields(available_fields, "step_limited"):
            parts.append(f"stepLim={int(row['step_limited'])}")
        if has_fields(available_fields, "vme_iterations"):
            parts.append(f"vmeIter={int(row['vme_iterations'])}")
        if has_fields(available_fields, "vme_last_rel_err"):
            parts.append(f"vmeErr={float(row['vme_last_rel_err']):.6f}")
        print(" ".join(parts))


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze heart-rate debug CSVs from one capture.")
    parser.add_argument("capture", help="Capture directory containing heart_rate.csv and heart_rate_debug.csv")
    parser.add_argument("--segment-frames", type=int, default=100, help="Frame span for segment summary, default: 100")
    parser.add_argument("--runner-ratio-threshold", type=float, default=0.85, help="Runner-up / coarse peak threshold, default: 0.85")
    parser.add_argument("--freq-gap-bpm-threshold", type=float, default=6.0, help="Coarse/fine gap threshold in bpm, default: 6.0")
    parser.add_argument("--top", type=int, default=12, help="Number of suspicious rows/windows to print, default: 12")
    args = parser.parse_args()

    capture_dir = Path(args.capture)
    hr_path = capture_dir / "heart_rate.csv"
    dbg_path = capture_dir / "heart_rate_debug.csv"
    if not hr_path.exists() or not dbg_path.exists():
        raise SystemExit(f"Missing CSVs under {capture_dir}")

    hr_rows = load_csv_rows(hr_path)
    dbg_rows = load_csv_rows(dbg_path)
    merged_rows, available_debug_fields = merge_rows(hr_rows, dbg_rows)
    valid_rows = [row for row in merged_rows if int(row["valid"]) == 1]

    new_fields = {
        "vme_guide_freq",
        "runner_up_freq",
        "tracked_freq",
        "runner_up_peak_mag",
        "tracked_peak_mag",
        "mti_alpha",
        "vme_alpha",
        "vme_last_rel_err",
        "vme_iterations",
        "track_selected",
        "step_limited",
    }
    missing_fields = sorted(new_fields - available_debug_fields)

    print(capture_dir)
    print(f"  rows: hr={len(hr_rows)} dbg={len(dbg_rows)} merged={len(merged_rows)} valid={len(valid_rows)}")
    if missing_fields:
        print(f"  missing new debug fields: {', '.join(missing_fields)}")

    if not merged_rows:
        return 0

    if valid_rows:
        print(
            f"  valid frames: {int(valid_rows[0]['frame_number'])} -> {int(valid_rows[-1]['frame_number'])}"
        )
        print(f"  bpm min/avg/max: {fmt_min_avg_max(valid_rows, 'bpm')}")
    else:
        print("  valid frames: none")

    tracked_avg = "n/a"
    if has_fields(available_debug_fields, "tracked_freq"):
        tracked_avg = f"{mean(float(row['tracked_freq']) for row in merged_rows) * 60.0:.2f}"
    print(
        "  coarse/fine/tracked avg bpm: "
        f"{mean(float(row['coarse_freq']) for row in merged_rows) * 60.0:.2f} / "
        f"{mean(float(row['fine_freq']) for row in merged_rows) * 60.0:.2f} / "
        f"{tracked_avg}"
    )
    if has_fields(available_debug_fields, "runner_up_peak_mag"):
        print(
            "  runner ratio avg/max: "
            f"{fmt_avg(merged_rows, 'runner_ratio')} / "
            f"{max(float(row['runner_ratio']) for row in merged_rows):.3f}"
        )
    if has_fields(available_debug_fields, "vme_iterations"):
        print(
            "  vme iter avg/max: "
            f"{fmt_avg(merged_rows, 'vme_iterations')} / "
            f"{max(int(row['vme_iterations']) for row in merged_rows)}"
        )
    if has_fields(available_debug_fields, "vme_last_rel_err"):
        print(
            "  vme err avg/max: "
            f"{fmt_avg(merged_rows, 'vme_last_rel_err')} / "
            f"{max(float(row['vme_last_rel_err']) for row in merged_rows):.6f}"
        )
    if has_fields(available_debug_fields, "vme_guide_freq"):
        print(
            "  guide-vme gap avg bpm: "
            f"{fmt_avg(merged_rows, 'guide_vme_gap_bpm')}"
        )
    print(
        "  coarse-fine gap avg/max bpm: "
        f"{fmt_avg(merged_rows, 'coarse_fine_gap_bpm')} / "
        f"{max(float(row['coarse_fine_gap_bpm']) for row in merged_rows):.2f}"
    )
    if has_fields(available_debug_fields, "tracked_freq"):
        print(
            "  tracked-fine gap avg/max bpm: "
            f"{fmt_avg(merged_rows, 'tracked_fine_gap_bpm')} / "
            f"{max(float(row['tracked_fine_gap_bpm']) for row in merged_rows):.2f}"
        )

    flag_parts = [f"gateChanged={sum(int(row['gate_changed']) for row in merged_rows)}"]
    if has_fields(available_debug_fields, "track_selected"):
        flag_parts.insert(0, f"trackSelected={sum(int(row['track_selected']) for row in merged_rows)}")
    if has_fields(available_debug_fields, "step_limited"):
        insert_at = 1 if has_fields(available_debug_fields, "track_selected") else 0
        flag_parts.insert(insert_at, f"stepLimited={sum(int(row['step_limited']) for row in merged_rows)}")
    print("  flags: " + " ".join(flag_parts))

    competition_windows = []
    if has_fields(available_debug_fields, "runner_up_peak_mag"):
        competition_windows = find_windows(
            merged_rows,
            lambda row: float(row["runner_ratio"]) >= args.runner_ratio_threshold,
        )
    tracked_windows = []
    if has_fields(available_debug_fields, "track_selected"):
        tracked_windows = find_windows(
            merged_rows,
            lambda row: int(row["track_selected"]) != 0,
        )
    step_limited_windows = []
    if has_fields(available_debug_fields, "step_limited"):
        step_limited_windows = find_windows(
            merged_rows,
            lambda row: int(row["step_limited"]) != 0,
        )

    print("  windows:")
    summarize_window("high-competition", competition_windows, args.top, available_debug_fields)
    summarize_window("track-selected", tracked_windows, args.top, available_debug_fields)
    summarize_window("step-limited", step_limited_windows, args.top, available_debug_fields)
    print_segment_summary(merged_rows, args.segment_frames, available_debug_fields)
    print_top_rows(merged_rows, args.runner_ratio_threshold, args.freq_gap_bpm_threshold, args.top, available_debug_fields)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
