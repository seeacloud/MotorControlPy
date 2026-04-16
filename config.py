"""应用配置 - 从config.json加载，支持热更新"""

import json
import os

CONFIG_FILE = "config.json"

# 默认配置
_DEFAULTS = {
    "serial": {
        "port": "COM7",
        "baudrate": 57600,
        "slave_id": 1,
        "timeout": 0.5
    },
    "motion": {
        "speed": 5.0,
        "accel": 10.0,
        "decel": 10.0
    },
    "homing": {
        "method_cw": 1,
        "method_ccw": 2,
        "speed": 100,
        "accel": 10.0,
        "offset": 3000
    },
    "conversion": {
        "pulse_per_mm": 250.0
    },
    "points": [],
    "startPoint": 0,
    "distTolerance": 10,
    "udp": {
        "listen_port": 6667,
        "send_port": 6666
    },
    "polling": {
        "fast_ms": 100,
        "slow_ms": 500
    },
    "auto_init_delay_ms": 1000,
    "toggles": {
        "auto_init": True,
        "broadcast_position": True
    }
}


class AppConfig:
    """从config.json加载配置，不存在则创建默认配置。"""

    def __init__(self, filepath: str = CONFIG_FILE):
        self._filepath = filepath
        self._data: dict = {}
        self.load()

    def load(self):
        if os.path.exists(self._filepath):
            try:
                with open(self._filepath, 'r', encoding='utf-8') as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._data = {}
        # 合并默认值(不覆盖已有)
        self._data = self._merge(_DEFAULTS, self._data)
        self.save()

    def save(self):
        try:
            with open(self._filepath, 'w', encoding='utf-8') as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except IOError:
            pass

    def _merge(self, defaults: dict, override: dict) -> dict:
        result = dict(defaults)
        for k, v in override.items():
            if k in result and isinstance(result[k], dict) and isinstance(v, dict):
                result[k] = self._merge(result[k], v)
            else:
                result[k] = v
        return result

    # === 便捷属性 ===
    @property
    def serial_port(self) -> str: return self._data["serial"]["port"]
    @property
    def serial_baudrate(self) -> int: return self._data["serial"]["baudrate"]
    @property
    def serial_slave_id(self) -> int: return self._data["serial"]["slave_id"]
    @property
    def serial_timeout(self) -> float: return self._data["serial"]["timeout"]

    @property
    def move_speed(self) -> float: return self._data["motion"]["speed"]
    @move_speed.setter
    def move_speed(self, val: float):
        self._data["motion"]["speed"] = val
        self.save()
    @property
    def move_accel(self) -> float: return self._data["motion"]["accel"]
    @property
    def move_decel(self) -> float: return self._data["motion"]["decel"]

    @property
    def homing_method_cw(self) -> int: return self._data["homing"]["method_cw"]
    @property
    def homing_method_ccw(self) -> int: return self._data["homing"]["method_ccw"]
    @property
    def homing_speed(self) -> int: return self._data["homing"]["speed"]
    @property
    def homing_accel(self) -> float: return self._data["homing"]["accel"]
    @property
    def homing_offset(self) -> int: return self._data["homing"]["offset"]

    @property
    def pulse_per_mm(self) -> float: return self._data["conversion"]["pulse_per_mm"]

    @property
    def points(self) -> list[dict]: return self._data.get("points", [])
    @points.setter
    def points(self, val: list[dict]):
        self._data["points"] = val
        self.save()

    @property
    def start_point(self) -> int: return self._data.get("startPoint", 0)
    @start_point.setter
    def start_point(self, val: int):
        self._data["startPoint"] = val
        self.save()

    @property
    def dist_tolerance(self) -> float: return self._data.get("distTolerance", 10)

    @property
    def udp_listen_port(self) -> int: return self._data["udp"]["listen_port"]
    @property
    def udp_send_port(self) -> int: return self._data["udp"]["send_port"]

    @property
    def auto_init_delay_ms(self) -> int: return self._data.get("auto_init_delay_ms", 1000)
    @property
    def fast_poll_ms(self) -> int: return self._data["polling"]["fast_ms"]
    @property
    def slow_poll_ms(self) -> int: return self._data["polling"]["slow_ms"]

    @property
    def toggle_auto_init(self) -> bool: return self._data.get("toggles", {}).get("auto_init", True)
    @toggle_auto_init.setter
    def toggle_auto_init(self, val: bool):
        self._data.setdefault("toggles", {})["auto_init"] = val
        self.save()

    @property
    def toggle_broadcast(self) -> bool: return self._data.get("toggles", {}).get("broadcast_position", True)
    @toggle_broadcast.setter
    def toggle_broadcast(self, val: bool):
        self._data.setdefault("toggles", {})["broadcast_position"] = val
        self.save()
