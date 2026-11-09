from PyQt6.QtCore import QThread, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from gui.worker import SLMPWorker


class MainWindow(QMainWindow):
    requestConnect = pyqtSignal(str, int)
    requestDisconnect = pyqtSignal()
    requestSetTarget = pyqtSignal(str, int)
    requestReadOnce = pyqtSignal()
    requestStartPolling = pyqtSignal(int)
    requestStopPolling = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mitsubishi PLC SLMP 3E Monitor")
        self.resize(420, 340)

        self._build_ui()
        self._start_worker()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        conn_box = QGroupBox("PLC 연결")
        form = QFormLayout(conn_box)
        self.ip_edit = QLineEdit("192.168.0.10")
        self.port_edit = QLineEdit("5007")
        form.addRow("IP 주소", self.ip_edit)
        form.addRow("포트", self.port_edit)
        root.addWidget(conn_box)

        btn_row = QHBoxLayout()
        self.connect_btn = QPushButton("연결")
        self.disconnect_btn = QPushButton("연결 해제")
        self.disconnect_btn.setEnabled(False)
        btn_row.addWidget(self.connect_btn)
        btn_row.addWidget(self.disconnect_btn)
        root.addLayout(btn_row)

        device_box = QGroupBox("읽기 대상")
        dform = QFormLayout(device_box)
        self.device_edit = QLineEdit("D")
        self.head_no_spin = QSpinBox()
        self.head_no_spin.setRange(0, 65535)
        self.head_no_spin.setValue(100)
        dform.addRow("디바이스", self.device_edit)
        dform.addRow("번호", self.head_no_spin)
        root.addWidget(device_box)

        poll_row = QHBoxLayout()
        self.auto_check = QCheckBox("자동 갱신")
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(100, 60000)
        self.interval_spin.setSingleStep(100)
        self.interval_spin.setValue(1000)
        self.interval_spin.setSuffix(" ms")
        self.read_once_btn = QPushButton("한 번 읽기")
        self.read_once_btn.setEnabled(False)
        poll_row.addWidget(self.auto_check)
        poll_row.addWidget(self.interval_spin)
        poll_row.addWidget(self.read_once_btn)
        root.addLayout(poll_row)

        self.value_label = QLabel("D100 = ---")
        self.value_label.setStyleSheet(
            "font-size: 36px; font-weight: bold; qproperty-alignment: AlignCenter;"
        )
        root.addWidget(self.value_label)

        self.status_label = QLabel("연결되지 않음")
        root.addWidget(self.status_label)

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
