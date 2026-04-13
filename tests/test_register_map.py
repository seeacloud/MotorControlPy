"""单元测试 - 寄存器映射"""

import pytest
from protocol.register_map import (
    REGISTERS, RegisterDef, DataType, Access, OperationMode,
    encode_value, decode_value, get_register_by_address,
)


class TestRegisterDef:
    """RegisterDef 属性测试"""

    def test_16bit_reg_count(self):
        reg = REGISTERS["control_word"]
        assert reg.reg_count == 1

    def test_32bit_reg_count(self):
        reg = REGISTERS["actual_position"]
        assert reg.reg_count == 2

    def test_signed_int16(self):
        reg = REGISTERS["operation_mode"]
        assert reg.is_signed is True
        assert reg.is_32bit is False

    def test_unsigned_uint16(self):
        reg = REGISTERS["error"]
        assert reg.is_signed is False
        assert reg.is_32bit is False

    def test_signed_int32(self):
        reg = REGISTERS["actual_position"]
        assert reg.is_signed is True
        assert reg.is_32bit is True


class TestEncodeDecodeValue:
    """缩放编解码测试"""

    def test_encode_with_scale(self):
        reg = REGISTERS["target_speed"]  # scale=10.0
        assert encode_value(reg, 5.0) == 50

    def test_decode_with_scale(self):
        reg = REGISTERS["target_speed"]
        assert decode_value(reg, 50) == 5.0

    def test_encode_no_scale(self):
        reg = REGISTERS["control_word"]  # scale=1.0
        assert encode_value(reg, 15) == 15

    def test_decode_no_scale(self):
        reg = REGISTERS["control_word"]
        assert decode_value(reg, 15) == 15

    @pytest.mark.parametrize("value", [0.0, 1.5, 10.0, 100.0])
    def test_roundtrip(self, value):
        reg = REGISTERS["acceleration"]  # scale=10.0
        encoded = encode_value(reg, value)
        decoded = decode_value(reg, encoded)
        assert decoded == value


class TestGetRegisterByAddress:
    """地址查找测试"""

    def test_find_existing(self):
        reg = get_register_by_address(0x6040)
        assert reg is not None
        assert reg.name_en == "control_word"

    def test_find_nonexistent(self):
        assert get_register_by_address(0x9999) is None


class TestOperationMode:
    """操作模式枚举测试"""

    def test_values(self):
        assert OperationMode.POSITION == 1
        assert OperationMode.SPEED == 3
        assert OperationMode.TORQUE == 4
        assert OperationMode.HOMING == 6
