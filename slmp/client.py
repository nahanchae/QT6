"""Mitsubishi MELSEC SLMP (MC protocol) client, binary 3E frame, over TCP."""

import socket
import struct

# Device codes for the binary 3E frame (1 byte each).
DEVICE_CODES = {
    "SM": 0x91, "SD": 0xA9,
    "X": 0x9C, "Y": 0x9D,
    "M": 0x90, "L": 0x92, "F": 0x93, "V": 0x94,
    "B": 0xA0, "D": 0xA8, "W": 0xB4, "R": 0xAF, "ZR": 0xB0,
    "TS": 0xC1, "TC": 0xC0, "TN": 0xC2,
    "CS": 0xC4, "CC": 0xC3, "CN": 0xC5,
}

_READ_WORDS_COMMAND = 0x0401
_WORD_UNITS_SUBCOMMAND = 0x0000


class SLMPError(Exception):
    """Raised when the PLC returns a non-zero completion/error code."""

    def __init__(self, code: int):
        self.code = code
        super().__init__(f"PLC returned error code 0x{code:04X}")


class SLMP3EClient:
    """Minimal synchronous client for reading word devices via a binary 3E frame."""

    def __init__(
        self,
        host: str,
        port: int = 5007,
        network_no: int = 0x00,
        pc_no: int = 0xFF,
        dest_module_io: int = 0x03FF,
        dest_module_station: int = 0x00,
        monitoring_timer: int = 0x0010,
        timeout: float = 3.0,
    ):
        self.host = host
        self.port = port
        self.network_no = network_no
        self.pc_no = pc_no
        self.dest_module_io = dest_module_io
        self.dest_module_station = dest_module_station
        self.monitoring_timer = monitoring_timer
        self.timeout = timeout
        self._sock: socket.socket | None = None

    def connect(self) -> None:
        self._sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        self._sock.settimeout(self.timeout)

    def close(self) -> None:
        if self._sock is not None:
            self._sock.close()
            self._sock = None

    def __enter__(self) -> "SLMP3EClient":
        self.connect()
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    @property
    def is_connected(self) -> bool:
        return self._sock is not None

    def read_words(self, device: str, head_no: int, count: int = 1) -> list[int]:
        """Read `count` consecutive word devices starting at `head_no` (e.g. device='D')."""
        device_code = DEVICE_CODES[device.upper()]
        request_data = (
            struct.pack("<I", head_no)[:3]
            + struct.pack("B", device_code)
            + struct.pack("<H", count)
        )
        response = self._send_command(_READ_WORDS_COMMAND, _WORD_UNITS_SUBCOMMAND, request_data)
        return list(struct.unpack(f"<{count}H", response[: count * 2]))

    def read_word(self, device: str, head_no: int) -> int:
        """Read one word device as an unsigned 16-bit value."""
        return self.read_words(device, head_no, 1)[0]

    def read_word_signed(self, device: str, head_no: int) -> int:
        """Read one word device as a signed 16-bit value (common for D registers)."""
        value = self.read_word(device, head_no)
        return value - 0x10000 if value >= 0x8000 else value

    def _send_command(self, command: int, subcommand: int, data: bytes) -> bytes:
        if self._sock is None:
            raise ConnectionError("Not connected to PLC")
        request_data = struct.pack("<HH", command, subcommand) + data
        frame = self._build_request_header(request_data) + request_data
        self._sock.sendall(frame)
        return self._receive_response()

    def _build_request_header(self, request_data: bytes) -> bytes:
        # 3E frame, binary code, no serial-number control (subheader 0x0050).
        request_data_length = len(request_data) + 2  # +2 for the monitoring timer below
        return (
            struct.pack("<H", 0x0050)
            + struct.pack("B", self.network_no)
            + struct.pack("B", self.pc_no)
            + struct.pack("<H", self.dest_module_io)
            + struct.pack("B", self.dest_module_station)
            + struct.pack("<H", request_data_length)
            + struct.pack("<H", self.monitoring_timer)
        )

    def _receive_response(self) -> bytes:
        header = self._recv_exact(9)
        response_data_length = struct.unpack("<H", header[7:9])[0]
        body = self._recv_exact(response_data_length)
        completion_code = struct.unpack("<H", body[0:2])[0]
        if completion_code != 0:
            raise SLMPError(completion_code)
        return body[2:]

    def _recv_exact(self, size: int) -> bytes:
        buf = bytearray()
        while len(buf) < size:
            chunk = self._sock.recv(size - len(buf))
            if not chunk:
                raise ConnectionError("PLC closed the connection")
            buf += chunk
        return bytes(buf)
