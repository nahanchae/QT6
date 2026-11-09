import os

from PyQt6 import uic
from PyQt6.QtCore import QThread, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import QMainWindow

from gui.worker import SLMPWorker

_UI_PATH = os.path.join(os.path.dirname(__file__), "main_window.ui")


class MainWindow(QMainWindow):
    requestConnect = pyqtSignal(str, int)
    requestDisconnect = pyqtSignal()
    requestSetTarget = pyqtSignal(str, int)
    requestReadOnce = pyqtSignal()
    requestStartPolling = pyqtSignal(int)
    requestStopPolling = pyqtSignal()

    def __init__(self):
        super().__init__()
        uic.loadUi(_UI_PATH, self)

        self._wire_ui()
        self._start_worker()

    def _wire_ui(self) -> None:
        self.connect_btn.clicked.connect(self.on_connect_clicked)
        self.disconnect_btn.clicked.connect(self.on_disconnect_clicked)
        self.read_once_btn.clicked.connect(self.on_read_once_clicked)
        self.auto_check.toggled.connect(self.on_auto_toggled)
        self.interval_spin.valueChanged.connect(self.on_interval_changed)

    def _start_worker(self) -> None:
        self.thread = QThread(self)
        self.worker = SLMPWorker()
        self.worker.moveToThread(self.thread)

        self.requestConnect.connect(self.worker.connect_with)
        self.requestDisconnect.connect(self.worker.disconnect_plc)
        self.requestSetTarget.connect(self.worker.set_target)
        self.requestReadOnce.connect(self.worker.read_once)
        self.requestStartPolling.connect(self.worker.start_polling)
        self.requestStopPolling.connect(self.worker.stop_polling)

        self.worker.connected.connect(self.on_connected)
        self.worker.disconnected.connect(self.on_disconnected)
        self.worker.valueRead.connect(self.on_value_read)
        self.worker.errorOccurred.connect(self.on_error)

        self.thread.start()

    def _push_target(self) -> None:
        device = self.device_edit.text().strip().upper() or "D"
        head_no = self.head_no_spin.value()
        self.requestSetTarget.emit(device, head_no)

    def on_connect_clicked(self) -> None:
        host = self.ip_edit.text().strip()
        try:
            port = int(self.port_edit.text().strip())
        except ValueError:
            self.status_label.setText("포트 번호가 올바르지 않습니다.")
            return
        self.requestConnect.emit(host, port)

    def on_disconnect_clicked(self) -> None:
        self.requestStopPolling.emit()
        self.requestDisconnect.emit()

    def on_read_once_clicked(self) -> None:
        self._push_target()
        self.requestReadOnce.emit()

    def on_auto_toggled(self, checked: bool) -> None:
        if checked:
            self._push_target()
            self.requestStartPolling.emit(self.interval_spin.value())
        else:
            self.requestStopPolling.emit()

    def on_interval_changed(self, value: int) -> None:
        if self.auto_check.isChecked():
            self.requestStartPolling.emit(value)

    @pyqtSlot()
    def on_connected(self) -> None:
        self.status_label.setText(f"{self.ip_edit.text()}:{self.port_edit.text()} 연결됨")
        self.connect_btn.setEnabled(False)
        self.disconnect_btn.setEnabled(True)
        self.read_once_btn.setEnabled(True)
        self._push_target()
        if self.auto_check.isChecked():
            self.requestStartPolling.emit(self.interval_spin.value())

    @pyqtSlot()
    def on_disconnected(self) -> None:
        self.status_label.setText("연결 해제됨")
        self.connect_btn.setEnabled(True)
        self.disconnect_btn.setEnabled(False)
        self.read_once_btn.setEnabled(False)

    @pyqtSlot(str, int, int)
    def on_value_read(self, device: str, head_no: int, value: int) -> None:
        self.value_label.setText(f"{device}{head_no} = {value}")
        self.status_label.setText("정상적으로 읽음")

    @pyqtSlot(str)
    def on_error(self, message: str) -> None:
        self.status_label.setText(f"오류: {message}")

    def closeEvent(self, event) -> None:
        self.requestStopPolling.emit()
        self.requestDisconnect.emit()
        self.thread.quit()
        self.thread.wait(2000)
        super().closeEvent(event)
