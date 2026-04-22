#!/usr/bin/env python3
import argparse
import struct
import sys
import time
from pathlib import Path

import serial


MAGIC_WORD = b"\x02\x01\x04\x03\x06\x05\x08\x07"
HEADER_LEN = 40
TLV_HEADER_LEN = 8

MMWDEMO_OUTPUT_MSG_HEART_RATE = 1001

DEFAULT_CFG_PORT = "COM4"
DEFAULT_DATA_PORT = "COM3"
DEFAULT_CFG_BAUD = 115200
DEFAULT_DATA_BAUD = 921600


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
    total_packet_len = header["total_packet_len"]
    if total_packet_len < HEADER_LEN:
        del rx_buffer[:len(MAGIC_WORD)]
        return None

    if len(rx_buffer) < total_packet_len:
        return None

    frame = bytes(rx_buffer[:total_packet_len])
    del rx_buffer[:total_packet_len]
    return frame


def parse_tlvs(frame: bytes) -> tuple[dict[str, int], list[tuple[int, bytes]]]:
    header = parse_frame_header(frame[:HEADER_LEN])
    offset = HEADER_LEN
    tlvs: list[tuple[int, bytes]] = []

    for _ in range(header["num_tlvs"]):
        if offset + TLV_HEADER_LEN > len(frame):
            break

        tlv_type, tlv_length = struct.unpack("<2I", frame[offset:offset + TLV_HEADER_LEN])
        offset += TLV_HEADER_LEN

        if offset + tlv_length > len(frame):
            break

        payload = frame[offset:offset + tlv_length]
        offset += tlv_length
        tlvs.append((tlv_type, payload))

    return header, tlvs


def monitor_data(data_ser: serial.Serial) -> None:
    rx_buffer = bytearray()
    print(f"[DATA] Listening on {data_ser.port} @ {data_ser.baudrate} ...")

    while True:
        frame = read_one_frame(data_ser, rx_buffer)
        if frame is None:
            continue

        header, tlvs = parse_tlvs(frame)
        heart_rate_found = False

        for tlv_type, payload in tlvs:
            if tlv_type != MMWDEMO_OUTPUT_MSG_HEART_RATE:
                continue

            if len(payload) != struct.calcsize("<5f4H"):
                print(
                    f"[DATA] Frame {header['frame_number']} subFrame {header['subframe_number']} "
                    f"heart-rate TLV length mismatch: {len(payload)}"
                )
                continue

            heart = parse_heart_rate_payload(payload)
            heart_rate_found = True
            print(
                f"[HR] frame={header['frame_number']} subFrame={header['subframe_number']} "
                f"valid={heart['valid']} bpm={heart['heart_rate_bpm']:.2f} "
                f"hz={heart['heart_rate_hz']:.3f} conf={heart['confidence']:.3f} "
                f"gate={heart['selected_range_bin']} range={heart['range_meters']:.3f} m "
                f"fs={heart['sample_rate_hz']:.3f} Hz win={heart['window_length']}"
            )

        if not heart_rate_found:
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
        with open_serial(args.cfg_port, args.cfg_baud, timeout=0.2) as cfg_ser:
            send_cfg(cfg_ser, cfg_lines, args.cmd_delay)

        time.sleep(0.5)

        with open_serial(args.data_port, args.data_baud, timeout=0.1) as data_ser:
            data_ser.reset_input_buffer()
            monitor_data(data_ser)
    except serial.SerialException as exc:
        print(f"Serial error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nStopped by user.")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
