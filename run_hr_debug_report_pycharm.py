#!/usr/bin/env python3
from pathlib import Path
import webbrowser

from hr_debug_report import generate_report


# PyCharm direct-run config:
# 1. Modify CAPTURE_DIR if you want another capture.
# 2. Click Run in PyCharm.
# 3. The HTML report will be regenerated and opened in your browser.
WORKSPACE_DIR = Path(__file__).resolve().parent
CAPTURE_DIR = WORKSPACE_DIR / "captures" / "capture_20260425_084303"
OUTPUT_HTML = CAPTURE_DIR / "hr_debug_report.html"
AUTO_OPEN_BROWSER = True


def main() -> int:
    report_path = generate_report(CAPTURE_DIR, OUTPUT_HTML)
    print(f"Capture: {CAPTURE_DIR}")
    print(f"Report : {report_path}")

    if AUTO_OPEN_BROWSER:
        webbrowser.open(report_path.resolve().as_uri())

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
