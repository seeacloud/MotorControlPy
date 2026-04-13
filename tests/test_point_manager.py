"""单元测试 - 点位管理器"""

import sys
import pytest
from config import AppConfig

# session 级别 QApplication，避免 C++ 对象被提前回收
_app = None

def get_app():
    global _app
    if _app is None:
        from PyQt6.QtWidgets import QApplication
        _app = QApplication.instance() or QApplication(sys.argv)
    return _app


@pytest.fixture
def cfg(tmp_path):
    return AppConfig(str(tmp_path / "config.json"))


@pytest.fixture
def pm(cfg):
    get_app()
    from ui.point_manager import PointManager
    mgr = PointManager(cfg)
    yield mgr


class TestPointManager:
    """点位管理器测试"""

    def test_initial_empty(self, pm):
        assert pm.count == 0
        assert pm.get_all() == []

    def test_add_point(self, pm):
        pm.add(100.0)
        assert pm.count == 1
        p = pm.get(0)
        assert p["name"] == "P-01"
        assert p["position_mm"] == 100.0

    def test_add_multiple(self, pm):
        pm.add(100.0)
        pm.add(200.0)
        pm.add(300.0)
        assert pm.count == 3
        assert pm.get(2)["name"] == "P-03"

    def test_remove_point(self, pm):
        pm.add(100.0)
        pm.add(200.0)
        pm.remove(0)
        assert pm.count == 1
        assert pm.get(0)["position_mm"] == 200.0

    def test_remove_invalid_index(self, pm):
        pm.add(100.0)
        pm.remove(5)
        assert pm.count == 1

    def test_clear(self, pm):
        pm.add(100.0)
        pm.add(200.0)
        pm.clear()
        assert pm.count == 0

    def test_update_position(self, pm):
        pm.add(100.0)
        pm.update_position(0, 150.5)
        assert pm.get(0)["position_mm"] == 150.5

    def test_position_rounding(self, pm):
        pm.add(100.123456)
        assert pm.get(0)["position_mm"] == 100.1

    def test_persistence(self, cfg):
        get_app()
        from ui.point_manager import PointManager
        pm1 = PointManager(cfg)
        pm1.add(100.0)
        pm1.add(200.0)

        pm2 = PointManager(cfg)
        assert pm2.count == 2
        assert pm2.get(0)["position_mm"] == 100.0

    def test_get_out_of_range(self, pm):
        assert pm.get(-1) is None
        assert pm.get(0) is None
