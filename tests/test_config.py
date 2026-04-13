"""单元测试 - 配置管理"""

import json
import pytest
from config import AppConfig


@pytest.fixture
def tmp_config(tmp_path):
    """创建临时配置文件"""
    cfg_file = tmp_path / "config.json"
    return AppConfig(str(cfg_file))


class TestAppConfigDefaults:
    """默认配置测试"""

    def test_serial_defaults(self, tmp_config):
        assert tmp_config.serial_port == "COM7"
        assert tmp_config.serial_baudrate == 57600
        assert tmp_config.serial_slave_id == 1

    def test_motion_defaults(self, tmp_config):
        assert tmp_config.move_speed == 5.0
        assert tmp_config.move_accel == 10.0
        assert tmp_config.move_decel == 10.0

    def test_homing_defaults(self, tmp_config):
        assert tmp_config.homing_method_ccw == 2
        assert tmp_config.homing_method_cw == 1

    def test_conversion_default(self, tmp_config):
        assert tmp_config.pulse_per_mm == 250.0

    def test_udp_defaults(self, tmp_config):
        assert tmp_config.udp_listen_port == 6667
        assert tmp_config.udp_send_port == 6666

    def test_toggle_defaults(self, tmp_config):
        assert tmp_config.toggle_auto_init is True
        assert tmp_config.toggle_broadcast is True


class TestAppConfigPersistence:
    """配置持久化测试"""

    def test_save_and_reload(self, tmp_path):
        cfg_file = str(tmp_path / "config.json")
        cfg1 = AppConfig(cfg_file)
        cfg1.toggle_auto_init = False
        cfg1.start_point = 3

        cfg2 = AppConfig(cfg_file)
        assert cfg2.toggle_auto_init is False
        assert cfg2.start_point == 3

    def test_points_persistence(self, tmp_path):
        cfg_file = str(tmp_path / "config.json")
        cfg1 = AppConfig(cfg_file)
        cfg1.points = [{"name": "P-01", "position_mm": 100.0}]

        cfg2 = AppConfig(cfg_file)
        assert len(cfg2.points) == 1
        assert cfg2.points[0]["position_mm"] == 100.0

    def test_load_existing_config(self, tmp_path):
        cfg_file = tmp_path / "config.json"
        cfg_file.write_text(json.dumps({
            "serial": {"port": "COM3", "baudrate": 115200, "slave_id": 2, "timeout": 1.0}
        }))
        cfg = AppConfig(str(cfg_file))
        assert cfg.serial_port == "COM3"
        assert cfg.serial_baudrate == 115200
        # 其他字段应使用默认值
        assert cfg.move_speed == 5.0

    def test_merge_preserves_existing(self, tmp_path):
        cfg_file = tmp_path / "config.json"
        cfg_file.write_text(json.dumps({
            "motion": {"speed": 20.0, "accel": 10.0, "decel": 10.0},
            "custom_field": "should_survive"
        }))
        cfg = AppConfig(str(cfg_file))
        assert cfg.move_speed == 20.0
        # 自定义字段应保留
        assert cfg._data["custom_field"] == "should_survive"
