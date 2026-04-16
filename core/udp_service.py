"""UDP通信服务 - 发送点位到达通知和实时位置"""

import socket
import logging
from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtSlot, QTimer
from PyQt6.QtNetwork import QUdpSocket, QHostAddress

logger = logging.getLogger(__name__)


class UdpService(QObject):
    """UDP收发服务: 监听6667，发送到广播6666。

    收发分离：接收用 _recv_socket，发送用 _send_socket，
    避免高频发送位置数据时阻塞接收。
    """

    message_received = pyqtSignal(str)

    def __init__(self, listen_port: int = 6667, send_port: int = 6666, parent=None):
        super().__init__(parent)
        self._listen_port = listen_port
        self._send_port = send_port

        # 接收 socket
        self._recv_socket = QUdpSocket(self)
        self._recv_socket.readyRead.connect(self._on_ready_read)
        self._recv_socket.errorOccurred.connect(self._on_recv_error)

        # 发送 socket（独立，不绑定端口）
        self._send_socket = QUdpSocket(self)

        self._bound = False

        # 健康检查定时器：每30秒检查一次 socket 状态
        self._health_timer = QTimer(self)
        self._health_timer.timeout.connect(self._health_check)

    def start(self):
        if not self._bound:
            ok = self._recv_socket.bind(
                QHostAddress.SpecialAddress.AnyIPv4, self._listen_port
            )
            if ok:
                self._bound = True
                self._health_timer.start(30000)
                logger.info(f"UDP监听端口 {self._listen_port}")
            else:
                logger.error(f"UDP绑定端口 {self._listen_port} 失败")

    def stop(self):
        self._health_timer.stop()
        if self._bound:
            self._recv_socket.close()
            self._bound = False
        self._send_socket.close()

    def send_broadcast(self, message: str):
        """广播发送消息到局域网"""
        data = message.encode('utf-8')
        self._send_socket.writeDatagram(
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
        while self._recv_socket.hasPendingDatagrams():
            data, host, port = self._recv_socket.readDatagram(
                int(self._recv_socket.pendingDatagramSize())
            )
            msg = bytes(data).decode('utf-8', errors='replace')
            self.message_received.emit(msg)

    def _on_recv_error(self, error):
        logger.error(f"UDP接收socket错误: {error}, 尝试重新绑定")
        self._try_rebind()

    def _health_check(self):
        """定期检查接收socket状态，异常时重新绑定"""
        if not self._bound:
            return
        state = self._recv_socket.state()
        if state != QUdpSocket.SocketState.BoundState:
            logger.warning(f"UDP接收socket状态异常: {state}, 重新绑定")
            self._try_rebind()

    def _try_rebind(self):
        """重新绑定接收socket"""
        self._recv_socket.close()
        self._bound = False
        # 重新创建 socket（彻底清理旧状态）
        self._recv_socket = QUdpSocket(self)
        self._recv_socket.readyRead.connect(self._on_ready_read)
        self._recv_socket.errorOccurred.connect(self._on_recv_error)
        ok = self._recv_socket.bind(
            QHostAddress.SpecialAddress.AnyIPv4, self._listen_port
        )
        if ok:
            self._bound = True
            logger.info(f"UDP重新绑定端口 {self._listen_port} 成功")
        else:
            logger.error(f"UDP重新绑定端口 {self._listen_port} 失败")
