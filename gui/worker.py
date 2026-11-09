from PyQt6.QtCore import QObject, QTimer, pyqtSignal, pyqtSlot

from slmp.client import SLMP3EClient, SLMPError


class SLMPWorker(QObject):
    """Runs all PLC I/O on a dedicated thread so the GUI thread never blocks."""

    connected = pyqtSignal()
    disconnected = pyqtSignal()
    valueRead = pyqtSignal(str, int, int)  # device, head_no, value
    errorOccurred = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.client: SLMP3EClient | None = None
        self.host = "192.168.0.10"
        self.port = 5007
        self.device = "D"
        self.head_no = 100
        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self._poll)

    @pyqtSlot(str, int)
    def connect_with(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        try:
            client = SLMP3EClient(host, port)
            client.connect()
        except OSError as exc:
            self.errorOccurred.emit(f"연결 실패: {exc}")
            return
        self.client = client
        self.connected.emit()

    @pyqtSlot()
    def disconnect_plc(self) -> None:
        self.poll_timer.stop()
        if self.client is not None:
            self.client.close()
            self.client = None
        self.disconnected.emit()

    @pyqtSlot(str, int)
    def set_target(self, device: str, head_no: int) -> None:
        self.device = device
        self.head_no = head_no

    @pyqtSlot()
    def read_once(self) -> None:
        self._poll()

    @pyqtSlot(int)
    def start_polling(self, interval_ms: int) -> None:
        self.poll_timer.start(interval_ms)

    @pyqtSlot()
    def stop_polling(self) -> None:
        self.poll_timer.stop()

    def _poll(self) -> None:
        if self.client is None:
            return
        try:
            value = self.client.read_word_signed(self.device, self.head_no)
        except (SLMPError, OSError) as exc:
            self.errorOccurred.emit(str(exc))
            self.poll_timer.stop()
            return
        self.valueRead.emit(self.device, self.head_no, value)
