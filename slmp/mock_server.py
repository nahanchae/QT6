"""A tiny SLMP (binary 3E frame) PLC simulator, for development without real hardware."""

import socket
import struct
import threading

_READ_WORDS_COMMAND = 0x0401
_WORD_UNITS_SUBCOMMAND = 0x0000
_COMMAND_ERROR = 0x4031


class MockSLMPServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 5007):
        self.host = host
        self.port = port
        self._words: dict[tuple[int, int], int] = {}
        self._lock = threading.Lock()
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((host, port))
        self.port = self._sock.getsockname()[1]
        self._sock.listen(5)
        self._running = False

    def set_word(self, device_code: int, head_no: int, value: int) -> None:
        with self._lock:
            self._words[(device_code, head_no)] = value & 0xFFFF

    def start(self) -> None:
        self._running = True
        threading.Thread(target=self._accept_loop, daemon=True).start()

    def stop(self) -> None:
        self._running = False
        try:
            self._sock.close()
        except OSError:
            pass

    def _accept_loop(self) -> None:
        while self._running:
            try:
                conn, _ = self._sock.accept()
            except OSError:
                return
            threading.Thread(target=self._handle_client, args=(conn,), daemon=True).start()

    def _handle_client(self, conn: socket.socket) -> None:
        with conn:
            while True:
                header = self._recv_exact(conn, 9)
                if header is None:
                    return
                # Remaining header bytes: request data length (already in `header`) + timer.
                timer = self._recv_exact(conn, 2)
                if timer is None:
                    return
                request_data_length = struct.unpack("<H", header[7:9])[0]
                body = self._recv_exact(conn, request_data_length - 2)
                if body is None:
                    return
                response_data = self._handle_request(body)
                response_header = header[0:7] + struct.pack("<H", len(response_data))
                conn.sendall(response_header + response_data)

    def _handle_request(self, body: bytes) -> bytes:
        command, subcommand = struct.unpack("<HH", body[0:4])
        data = body[4:]
        if command == _READ_WORDS_COMMAND and subcommand == _WORD_UNITS_SUBCOMMAND:
            head_no = int.from_bytes(data[0:3], "little")
            device_code = data[3]
            count = struct.unpack("<H", data[4:6])[0]
            with self._lock:
                values = b"".join(
                    struct.pack("<H", self._words.get((device_code, head_no + i), 0))
                    for i in range(count)
                )
            return struct.pack("<H", 0x0000) + values
        return struct.pack("<H", _COMMAND_ERROR)

    @staticmethod
    def _recv_exact(conn: socket.socket, size: int) -> bytes | None:
        buf = bytearray()
        while len(buf) < size:
            chunk = conn.recv(size - len(buf))
            if not chunk:
                return None
            buf += chunk
        return bytes(buf)
