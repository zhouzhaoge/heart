import argparse
import csv
from collections import Counter
from pathlib import Path
from statistics import mean


def load_csv_rows(path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def find_frame_cfg(path):
    cfg_path = path / "try.cfg"
    if not cfg_path.exists():
        return "missing"
    for line in cfg_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if line.startswith("frameCfg"):
            return line
    return "missing"


def summarize_capture(path):
    hr_rows = load_csv_rows(path / "heart_rate.csv")
    dbg_rows = load_csv_rows(path / "heart_rate_debug.csv")
    valid_hr = [row for row in hr_rows if int(row["valid"]) == 1]
    valid_dbg = [row for row in dbg_rows if int(row["valid"]) == 1]

    summary = {
        "path": str(path),
        "frame_cfg": find_frame_cfg(path),
        "hr_rows": len(hr_rows),
        "dbg_rows": len(dbg_rows),
        "valid_rows": len(valid_hr),
    }

    if not valid_hr:
        return summary

    bpms = [float(row["heart_rate_bpm"]) for row in valid_hr]
    hzs = [float(row["heart_rate_hz"]) for row in valid_hr]

    summary.update(
        {
            "first_valid_frame": int(valid_hr[0]["frame_number"]),
            "last_valid_frame": int(valid_hr[-1]["frame_number"]),
            "bpm_min": min(bpms),
            "bpm_avg": mean(bpms),
            "bpm_max": max(bpms),
            "hz_min": min(hzs),
            "hz_avg": mean(hzs),
            "hz_max": max(hzs),
            "top_bpm_bins": Counter(round(val) for val in bpms).most_common(8),
            "gate_counts": Counter(row["selected_range_bin"] for row in dbg_rows).most_common(4),
            "best_counts": Counter(row["best_range_bin"] for row in dbg_rows).most_common(4),
            "gate_changes": sum(1 for row in dbg_rows if int(row["gate_changed"]) == 1),
        }
    )

    jumps = []
    for idx in range(1, len(valid_hr)):
        jumps.append(
            (
                abs(float(valid_hr[idx]["heart_rate_hz"]) - float(valid_hr[idx - 1]["heart_rate_hz"])),
                int(valid_hr[idx]["frame_number"]),
            )
        )
    summary["max_jump"] = max(jumps) if jumps else (0.0, summary["first_valid_frame"])

    guide = [float(row["guide_freq"]) for row in valid_dbg]
    coarse = [float(row["coarse_freq"]) for row in valid_dbg]
    fine = [float(row["fine_freq"]) for row in valid_dbg]
    summary["guide_avg"] = mean(guide)
    summary["coarse_avg"] = mean(coarse)
    summary["fine_avg"] = mean(fine)

    segment_stats = []
    for start in range(summary["first_valid_frame"], summary["last_valid_frame"] + 1, 100):
        segment = [float(row["heart_rate_bpm"]) for row in valid_hr if start <= int(row["frame_number"]) < start + 100]
        if segment:
            segment_stats.append((start, start + 99, mean(segment), min(segment), max(segment)))
    summary["segments"] = segment_stats

    return summary


def print_summary(summary):
    print(summary["path"])
    print(f"  frameCfg: {summary['frame_cfg']}")
    print(f"  rows: hr={summary['hr_rows']} dbg={summary['dbg_rows']} valid={summary['valid_rows']}")
    if "first_valid_frame" not in summary:
        return
    print(
        f"  valid frames: {summary['first_valid_frame']} -> {summary['last_valid_frame']}"
    )
    print(
        "  bpm min/avg/max: "
        f"{summary['bpm_min']:.2f} / {summary['bpm_avg']:.2f} / {summary['bpm_max']:.2f}"
    )
    print(
        "  hz min/avg/max: "
        f"{summary['hz_min']:.4f} / {summary['hz_avg']:.4f} / {summary['hz_max']:.4f}"
    )
    print(
        "  guide/coarse/fine avg: "
        f"{summary['guide_avg']:.4f} / {summary['coarse_avg']:.4f} / {summary['fine_avg']:.4f}"
    )
    print(
        f"  max jump: {summary['max_jump'][0] * 60.0:.2f} bpm at frame {summary['max_jump'][1]}"
    )
    print(f"  top rounded bpm: {summary['top_bpm_bins']}")
    print(f"  gate counts: {summary['gate_counts']}, gate changes={summary['gate_changes']}")
    print(f"  best bins: {summary['best_counts']}")
    print("  segments:")
    for start, end, avg_bpm, min_bpm, max_bpm in summary["segments"]:
        print(f"    {start}-{end}: avg={avg_bpm:.2f} min={min_bpm:.2f} max={max_bpm:.2f}")


def main():
    parser = argparse.ArgumentParser(description="Compare heart-rate capture summaries.")
    parser.add_argument("captures", nargs="+", help="Capture directories containing heart_rate.csv")
    args = parser.parse_args()

    for capture in args.captures:
        print_summary(summarize_capture(Path(capture)))


if __name__ == "__main__":
    main()
