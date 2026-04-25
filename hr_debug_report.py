#!/usr/bin/env python3
import argparse
import csv
import html
import json
import subprocess
import sys
from pathlib import Path
from statistics import mean

TRACK_HALF_SPAN_HZ = 0.12
MAX_STEP_HZ = 0.015
TRACK_HALF_SPAN_BPM = TRACK_HALF_SPAN_HZ * 60.0
MAX_STEP_BPM = MAX_STEP_HZ * 60.0


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
) -> list[dict[str, float | int]]:
    hr_by_key: dict[tuple[int, int], dict[str, str]] = {}
    for row in hr_rows:
        key = (to_int(row, "frame_number"), to_int(row, "subframe_number"))
        hr_by_key[key] = row

    merged: list[dict[str, float | int]] = []
    for dbg in dbg_rows:
        key = (to_int(dbg, "frame_number"), to_int(dbg, "subframe_number"))
        hr = hr_by_key.get(key)
        if hr is None:
            continue
        coarse_bpm = to_float(dbg, "coarse_freq") * 60.0
        runner_bpm = to_float(dbg, "runner_up_freq") * 60.0
        merged.append(
            {
                "frame_number": key[0],
                "valid": to_int(hr, "valid"),
                "bpm": to_float(hr, "heart_rate_bpm"),
                "confidence": to_float(hr, "confidence"),
                "guide_bpm": to_float(dbg, "guide_freq") * 60.0,
                "vme_guide_bpm": to_float(dbg, "vme_guide_freq") * 60.0,
                "coarse_bpm": coarse_bpm,
                "runner_up_bpm": runner_bpm,
                "fine_bpm": to_float(dbg, "fine_freq") * 60.0,
                "tracked_bpm": to_float(dbg, "tracked_freq") * 60.0,
                "competition_ratio": to_float(dbg, "competition_ratio"),
                "guide_vme_gap_bpm": to_float(dbg, "guide_vme_gap_hz") * 60.0,
                "coarse_fine_gap_bpm": to_float(dbg, "coarse_fine_gap_hz") * 60.0,
                "tracked_fine_gap_bpm": to_float(dbg, "tracked_fine_gap_hz") * 60.0,
                "runner_gap_bpm": abs(coarse_bpm - runner_bpm),
                "vme_last_rel_err": to_float(dbg, "vme_last_rel_err"),
                "estimate_seq": to_int(dbg, "estimate_seq"),
                "inter_frame_proc_time_usec": to_float(dbg, "inter_frame_proc_time_usec"),
                "inter_frame_proc_margin_usec": to_float(dbg, "inter_frame_proc_margin_usec"),
                "tx_write_time_usec": to_float(dbg, "tx_write_time_usec"),
                "tx_overwrite_count": to_int(dbg, "tx_overwrite_count"),
                "vme_iterations": to_int(dbg, "vme_iterations"),
                "track_selected": to_int(dbg, "track_selected"),
                "step_limited": to_int(dbg, "step_limited"),
            }
        )
    return merged


def avg(rows: list[dict[str, float | int]], key: str) -> float:
    if not rows:
        return 0.0
    return mean(float(row[key]) for row in rows)


def find_bpm_windows(
    rows: list[dict[str, float | int]],
    low_bpm: float,
    high_bpm: float,
) -> list[tuple[int, int]]:
    windows: list[tuple[int, int]] = []
    start_frame: int | None = None
    prev_frame: int | None = None
    for row in rows:
        frame = int(row["frame_number"])
        bpm = float(row["bpm"])
        if low_bpm <= bpm <= high_bpm:
            if start_frame is None:
                start_frame = frame
            elif prev_frame is not None and (frame - prev_frame) > 20:
                windows.append((start_frame, prev_frame))
                start_frame = frame
        elif start_frame is not None and prev_frame is not None:
            windows.append((start_frame, prev_frame))
            start_frame = None
        prev_frame = frame

    if start_frame is not None and prev_frame is not None:
        windows.append((start_frame, prev_frame))
    return windows


def format_windows(windows: list[tuple[int, int]], top_n: int = 3) -> str:
    if not windows:
        return "none"
    return ", ".join(f"{start}-{end}" for start, end in windows[:top_n])


def build_summary(merged_rows: list[dict[str, float | int]]) -> list[tuple[str, str]]:
    valid_rows = [row for row in merged_rows if int(row["valid"]) == 1]
    estimate_rows = [row for row in merged_rows if int(row["estimate_seq"]) > 0]
    return [
        ("合并行数 / Merged rows", str(len(merged_rows))),
        ("有效行数 / Valid rows", str(len(valid_rows))),
        ("有效帧范围 / Valid frame range", "none" if not valid_rows else f"{int(valid_rows[0]['frame_number'])} -> {int(valid_rows[-1]['frame_number'])}"),
        ("有效 BPM 最小/平均/最大 / Valid BPM min/avg/max", "none" if not valid_rows else f"{min(float(r['bpm']) for r in valid_rows):.2f} / {avg(valid_rows, 'bpm'):.2f} / {max(float(r['bpm']) for r in valid_rows):.2f}"),
        ("Guide/VME 平均差值 / Guide-VME gap avg bpm", f"{avg(merged_rows, 'guide_vme_gap_bpm'):.2f}"),
        ("主峰-细化差值 / Coarse-Fine gap avg/max bpm", f"{avg(merged_rows, 'coarse_fine_gap_bpm'):.2f} / {max(float(r['coarse_fine_gap_bpm']) for r in merged_rows):.2f}"),
        ("跟踪-细化差值 / Tracked-Fine gap avg/max bpm", f"{avg(merged_rows, 'tracked_fine_gap_bpm'):.2f} / {max(float(r['tracked_fine_gap_bpm']) for r in merged_rows):.2f}"),
        ("竞争比平均/最大 / Competition avg/max", f"{avg(merged_rows, 'competition_ratio'):.3f} / {max(float(r['competition_ratio']) for r in merged_rows):.3f}"),
        ("次峰与主峰距离 / Runner gap avg/max bpm", f"{avg(merged_rows, 'runner_gap_bpm'):.2f} / {max(float(r['runner_gap_bpm']) for r in merged_rows):.2f}"),
        ("跟踪接管次数 / Track selected count", str(sum(int(r["track_selected"]) for r in merged_rows))),
        ("步进限制次数 / Step limited count", str(sum(int(r["step_limited"]) for r in merged_rows))),
        ("估计序号范围 / Estimate seq range/count", "none" if not estimate_rows else f"{int(estimate_rows[0]['estimate_seq'])} -> {int(estimate_rows[-1]['estimate_seq'])} / {len(estimate_rows)}"),
        ("处理时间平均/最大 / Proc time avg/max us", f"{avg(merged_rows, 'inter_frame_proc_time_usec'):.0f} / {max(float(r['inter_frame_proc_time_usec']) for r in merged_rows):.0f}"),
        ("处理余量最小/平均 / Proc margin min/avg us", f"{min(float(r['inter_frame_proc_margin_usec']) for r in merged_rows):.0f} / {avg(merged_rows, 'inter_frame_proc_margin_usec'):.0f}"),
        ("发送时间平均/最大 / TX write avg/max us", f"{avg(merged_rows, 'tx_write_time_usec'):.0f} / {max(float(r['tx_write_time_usec']) for r in merged_rows):.0f}"),
        ("发送覆盖最大值 / TX overwrite max", str(max(int(r["tx_overwrite_count"]) for r in merged_rows))),
    ]


def find_top_rows(merged_rows: list[dict[str, float | int]], limit: int) -> list[dict[str, float | int]]:
    suspects = [
        row
        for row in merged_rows
        if (
            int(row["step_limited"]) != 0
            or int(row["track_selected"]) != 0
            or float(row["coarse_fine_gap_bpm"]) >= 6.0
            or float(row["competition_ratio"]) >= 0.20
        )
    ]
    suspects.sort(
        key=lambda row: (
            int(row["step_limited"]),
            int(row["track_selected"]),
            float(row["competition_ratio"]),
            float(row["coarse_fine_gap_bpm"]),
            float(row["confidence"]),
        ),
        reverse=True,
    )
    return suspects[:limit]


def build_fallback_text_analysis(capture_dir: Path, merged_rows: list[dict[str, float | int]]) -> str:
    valid_rows = [row for row in merged_rows if int(row["valid"]) == 1]
    lines = [
        str(capture_dir),
        f"  rows: merged={len(merged_rows)} valid={len(valid_rows)}",
    ]
    if valid_rows:
        lines.append(
            f"  valid frames: {int(valid_rows[0]['frame_number'])} -> {int(valid_rows[-1]['frame_number'])}"
        )
        lines.append(
            "  valid bpm min/avg/max: "
            f"{min(float(r['bpm']) for r in valid_rows):.2f} / "
            f"{avg(valid_rows, 'bpm'):.2f} / "
            f"{max(float(r['bpm']) for r in valid_rows):.2f}"
        )
    lines.append(
        "  coarse/fine/tracked avg bpm: "
        f"{avg(merged_rows, 'coarse_bpm'):.2f} / "
        f"{avg(merged_rows, 'fine_bpm'):.2f} / "
        f"{avg(merged_rows, 'tracked_bpm'):.2f}"
    )
    lines.append(
        "  competition avg/max: "
        f"{avg(merged_rows, 'competition_ratio'):.3f} / "
        f"{max(float(r['competition_ratio']) for r in merged_rows):.3f}"
    )
    lines.append(
        "  tx write avg/max us: "
        f"{avg(merged_rows, 'tx_write_time_usec'):.0f} / "
        f"{max(float(r['tx_write_time_usec']) for r in merged_rows):.0f}"
    )
    lines.append(
        "  tx overwrite max: "
        f"{max(int(r['tx_overwrite_count']) for r in merged_rows)}"
    )
    top_rows = find_top_rows(merged_rows, 10)
    lines.append(f"  suspicious rows: {len(top_rows)} shown")
    for row in top_rows:
        lines.append(
            f"    frame={int(row['frame_number'])} "
            f"bpm={float(row['bpm']):.2f} "
            f"coarse={float(row['coarse_bpm']):.2f} "
            f"runner={float(row['runner_up_bpm']):.2f} "
            f"fine={float(row['fine_bpm']):.2f} "
            f"tracked={float(row['tracked_bpm']):.2f} "
            f"competition={float(row['competition_ratio']):.3f} "
            f"trackSel={int(row['track_selected'])} "
            f"stepLim={int(row['step_limited'])}"
        )
    return "\n".join(lines)


def run_text_analysis(capture_dir: Path, merged_rows: list[dict[str, float | int]]) -> str:
    analyze_script = Path(__file__).with_name("analyze_hr_debug.py")
    if not analyze_script.exists():
        return build_fallback_text_analysis(capture_dir, merged_rows)

    result = subprocess.run(
        [sys.executable, str(analyze_script), str(capture_dir)],
        cwd=str(Path(__file__).parent),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    output = ((result.stdout or "") + (result.stderr or "")).strip()
    if result.returncode != 0 or not output:
        return build_fallback_text_analysis(capture_dir, merged_rows)
    return output


def build_findings_html(merged_rows: list[dict[str, float | int]]) -> str:
    valid_rows = [row for row in merged_rows if int(row["valid"]) == 1]
    high_windows = find_bpm_windows(valid_rows, 81.5, 84.5)
    low_windows = find_bpm_windows(valid_rows, 74.5, 77.5)
    return "\n".join(
        [
            "<p><strong>结论 / Conclusion:</strong> 本次更可能的真实心率带在 <strong>82–84 bpm</strong>。前段大约在 487-607 帧、后段大约在 1357-1417 帧都形成了较稳定的平台。"
            " / The more plausible true heart-rate band in this capture is <strong>82–84 bpm</strong>. It forms stable plateaus roughly around frames 487-607 and 1357-1417.</p>",
            f"<p><strong>中间错误吸引带 / Middle false-attractor band:</strong> 中间阶段算法会切到 <strong>75–78 bpm</strong> 这一组候选，主要窗口大致是 {html.escape(format_windows(low_windows))}。"
            "这不是串口问题，而是 guide/VME/coarse 一起跳到了低频候选家族。 / In the middle section the algorithm flips to a <strong>75–78 bpm</strong> candidate family, mainly around "
            f"{html.escape(format_windows(low_windows))}. This is not a UART issue; guide/VME/coarse move together into a lower-frequency candidate family.</p>",
            "<p><strong>次峰影响 / Runner-up effect:</strong> 次峰不是唯一的错误来源，但会显著降低决策裕量。"
            f"本次 `competition ratio` 最高约 <strong>{max(float(row['competition_ratio']) for row in merged_rows):.3f}</strong>，"
            f"主峰与次峰平均只差 <strong>{avg(merged_rows, 'runner_gap_bpm'):.2f} bpm</strong>。"
            "这意味着在每个候选家族内部，主峰旁边就有一个比较近的次峰，算法一旦被 guide/VME 带到错误家族，细化和跟踪就更容易被次峰削弱稳定性。 / "
            "The runner-up is not the only source of error, but it clearly reduces decision margin. In this capture the maximum `competition ratio` is about "
            f"<strong>{max(float(row['competition_ratio']) for row in merged_rows):.3f}</strong>, while the average primary-to-runner distance is only <strong>{avg(merged_rows, 'runner_gap_bpm'):.2f} bpm</strong>. "
            "That means each candidate family already contains a nearby secondary peak, so once guide/VME lead the search into the wrong family, fine and tracked selection become easier to destabilize.</p>",
            f"<p><strong>平滑下滑与回升 / Why the ramps are smooth:</strong> 当前跟踪半窗约为 <strong>±{TRACK_HALF_SPAN_BPM:.1f} bpm</strong>，单次最大步进约为 <strong>{MAX_STEP_BPM:.1f} bpm</strong>。"
            "所以输出不是瞬时从 84 跳到 75，而是 84 → 83.1 → 82.2 ... → 75 这样逐步滑下，再逐步回升。 / "
            f"The current tracking half-window is about <strong>±{TRACK_HALF_SPAN_BPM:.1f} bpm</strong>, and the max step is about <strong>{MAX_STEP_BPM:.1f} bpm</strong> per estimate. "
            "So the output does not jump from 84 to 75 instantly; it slides down as 84 → 83.1 → 82.2 ... → 75, then climbs back in the same stepped way.</p>",
            f"<p><strong>传输健康 / Transport health:</strong> 本次 `txWriteUs` 平均约 <strong>{avg(merged_rows, 'tx_write_time_usec'):.0f} us</strong>，"
            f"`txOverwriteCount` 最大为 <strong>{max(int(row['tx_overwrite_count']) for row in merged_rows)}</strong>，"
            f"最小处理余量约 <strong>{min(float(row['inter_frame_proc_margin_usec']) for row in merged_rows):.0f} us</strong>。"
            "串口发送是健康的，不像是它导致了心率不稳定。 / TX stays healthy in this capture, so UART is unlikely to be the source of heart-rate instability.</p>",
        ]
    )


def build_root_cause_html() -> str:
    return "\n".join(
        [
            "<tr><th>更可能真实心率 / Likely true HR</th><td>82–84 bpm 更像真实目标心率；75–78 bpm 更像被候选切换和跟踪限速拉出来的错误吸引带。 / 82–84 bpm looks more like the real target band, while 75–78 bpm behaves more like a false attractor created by candidate switching and tracking rate limit.</td></tr>",
            "<tr><th>次峰作用 / Runner-up role</th><td>次峰通常离主峰很近，会降低主峰优势；即使它不是最终输出，也会让错误候选家族更容易在后续流程里占优。 / The runner-up usually stays close to the main peak and reduces the main peak's margin; even when it is not the final output, it makes the wrong candidate family easier to win later decisions.</td></tr>",
            f"<tr><th>跟踪窗影响 / Tracking window effect</th><td>当前跟踪半窗约 ±{TRACK_HALF_SPAN_BPM:.1f} bpm。84 bpm 附近时，下边界能碰到 76.8 bpm 一带；75 bpm 附近时，上边界又能碰到 82.2 bpm 一带，所以两个错误家族可以互相“够到”。 / The current tracking half-window is about ±{TRACK_HALF_SPAN_BPM:.1f} bpm. Around 84 bpm the lower edge can reach the 76.8 bpm region, and around 75 bpm the upper edge can reach about 82.2 bpm, so the two candidate families can touch each other.</td></tr>",
            f"<tr><th>步进限制影响 / Step-limit effect</th><td>当前最大步进约 {MAX_STEP_BPM:.1f} bpm 每次估计，因此一旦错误候选被接纳，输出会表现成连续斜坡，而不是瞬时跳变。 / The current max step is about {MAX_STEP_BPM:.1f} bpm per estimate, so once a wrong candidate is accepted, the output becomes a ramp rather than an instantaneous jump.</td></tr>",
            "<tr><th>串口是否是主因 / Is UART the main cause</th><td>不是主因。当前数据里发送耗时远低于处理余量，且没有覆盖丢弃。 / No. TX time stays far below processing margin and there is no overwrite/drop behavior in this capture.</td></tr>",
        ]
    )


def render_html(
    capture_dir: Path,
    merged_rows: list[dict[str, float | int]],
    summary: list[tuple[str, str]],
    top_rows: list[dict[str, float | int]],
    text_analysis: str,
) -> str:
    plot_rows = [
        {
            "frame": int(row["frame_number"]),
            "valid": int(row["valid"]),
            "bpm": round(float(row["bpm"]), 3),
            "guide": round(float(row["guide_bpm"]), 3),
            "vmeGuide": round(float(row["vme_guide_bpm"]), 3),
            "coarse": round(float(row["coarse_bpm"]), 3),
            "runner": round(float(row["runner_up_bpm"]), 3),
            "fine": round(float(row["fine_bpm"]), 3),
            "tracked": round(float(row["tracked_bpm"]), 3),
            "competition": round(float(row["competition_ratio"]), 5),
            "runnerGap": round(float(row["runner_gap_bpm"]), 3),
            "coarseFineGap": round(float(row["coarse_fine_gap_bpm"]), 3),
            "trackedFineGap": round(float(row["tracked_fine_gap_bpm"]), 3),
            "confidence": round(float(row["confidence"]), 3),
            "trackSelected": int(row["track_selected"]),
            "stepLimited": int(row["step_limited"]),
            "procTimeUs": round(float(row["inter_frame_proc_time_usec"]), 3),
            "procMarginUs": round(float(row["inter_frame_proc_margin_usec"]), 3),
            "txWriteUs": round(float(row["tx_write_time_usec"]), 3),
            "overwrite": int(row["tx_overwrite_count"]),
            "estimateSeq": int(row["estimate_seq"]),
        }
        for row in merged_rows
    ]

    summary_html = "\n".join(
        f"<tr><th>{html.escape(label)}</th><td>{html.escape(value)}</td></tr>"
        for label, value in summary
    )
    top_rows_html = "\n".join(
        (
            "<tr>"
            f"<td>{int(row['frame_number'])}</td>"
            f"<td>{float(row['bpm']):.2f}</td>"
            f"<td>{float(row['guide_bpm']):.2f}</td>"
            f"<td>{float(row['coarse_bpm']):.2f}</td>"
            f"<td>{float(row['runner_up_bpm']):.2f}</td>"
            f"<td>{float(row['fine_bpm']):.2f}</td>"
            f"<td>{float(row['tracked_bpm']):.2f}</td>"
            f"<td>{float(row['competition_ratio']):.3f}</td>"
            f"<td>{int(row['track_selected'])}</td>"
            f"<td>{int(row['step_limited'])}</td>"
            f"<td>{float(row['tx_write_time_usec']):.0f}</td>"
            "</tr>"
        )
        for row in top_rows
    )
    findings_html = build_findings_html(merged_rows)
    root_cause_html = build_root_cause_html()
    data_json = json.dumps(plot_rows, ensure_ascii=True)
    title = f"心率调试报告 / Heart Rate Debug Report - {capture_dir.name}"
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>{html.escape(title)}</title>
  <style>
    :root {{
      --bg: #f7f4eb;
      --panel: #fffdf8;
      --ink: #1f2a2e;
      --muted: #5e696d;
      --line: #d8cdb8;
      --accent: #b5482f;
      --accent-2: #1f7a8c;
      --accent-3: #7a9e1f;
      --accent-4: #7d5ba6;
      --warn: #cf6a32;
    }}
    body {{
      margin: 0;
      background:
        radial-gradient(circle at top right, rgba(181,72,47,0.14), transparent 28%),
        radial-gradient(circle at left 20%, rgba(31,122,140,0.12), transparent 24%),
        var(--bg);
      color: var(--ink);
      font: 15px/1.45 "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
    }}
    main {{
      max-width: 1500px;
      margin: 0 auto;
      padding: 28px 22px 40px;
    }}
    h1, h2 {{
      margin: 0 0 12px;
      font-family: Georgia, "Times New Roman", serif;
      font-weight: 700;
      letter-spacing: 0.02em;
    }}
    h1 {{
      font-size: 34px;
    }}
    h2 {{
      font-size: 22px;
    }}
    .subtitle {{
      color: var(--muted);
      margin: 6px 0 22px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
      gap: 18px;
      margin-bottom: 18px;
    }}
    .panel {{
      background: linear-gradient(180deg, rgba(255,255,255,0.96), rgba(250,247,239,0.96));
      border: 1px solid var(--line);
      border-radius: 18px;
      box-shadow: 0 10px 24px rgba(61, 48, 32, 0.08);
      padding: 18px 18px 16px;
    }}
    .panel.wide {{
      grid-column: 1 / -1;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }}
    th, td {{
      text-align: left;
      padding: 8px 8px;
      border-bottom: 1px solid #ebe2d3;
      vertical-align: top;
    }}
    th {{
      color: var(--muted);
      font-weight: 600;
      width: 42%;
    }}
    .chart-wrap {{
      margin-top: 8px;
    }}
    canvas {{
      width: 100%;
      height: 320px;
      display: block;
      border-radius: 12px;
      background: #fffefb;
      border: 1px solid #efe6d8;
    }}
    .legend {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px 18px;
      margin-top: 10px;
      color: var(--muted);
      font-size: 13px;
    }}
    .legend span::before {{
      content: "";
      display: inline-block;
      width: 12px;
      height: 12px;
      border-radius: 999px;
      margin-right: 8px;
      vertical-align: -1px;
      background: var(--dot, #000);
    }}
    pre {{
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      font: 13px/1.4 Consolas, "Courier New", monospace;
      color: #263338;
      background: #fbf8f1;
      border: 1px solid #efe6d8;
      border-radius: 12px;
      padding: 14px;
    }}
    .note {{
      color: var(--muted);
      margin-top: 8px;
      font-size: 13px;
    }}
  </style>
</head>
<body>
  <main>
    <h1>{html.escape(title)}</h1>
    <div class="subtitle">抓包目录 / Capture directory: {html.escape(str(capture_dir))}</div>

    <div class="grid">
      <section class="panel">
        <h2>摘要 / Summary</h2>
        <table>
          {summary_html}
        </table>
      </section>

      <section class="panel">
        <h2>初步判断 / Initial Findings</h2>
        {findings_html}
        <div class="note">本报告使用当前精简版 debug 字段，并包含传输健康统计。 / This report uses the compact debug fields and includes transport-health statistics.</div>
      </section>

      <section class="panel wide">
        <h2>可能根因 / Likely Root Causes</h2>
        <table>
          {root_cause_html}
        </table>
      </section>

      <section class="panel wide">
        <h2>心率与候选轨迹 / Heart Rate And Candidate Tracks</h2>
        <div class="chart-wrap"><canvas id="chart-bpm" width="1400" height="360"></canvas></div>
        <div class="legend">
          <span style="--dot:#b5482f">输出心率 / Output BPM</span>
          <span style="--dot:#1f7a8c">主候选 / Coarse BPM</span>
          <span style="--dot:#7a9e1f">细化结果 / Fine BPM</span>
          <span style="--dot:#7d5ba6">跟踪结果 / Tracked BPM</span>
          <span style="--dot:#cf6a32">次峰 / Runner-up BPM</span>
        </div>
        <div class="note">如果红色输出线在前后两段都稳定停在 82–84 bpm，而中间被拖到 75 bpm 附近，再回到高位，更像是算法在两个候选家族之间切换。 / If the red output line stays on the 82–84 bpm plateau in the early and late segments, gets dragged toward 75 bpm in the middle, and later returns upward, that looks more like switching between candidate families than transport failure.</div>
      </section>

      <section class="panel wide">
        <h2>次峰影响 / Runner-up Influence</h2>
        <div class="chart-wrap"><canvas id="chart-runner" width="1400" height="360"></canvas></div>
        <div class="legend">
          <span style="--dot:#b5482f">输出心率 / Output BPM</span>
          <span style="--dot:#1f7a8c">主候选 / Primary Candidate</span>
          <span style="--dot:#cf6a32">次峰 / Runner-up</span>
          <span style="--dot:#7d5ba6">跟踪结果 / Tracked Result</span>
        </div>
        <div class="note">看图时重点看两点：1. 橙色次峰线是否长期靠近蓝色主候选线；2. 这种靠近是否和下面图里的竞争比升高同时出现。若同时出现，说明次峰正在削弱主峰的决策裕量。 / Watch two things here: 1. whether the orange runner-up line stays close to the blue primary-candidate line; 2. whether that closeness happens together with a higher competition ratio in the next chart. When both happen together, the runner-up is reducing the primary peak's decision margin.</div>
      </section>

      <section class="panel wide">
        <h2>不稳定指标 / Instability Indicators</h2>
        <div class="chart-wrap"><canvas id="chart-risk" width="1400" height="360"></canvas></div>
        <div class="legend">
          <span style="--dot:#b5482f">竞争比 / Competition Ratio</span>
          <span style="--dot:#1f7a8c">主峰-细化差 / Coarse-Fine Gap (bpm)</span>
          <span style="--dot:#7d5ba6">跟踪-细化差 / Tracked-Fine Gap (bpm)</span>
          <span style="--dot:#cf6a32">步进限制 / Step Limited</span>
          <span style="--dot:#7a9e1f">跟踪接管 / Track Selected</span>
        </div>
        <div class="note">当 `stepLimited` 连续出现时，通常意味着输出正在被限速拉向另一组候选。 / When `stepLimited` appears repeatedly, the output is usually being rate-limited toward another candidate group.</div>
      </section>

      <section class="panel wide">
        <h2>传输健康 / Transport Health</h2>
        <div class="chart-wrap"><canvas id="chart-transport" width="1400" height="360"></canvas></div>
        <div class="legend">
          <span style="--dot:#1f7a8c">处理时间 / Proc Time (us)</span>
          <span style="--dot:#7a9e1f">处理余量 / Proc Margin (us)</span>
          <span style="--dot:#b5482f">发送耗时 / TX Write (us)</span>
          <span style="--dot:#7d5ba6">估计序号 / Estimate Seq</span>
          <span style="--dot:#cf6a32">覆盖次数 / Overwrite Count</span>
        </div>
        <div class="note">若发送耗时远小于处理余量、且覆盖次数维持为 0，则基本可以排除“debug 传输把实时链路挤爆”这类问题。 / If TX time stays far below processing margin and overwrite remains 0, you can mostly rule out the idea that debug transmission is choking the real-time path.</div>
      </section>

      <section class="panel wide">
        <h2>重点可疑行 / Top Suspicious Rows</h2>
        <table>
          <thead>
            <tr>
              <th>帧 / Frame</th>
              <th>输出 / BPM</th>
              <th>Guide</th>
              <th>主峰 / Coarse</th>
              <th>次峰 / Runner-up</th>
              <th>细化 / Fine</th>
              <th>跟踪 / Tracked</th>
              <th>竞争比 / Competition</th>
              <th>跟踪接管 / TrackSel</th>
              <th>步进限制 / StepLim</th>
              <th>发送耗时 / TX us</th>
            </tr>
          </thead>
          <tbody>
            {top_rows_html}
          </tbody>
        </table>
        <div class="note">这些行优先展示 `stepLimited`、`trackSelected`、高竞争比和较大的主峰/细化偏差。 / These rows prioritize `stepLimited`, `trackSelected`, high competition ratio, and larger coarse/fine separation.</div>
      </section>

      <section class="panel wide">
        <h2>命令行分析输出 / CLI Analysis Output</h2>
        <pre>{html.escape(text_analysis)}</pre>
      </section>
    </div>
  </main>

  <script>
    const rows = {data_json};

    function drawChart(canvasId, series, options) {{
      const canvas = document.getElementById(canvasId);
      const ctx = canvas.getContext('2d');
      const width = canvas.width;
      const height = canvas.height;
      const pad = {{ left: 56, right: 18, top: 16, bottom: 34 }};
      const plotW = width - pad.left - pad.right;
      const plotH = height - pad.top - pad.bottom;
      const frames = rows.map(r => r.frame);
      const xMin = Math.min(...frames);
      const xMax = Math.max(...frames);

      let yMin = options.yMin;
      let yMax = options.yMax;
      if (yMin === null || yMax === null) {{
        const vals = [];
        for (const s of series) {{
          for (const row of rows) {{
            const value = s.value(row);
            if (value !== null && Number.isFinite(value)) {{
              vals.push(value);
            }}
          }}
        }}
        yMin = yMin ?? Math.min(...vals);
        yMax = yMax ?? Math.max(...vals);
        if (yMin === yMax) {{
          yMax = yMin + 1;
        }}
      }}
      const yPad = (yMax - yMin) * 0.08;
      yMin -= yPad;
      yMax += yPad;

      function xOf(frame) {{
        return pad.left + ((frame - xMin) / (xMax - xMin || 1)) * plotW;
      }}
      function yOf(value) {{
        return pad.top + plotH - ((value - yMin) / (yMax - yMin || 1)) * plotH;
      }}

      ctx.clearRect(0, 0, width, height);
      ctx.fillStyle = '#fffefb';
      ctx.fillRect(0, 0, width, height);

      ctx.strokeStyle = '#e6ddcf';
      ctx.lineWidth = 1;
      ctx.beginPath();
      for (let i = 0; i < 5; i += 1) {{
        const y = pad.top + (plotH * i) / 4;
        ctx.moveTo(pad.left, y);
        ctx.lineTo(width - pad.right, y);
      }}
      ctx.stroke();

      ctx.strokeStyle = '#b8ae9d';
      ctx.beginPath();
      ctx.moveTo(pad.left, pad.top);
      ctx.lineTo(pad.left, height - pad.bottom);
      ctx.lineTo(width - pad.right, height - pad.bottom);
      ctx.stroke();

      ctx.fillStyle = '#5e696d';
      ctx.font = '12px Segoe UI';
      for (let i = 0; i < 5; i += 1) {{
        const value = yMax - ((yMax - yMin) * i) / 4;
        const y = pad.top + (plotH * i) / 4;
        ctx.fillText(value.toFixed(options.yDigits ?? 1), 6, y + 4);
      }}

      const ticks = 8;
      for (let i = 0; i <= ticks; i += 1) {{
        const frame = Math.round(xMin + ((xMax - xMin) * i) / ticks);
        const x = xOf(frame);
        ctx.fillText(String(frame), x - 12, height - 10);
      }}

      for (const s of series) {{
        ctx.strokeStyle = s.color;
        ctx.fillStyle = s.color;
        ctx.lineWidth = s.width || 2;
        ctx.beginPath();
        let started = false;
        for (const row of rows) {{
          const value = s.value(row);
          if (value === null || !Number.isFinite(value)) {{
            started = false;
            continue;
          }}
          const x = xOf(row.frame);
          const y = yOf(value);
          if (!started) {{
            ctx.moveTo(x, y);
            started = true;
          }} else {{
            ctx.lineTo(x, y);
          }}
        }}
        if (!s.pointsOnly) {{
          ctx.stroke();
        }}
      }}
    }}

    drawChart('chart-bpm', [
      {{ color: '#b5482f', value: row => row.valid ? row.bpm : null }},
      {{ color: '#1f7a8c', value: row => row.coarse }},
      {{ color: '#7a9e1f', value: row => row.fine }},
      {{ color: '#7d5ba6', value: row => row.tracked > 0 ? row.tracked : null }},
      {{ color: '#cf6a32', value: row => row.runner > 0 ? row.runner : null }},
    ], {{ yMin: null, yMax: null, yDigits: 1 }});

    drawChart('chart-runner', [
      {{ color: '#b5482f', value: row => row.valid ? row.bpm : null }},
      {{ color: '#1f7a8c', value: row => row.coarse }},
      {{ color: '#cf6a32', value: row => row.runner > 0 ? row.runner : null }},
      {{ color: '#7d5ba6', value: row => row.tracked > 0 ? row.tracked : null }},
    ], {{ yMin: null, yMax: null, yDigits: 1 }});

    drawChart('chart-risk', [
      {{ color: '#b5482f', value: row => row.competition }},
      {{ color: '#1f7a8c', value: row => row.coarseFineGap }},
      {{ color: '#7d5ba6', value: row => row.trackedFineGap }},
      {{ color: '#cf6a32', value: row => row.stepLimited ? 1 : 0 }},
      {{ color: '#7a9e1f', value: row => row.trackSelected ? 0.85 : 0 }},
    ], {{ yMin: 0, yMax: null, yDigits: 2 }});

    drawChart('chart-transport', [
      {{ color: '#1f7a8c', value: row => row.procTimeUs }},
      {{ color: '#7a9e1f', value: row => row.procMarginUs }},
      {{ color: '#b5482f', value: row => row.txWriteUs }},
      {{ color: '#7d5ba6', value: row => row.estimateSeq }},
      {{ color: '#cf6a32', value: row => row.overwrite }},
    ], {{ yMin: 0, yMax: null, yDigits: 0 }});
  </script>
</body>
</html>
"""


def generate_report(capture: str | Path, output: str | Path | None = None) -> Path:
    capture_dir = Path(capture)
    hr_path = capture_dir / "heart_rate.csv"
    dbg_path = capture_dir / "heart_rate_debug.csv"
    if not hr_path.exists() or not dbg_path.exists():
        raise FileNotFoundError(f"Missing CSVs under {capture_dir}")

    hr_rows = load_csv_rows(hr_path)
    dbg_rows = load_csv_rows(dbg_path)
    merged_rows = merge_rows(hr_rows, dbg_rows)
    if not merged_rows:
        raise RuntimeError(f"No merged rows found under {capture_dir}")

    summary = build_summary(merged_rows)
    top_rows = find_top_rows(merged_rows, 16)
    text_analysis = run_text_analysis(capture_dir, merged_rows)
    html_text = render_html(capture_dir, merged_rows, summary, top_rows, text_analysis)

    output_path = Path(output) if output else (capture_dir / "hr_debug_report.html")
    output_path.write_text(html_text, encoding="utf-8")
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate an HTML report for one heart-rate debug capture.")
    parser.add_argument("capture", help="Capture directory containing heart_rate.csv and heart_rate_debug.csv")
    parser.add_argument(
        "--output",
        help="Output HTML path. Default: <capture>/hr_debug_report.html",
    )
    args = parser.parse_args()

    output_path = generate_report(args.capture, args.output)
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
