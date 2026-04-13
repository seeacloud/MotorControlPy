"""集成测试 - UDP 通信"""

import socket
import time
import pytest


@pytest.fixture
def udp_receiver():
    """创建 UDP 接收端，监听 6666 端口"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", 16666))  # 用非标准端口避免冲突
    sock.settimeout(2.0)
    yield sock
    sock.close()


@pytest.fixture
def udp_sender():
    """创建 UDP 发送端"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    yield sock
    sock.close()


class TestUdpCommunication:
    """UDP 收发集成测试（不依赖 Qt）"""

    def test_send_receive(self, udp_receiver, udp_sender):
        udp_sender.sendto(b"P1", ("127.0.0.1", 16666))
        data, addr = udp_receiver.recvfrom(1024)
        assert data == b"P1"

    def test_position_format(self, udp_receiver, udp_sender):
        position_mm = 123.4
        msg = f"{position_mm:.1f}"
        udp_sender.sendto(msg.encode(), ("127.0.0.1", 16666))
        data, _ = udp_receiver.recvfrom(1024)
        assert data.decode() == "123.4"

    def test_point_arrival_format(self, udp_receiver, udp_sender):
        for i in range(1, 5):
            msg = f"P{i}"
            udp_sender.sendto(msg.encode(), ("127.0.0.1", 16666))
            data, _ = udp_receiver.recvfrom(1024)
            assert data.decode() == f"P{i}"

    def test_command_receive(self, udp_sender):
        """模拟发送移动命令"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("0.0.0.0", 16667))
        sock.settimeout(2.0)
        try:
            udp_sender.sendto(b"1", ("127.0.0.1", 16667))
            data, _ = sock.recvfrom(1024)
            assert data == b"1"
        finally:
            sock.close()
