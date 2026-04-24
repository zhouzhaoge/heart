#!/usr/bin/env python3
import argparse
import csv
import struct
import sys
import time
from contextlib import ExitStack
from pathlib import Path
import shutil

import serial


MAGIC_WORD = b"\x02\x01\x04\x03\x06\x05\x08\x07"
HEADER_LEN = 40
TLV_HEADER_LEN = 8
MAX_TOTAL_PACKET_LEN = 32768
MAX_TLVS_PER_FRAME = 32

MMWDEMO_OUTPUT_MSG_HEART_RATE = 1001
MMWDEMO_OUTPUT_MSG_HEART_RATE_DEBUG = 1002

DEFAULT_CFG_PORT = "COM4"
DEFAULT_DATA_PORT = "COM3"
DEFAULT_CFG_BAUD = 115200
DEFAULT_DATA_BAUD = 921600

HEART_RATE_FIELDS = [
    "frame_number",
    "subframe_number",
    "time_cpu_cycles",
    "heart_rate_bpm",
    "heart_rate_hz",
    "confidence",
    "sample_rate_hz",
    "range_meters",
    "selected_range_bin",
    "window_length",
    "valid",
]

HEART_RATE_DEBUG_FIELDS = [
    "frame_number",
    "subframe_number",
    "time_cpu_cycles",
    "sample_power_mean",
    "power_threshold",
    "best_score",
    "selected_score",
    "guide_freq",
    "vme_guide_freq",
    "coarse_freq",
    "runner_up_freq",
    "fine_freq",
    "tracked_freq",
    "guide_peak_mag",
    "coarse_peak_mag",
    "runner_up_peak_mag",
    "fine_peak_mag",
    "tracked_peak_mag",
    "signal_power",
    "mti_alpha",
    "vme_alpha",
    "vme_last_rel_err",
    "selected_range_meters",
    "best_range_bin",
    "selected_range_bin",
    "window_length",
    "sample_count",
    "is_filled",
    "valid",
    "gate_changed",
    "vme_iterations",
    "track_selected",
    "step_limited",
]


def open_serial(port: str, baudrate: int, timeout: float) -> serial.Serial:
    return serial.Serial(port=port, baudrate=baudrate, timeout=timeout)


def load_cfg_lines(cfg_path: Path) -> list[str]:
    lines: list[str] = []
    for raw in cfg_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("%") or line.startswith("#"):
            continue
        lines.append(line)
    return lines


def send_cfg(cfg_ser: serial.Serial, cfg_lines: list[str], inter_cmd_delay: float) -> None:
    print(f"[CFG] Sending {len(cfg_lines)} commands on {cfg_ser.port} ...")
    cfg_ser.reset_input_buffer()
    cfg_ser.reset_output_buffer()

    for line in cfg_lines:
        payload = (line + "\n").encode("ascii")
        cfg_ser.write(payload)
        cfg_ser.flush()
        print(f"[CFG] >> {line}")
        time.sleep(inter_cmd_delay)

        response = cfg_ser.read_all()
        if response:
            text = response.decode("utf-8", errors="replace").strip()
            if text:
                for resp_line in text.splitlines():
                    print(f"[CFG] << {resp_line}")

    time.sleep(0.2)
    response = cfg_ser.read_all()
    if response:
        text = response.decode("utf-8", errors="replace").strip()
        if text:
            for resp_line in text.splitlines():
                print(f"[CFG] << {resp_line}")

    settle_deadline = time.time() + 1.0
    while time.time() < settle_deadline:
        response = cfg_ser.read_all()
        if response:
            text = response.decode("utf-8", errors="replace").strip()
            if text:
                for resp_line in text.splitlines():
                    print(f"[CFG] << {resp_line}")
            settle_deadline = time.time() + 0.3
        time.sleep(0.05)


def drain_data_serial(data_ser: serial.Serial, rx_buffer: bytearray) -> int:
    chunk = data_ser.read_all()
    if chunk:
        rx_buffer.extend(chunk)
        return len(chunk)
    return 0


def drain_text_serial(ser: serial.Serial, text_buffer: bytearray, prefix: str) -> int:
    chunk = ser.read_all()
    if not chunk:
        return 0

    text_buffer.extend(chunk)
    last_newline = max(text_buffer.rfind(b"\n"), text_buffer.rfind(b"\r"))
    if last_newline < 0:
        return len(chunk)

    completed = bytes(text_buffer[:last_newline + 1])
    del text_buffer[:last_newline + 1]

    text = completed.decode("utf-8", errors="replace")
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            print(f"{prefix} {stripped}")

    return len(chunk)


def find_magic_word(buffer: bytearray) -> int:
    return buffer.find(MAGIC_WORD)


def parse_frame_header(header: bytes) -> dict[str, int]:
    values = struct.unpack("<4H8I", header)
    return {
        "version": values[4],
        "total_packet_len": values[5],
        "platform": values[6],
        "frame_number": values[7],
        "time_cpu_cycles": values[8],
        "num_detected_obj": values[9],
        "num_tlvs": values[10],
        "subframe_number": values[11],
    }


def validate_frame_header(header: dict[str, int]) -> str | None:
    total_packet_len = header["total_packet_len"]
    if total_packet_len < HEADER_LEN:
        return f"total_packet_len={total_packet_len} smaller than header"
    if total_packet_len > MAX_TOTAL_PACKET_LEN:
        return f"total_packet_len={total_packet_len} exceeds max={MAX_TOTAL_PACKET_LEN}"
    if (total_packet_len % 32) != 0:
        return f"total_packet_len={total_packet_len} is not 32-byte aligned"
    if header["num_tlvs"] > MAX_TLVS_PER_FRAME:
        return f"num_tlvs={header['num_tlvs']} exceeds max={MAX_TLVS_PER_FRAME}"
    return None


def parse_heart_rate_payload(payload: bytes) -> dict[str, float | int]:
    heart_rate_bpm, heart_rate_hz, confidence, sample_rate_hz, range_meters, selected_range_bin, window_length, valid, _reserved = struct.unpack(
        "<5f4H", payload
    )
    return {
        "heart_rate_bpm": heart_rate_bpm,
        "heart_rate_hz": heart_rate_hz,
        "confidence": confidence,
        "sample_rate_hz": sample_rate_hz,
        "range_meters": range_meters,
        "selected_range_bin": selected_range_bin,
        "window_length": window_length,
        "valid": valid,
    }


def parse_heart_rate_debug_payload(payload: bytes) -> dict[str, float | int]:
    values = struct.unpack("<20f10H", payload)
    return {
        "sample_power_mean": values[0],
        "power_threshold": values[1],
        "best_score": values[2],
        "selected_score": values[3],
        "guide_freq": values[4],
        "vme_guide_freq": values[5],
        "coarse_freq": values[6],
        "runner_up_freq": values[7],
        "fine_freq": values[8],
        "tracked_freq": values[9],
        "guide_peak_mag": values[10],
        "coarse_peak_mag": values[11],
        "runner_up_peak_mag": values[12],
        "fine_peak_mag": values[13],
        "tracked_peak_mag": values[14],
        "signal_power": values[15],
        "mti_alpha": values[16],
        "vme_alpha": values[17],
        "vme_last_rel_err": values[18],
        "selected_range_meters": values[19],
        "best_range_bin": values[20],
        "selected_range_bin": values[21],
        "window_length": values[22],
        "sample_count": values[23],
        "is_filled": values[24],
        "valid": values[25],
        "gate_changed": values[26],
        "vme_iterations": values[27],
        "track_selected": values[28],
        "step_limited": values[29],
    }


def create_capture_dir(base_dir: Path, cfg_path: Path) -> Path:
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    capture_dir = base_dir / f"capture_{timestamp}"
    capture_dir.mkdir(parents=True, exist_ok=False)
    shutil.copy2(cfg_path, capture_dir / cfg_path.name)
    return capture_dir


def open_csv_writer(stack: ExitStack, csv_path: Path, fieldnames: list[str]) -> tuple[object, csv.DictWriter]:
    csv_file = stack.enter_context(csv_path.open("w", newline="", encoding="utf-8"))
    writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
    writer.writeheader()
    csv_file.flush()
    return csv_file, writer


def describe_rx_buffer(rx_buffer: bytearray) -> str:
    start = find_magic_word(rx_buffer)
    if start < 0:
        return f"rxBuf={len(rx_buffer)} magic=missing"

    if len(rx_buffer) < (start + HEADER_LEN):
        return f"rxBuf={len(rx_buffer)} magicAt={start} state=waiting_header"

    header = parse_frame_header(bytes(rx_buffer[start:start + HEADER_LEN]))
    header_issue = validate_frame_header(header)
    if header_issue is not None:
        return f"rxBuf={len(rx_buffer)} magicAt={start} invalidHeader={header_issue}"

    total_packet_len = header["total_packet_len"]
    have_len = len(rx_buffer) - start
    if have_len < total_packet_len:
        return (
            f"rxBuf={len(rx_buffer)} magicAt={start} "
            f"frame={header['frame_number']} total={total_packet_len} have={have_len}"
        )

    return (
        f"rxBuf={len(rx_buffer)} magicAt={start} "
        f"frame={header['frame_number']} total={total_packet_len} have={have_len} state=ready"
    )


def read_one_frame(data_ser: serial.Serial, rx_buffer: bytearray) -> bytes | None:
    chunk = data_ser.read(4096)
    if chunk:
        rx_buffer.extend(chunk)

    start = find_magic_word(rx_buffer)
    if start < 0:
        if len(rx_buffer) > 2 * 1024 * 1024:
            del rx_buffer[:-len(MAGIC_WORD)]
        return None

    if start > 0:
        del rx_buffer[:start]

    if len(rx_buffer) < HEADER_LEN:
        return None

    header = parse_frame_header(bytes(rx_buffer[:HEADER_LEN]))
    header_issue = validate_frame_header(header)
    if header_issue is not None:
        print(f"[SYNC] invalid frame header at frame={header['frame_number']}: {header_issue}")
        del rx_buffer[:1]
        return None

    total_packet_len = header["total_packet_len"]
    if len(rx_buffer) < total_packet_len:
        return None

    frame = bytes(rx_buffer[:total_packet_len])
    del rx_buffer[:total_packet_len]
    return frame


def parse_tlvs(frame: bytes) -> tuple[dict[str, int], list[tuple[int, bytes]], str | None]:
    header = parse_frame_header(frame[:HEADER_LEN])
    offset = HEADER_LEN
    tlvs: list[tuple[int, bytes]] = []
    error: str | None = None

    for _ in range(header["num_tlvs"]):
        if offset + TLV_HEADER_LEN > len(frame):
            error = f"truncated TLV header at offset={offset}"
            break

        tlv_type, tlv_length = struct.unpack("<2I", frame[offset:offset + TLV_HEADER_LEN])
        offset += TLV_HEADER_LEN
        if tlv_length == 0:
            error = f"zero-length TLV type={tlv_type} at offset={offset - TLV_HEADER_LEN}"
            break

        if offset + tlv_length > len(frame):
            error = (
                f"truncated TLV payload type={tlv_type} "
                f"len={tlv_length} offset={offset}"
            )
            break

        payload = frame[offset:offset + tlv_length]
        offset += tlv_length
        tlvs.append((tlv_type, payload))

    return header, tlvs, error


def monitor_data(
    data_ser: serial.Serial,
    cfg_ser: serial.Serial,
    raw_file,
    heart_rate_writer: csv.DictWriter,
    heart_rate_csv,
    heart_rate_debug_writer: csv.DictWriter,
    heart_rate_debug_csv,
    rx_buffer: bytearray,
    cfg_rx_buffer: bytearray,
    idle_log_interval: float,
) -> None:
    last_wait_log_time = time.monotonic()
    print(f"[DATA] Listening on {data_ser.port} @ {data_ser.baudrate} ...")

    while True:
        drain_text_serial(cfg_ser, cfg_rx_buffer, "[CLI]")
        frame = read_one_frame(data_ser, rx_buffer)
        if frame is None:
            now = time.monotonic()
            if (now - last_wait_log_time) >= idle_log_interval:
                print(f"[WAIT] {describe_rx_buffer(rx_buffer)}")
                last_wait_log_time = now
            continue

        last_wait_log_time = time.monotonic()
        header, tlvs, tlv_error = parse_tlvs(frame)
        raw_file.write(frame)
        raw_file.flush()
        heart_rate_found = False
        heart_rate_debug_found = False

        if tlv_error is not None:
            print(
                f"[TLV] frame={header['frame_number']} subFrame={header['subframe_number']} "
                f"{tlv_error}"
            )

        for tlv_type, payload in tlvs:
            if tlv_type == MMWDEMO_OUTPUT_MSG_HEART_RATE:
                if len(payload) != struct.calcsize("<5f4H"):
                    print(
                        f"[DATA] Frame {header['frame_number']} subFrame {header['subframe_number']} "
                        f"heart-rate TLV length mismatch: {len(payload)}"
                    )
                    continue

                heart = parse_heart_rate_payload(payload)
                heart_rate_found = True
                heart_rate_writer.writerow(
                    {
                        "frame_number": header["frame_number"],
                        "subframe_number": header["subframe_number"],
                        "time_cpu_cycles": header["time_cpu_cycles"],
                        **heart,
                    }
                )
                heart_rate_csv.flush()
                print(
                    f"[HR] frame={header['frame_number']} subFrame={header['subframe_number']} "
                    f"valid={heart['valid']} bpm={heart['heart_rate_bpm']:.2f} "
                    f"hz={heart['heart_rate_hz']:.3f} conf={heart['confidence']:.3f} "
                    f"gate={heart['selected_range_bin']} range={heart['range_meters']:.3f} m "
                    f"fs={heart['sample_rate_hz']:.3f} Hz win={heart['window_length']}"
                )
            elif tlv_type == MMWDEMO_OUTPUT_MSG_HEART_RATE_DEBUG:
                if len(payload) != struct.calcsize("<20f10H"):
                    print(
                        f"[DATA] Frame {header['frame_number']} subFrame {header['subframe_number']} "
                        f"heart-rate debug TLV length mismatch: {len(payload)}"
                    )
                    continue

                debug = parse_heart_rate_debug_payload(payload)
                heart_rate_debug_found = True
                heart_rate_debug_writer.writerow(
                    {
                        "frame_number": header["frame_number"],
                        "subframe_number": header["subframe_number"],
                        "time_cpu_cycles": header["time_cpu_cycles"],
                        **debug,
                    }
                )
                heart_rate_debug_csv.flush()
                print(
                    f"[DBG] frame={header['frame_number']} subFrame={header['subframe_number']} "
                    f"bestBin={debug['best_range_bin']} selBin={debug['selected_range_bin']} "
                    f"gateChanged={debug['gate_changed']} bestScore={debug['best_score']:.3f} "
                    f"selScore={debug['selected_score']:.3f} "
                    f"guide={debug['guide_freq']:.3f} vmeGuide={debug['vme_guide_freq']:.3f} "
                    f"coarse={debug['coarse_freq']:.3f} runner={debug['runner_up_freq']:.3f} "
                    f"fine={debug['fine_freq']:.3f} tracked={debug['tracked_freq']:.3f} "
                    f"guidePk={debug['guide_peak_mag']:.3f} coarsePk={debug['coarse_peak_mag']:.3f} "
                    f"runnerPk={debug['runner_up_peak_mag']:.3f} finePk={debug['fine_peak_mag']:.3f} "
                    f"trackedPk={debug['tracked_peak_mag']:.3f} "
                    f"sigP={debug['signal_power']:.3f} sampP={debug['sample_power_mean']:.3f} "
                    f"thr={debug['power_threshold']:.3f} mtiAlpha={debug['mti_alpha']:.5f} "
                    f"vmeAlpha={debug['vme_alpha']:.1f} vmeIter={debug['vme_iterations']} "
                    f"vmeErr={debug['vme_last_rel_err']:.6f} trackSel={debug['track_selected']} "
                    f"stepLim={debug['step_limited']} "
                    f"range={debug['selected_range_meters']:.3f} m filled={debug['is_filled']} "
                    f"samples={debug['sample_count']}/{debug['window_length']} valid={debug['valid']}"
                )

        if (not heart_rate_found) and (not heart_rate_debug_found):
            print(
                f"[DATA] frame={header['frame_number']} subFrame={header['subframe_number']} "
                f"numTLVs={header['num_tlvs']} no heart-rate TLV"
            )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Send try.cfg on COM4 and parse heart-rate TLV from COM3."
    )
    parser.add_argument(
        "--cfg-port",
        default=DEFAULT_CFG_PORT,
        help=f"CLI/config UART port, default: {DEFAULT_CFG_PORT}",
    )
    parser.add_argument(
        "--data-port",
        default=DEFAULT_DATA_PORT,
        help=f"Data UART port, default: {DEFAULT_DATA_PORT}",
    )
    parser.add_argument(
        "--cfg-baud",
        type=int,
        default=DEFAULT_CFG_BAUD,
        help=f"CLI/config baudrate, default: {DEFAULT_CFG_BAUD}",
    )
    parser.add_argument(
        "--data-baud",
        type=int,
        default=DEFAULT_DATA_BAUD,
        help=f"Data baudrate, default: {DEFAULT_DATA_BAUD}",
    )
    parser.add_argument(
        "--cfg",
        default="try.cfg",
        help="Path to cfg file, default: try.cfg",
    )
    parser.add_argument(
        "--cmd-delay",
        type=float,
        default=0.08,
        help="Delay between cfg commands in seconds, default: 0.08",
    )
    parser.add_argument(
        "--output-dir",
        default="captures",
        help="Directory used to store raw UART data and parsed CSV logs, default: captures",
    )
    parser.add_argument(
        "--idle-log-interval",
        type=float,
        default=2.0,
        help="Seconds between UART wait diagnostics when no full frame is received, default: 2.0",
    )
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    cfg_path = Path(args.cfg).resolve()
    if not cfg_path.exists():
        print(f"CFG file not found: {cfg_path}", file=sys.stderr)
        return 1

    cfg_lines = load_cfg_lines(cfg_path)
    if not cfg_lines:
        print(f"CFG file is empty: {cfg_path}", file=sys.stderr)
        return 1

    try:
        output_dir = Path(args.output_dir).resolve()
        capture_dir = create_capture_dir(output_dir, cfg_path)
        print(f"[SAVE] Capture directory: {capture_dir}")

        with ExitStack() as stack:
            data_rx_buffer = bytearray()
            cfg_rx_buffer = bytearray()
            raw_file = stack.enter_context((capture_dir / "uart_raw.bin").open("ab"))
            heart_rate_csv, heart_rate_writer = open_csv_writer(
                stack,
                capture_dir / "heart_rate.csv",
                HEART_RATE_FIELDS,
            )
            heart_rate_debug_csv, heart_rate_debug_writer = open_csv_writer(
                stack,
                capture_dir / "heart_rate_debug.csv",
                HEART_RATE_DEBUG_FIELDS,
            )
            data_ser = stack.enter_context(open_serial(args.data_port, args.data_baud, timeout=0.1))
            data_ser.reset_input_buffer()
            data_ser.reset_output_buffer()

            cfg_ser = stack.enter_context(open_serial(args.cfg_port, args.cfg_baud, timeout=0.2))
            cfg_ser.reset_input_buffer()
            cfg_ser.reset_output_buffer()
            print(f"[DATA] Priming {data_ser.port} before sensorStart ...")
            send_cfg(cfg_ser, cfg_lines, args.cmd_delay)
            drain_data_serial(data_ser, data_rx_buffer)
            drain_text_serial(cfg_ser, cfg_rx_buffer, "[CLI]")
            monitor_data(
                data_ser,
                cfg_ser,
                raw_file,
                heart_rate_writer,
                heart_rate_csv,
                heart_rate_debug_writer,
                heart_rate_debug_csv,
                data_rx_buffer,
                cfg_rx_buffer,
                args.idle_log_interval,
            )
    except serial.SerialException as exc:
        print(f"Serial error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nStopped by user.")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
