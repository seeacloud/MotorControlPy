"""UDP通信服务 - 发送点位到达通知和实时位置"""

import socket
import logging
from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtSlot
from PyQt6.QtNetwork import QUdpSocket, QHostAddress

logger = logging.getLogger(__name__)


class UdpService(QObject):
    """UDP收发服务: 监听6667，发送到广播6666。"""

    message_received = pyqtSignal(str)

    def __init__(self, listen_port: int = 6667, send_port: int = 6666, parent=None):
        super().__init__(parent)
        self._listen_port = listen_port
        self._send_port = send_port
        self._socket = QUdpSocket(self)
        self._socket.readyRead.connect(self._on_ready_read)
        self._bound = False

    def start(self):
        if not self._bound:
            ok = self._socket.bind(QHostAddress.SpecialAddress.AnyIPv4, self._listen_port)
            if ok:
                self._bound = True
                logger.info(f"UDP监听端口 {self._listen_port}")
            else:
                logger.error(f"UDP绑定端口 {self._listen_port} 失败")

    def stop(self):
        if self._bound:
            self._socket.close()
            self._bound = False

    def send_broadcast(self, message: str):
        """广播发送消息到局域网"""
        data = message.encode('utf-8')
        self._socket.writeDatagram(
            data, QHostAddress(QHostAddress.SpecialAddress.Broadcast), self._send_port
        )

    def send_point_arrival(self, point_index: int):
        """发送点位到达通知: P1, P2, ..."""
        msg = f"P{point_index + 1}"
        self.send_broadcast(msg)
        logger.info(f"UDP发送: {msg}")

    def send_position(self, position_mm: float):
        """发送实时位置"""
        self.send_broadcast(f"{position_mm:.1f}")

    def _on_ready_read(self):
        while self._socket.hasPendingDatagrams():
            data, host, port = self._socket.readDatagram(
                int(self._socket.pendingDatagramSize())
            )
            msg = bytes(data).decode('utf-8', errors='replace')
            self.message_received.emit(msg)
