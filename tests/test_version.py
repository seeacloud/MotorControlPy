"""应用版本测试。"""

from version import APP_VERSION, __version__


def test_current_version():
    assert APP_VERSION == "6.0"
    assert __version__ == APP_VERSION
