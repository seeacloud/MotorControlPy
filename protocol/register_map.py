"""JMC伺服驱动器寄存器映射定义"""

from dataclasses import dataclass, field
from enum import IntEnum
from protocol.data_types import split_32bit, combine_32bit


class DataType(IntEnum):
    UINT16 = 1
    INT16 = 2
    UINT32 = 3
    INT32 = 4


class Access(IntEnum):
    RO = 1
    WO = 2
    RW = 3


class OperationMode(IntEnum):
    POSITION = 1
    SPEED = 3
    TORQUE = 4
    HOMING = 6


@dataclass
class RegisterDef:
    address: int
    name_cn: str
    name_en: str
    data_type: DataType
    access: Access
    scale: float = 1.0       # 寄存器值 = 实际值 * scale
    unit: str = ""
    description: str = ""
    bit_fields: dict = field(default_factory=dict)

    @property
    def reg_count(self) -> int:
        return 2 if self.data_type in (DataType.UINT32, DataType.INT32) else 1

    @property
    def is_signed(self) -> bool:
        return self.data_type in (DataType.INT16, DataType.INT32)

    @property
    def is_32bit(self) -> bool:
        return self.data_type in (DataType.UINT32, DataType.INT32)


# === 控制字位域定义 ===
CONTROL_WORD_BITS = {
    0: "初始化设备",
    1: "使能电压(开ɲ车)",
    2: "快速停止",
    3: "操作使能",
    4: "位置/回零启动(上升沿)",
    5: "立即更新位置",
    6: "绝对(0)/相对(1)定位",
    7: "故障复位(上升沿)",
    8: "暂停(上升沿)/恢复(下降沿)",
    9: "连续运动(不停顿到下一段)",
}

# === 状态字位域定义 ===
STATUS_WORD_BITS = {
    0: "准备就绪",
    1: "初始化完成",
    2: "操作使能",
    3: "故障触发",
    4: "供电正常",
    5: "快速停止",
    6: "初始化状态",
    7: "报警",
    8: "暂停中",
    9: "运动标志",
    10: "到达标志",
    11: "回零/速度零标志",
    12: "速度到达/回零完成",
    13: "位置/速度限制",
    14: "CW正向限位",
    15: "CCW反向限位",
}

# === 错误寄存器位域定义 ===
ERROR_BITS = {
    0: "通用错误",
    1: "过流错误",
    2: "过压错误",
    3: "温度报警",
    4: "通讯错误",
    5: "位置超差",
    7: "编码器缺失",
}

# === 寄存器定义表 ===
REGISTERS: dict[str, RegisterDef] = {
    "error": RegisterDef(
        0x1001, "错误寄存器", "error_register",
        DataType.UINT16, Access.RO,
        bit_fields=ERROR_BITS,
    ),
    "device_info": RegisterDef(
        0x1008, "设备信息", "device_info",
        DataType.UINT16, Access.RO,
    ),
    "hw_version": RegisterDef(
        0x1009, "硬件版本", "hw_version",
        DataType.UINT16, Access.RO,
    ),
    "sw_version": RegisterDef(
        0x100A, "软件版本", "sw_version",
        DataType.UINT16, Access.RO,
    ),
    "word_order": RegisterDef(
        0x6000, "字序格式", "word_order",
        DataType.UINT16, Access.RW,
        description="32位寄存器高低位顺序: 0=高位在前, 1=低位在前",
    ),
    "control_word": RegisterDef(
        0x6040, "控制字", "control_word",
        DataType.UINT16, Access.WO,
        bit_fields=CONTROL_WORD_BITS,
    ),
    "status_word": RegisterDef(
        0x6041, "状态字", "status_word",
        DataType.UINT16, Access.RO,
        bit_fields=STATUS_WORD_BITS,
    ),
    "halt_option": RegisterDef(
        0x605A, "停止选项", "halt_option",
        DataType.INT16, Access.RW,
        description="1=当前减速停止, 2=快速停止减速, 3+=直接停止",
    ),
    "pause_option": RegisterDef(
        0x605D, "暂停选项", "pause_option",
        DataType.INT16, Access.RW,
    ),
    "operation_mode": RegisterDef(
        0x6060, "操作模式", "operation_mode",
        DataType.INT16, Access.WO,
        description="1=位置, 3=速度, 4=转矩, 6=回零",
    ),
    "mode_display": RegisterDef(
        0x6061, "模式显示", "mode_display",
        DataType.INT16, Access.RO,
    ),
    "actual_position": RegisterDef(
        0x6064, "实际位置", "actual_position",
        DataType.INT32, Access.RO, unit="pulse",
    ),
    "actual_speed": RegisterDef(
        0x606C, "实际速度", "actual_speed",
        DataType.INT32, Access.RO, unit="rps/min",
    ),
    "target_position": RegisterDef(
        0x607A, "目标位置", "target_position",
        DataType.INT32, Access.RW, unit="pulse",
    ),
    "home_offset": RegisterDef(
        0x607C, "原点偏移", "home_offset",
        DataType.INT32, Access.RW, unit="pulse",
    ),
    "target_speed": RegisterDef(
        0x6081, "目标速度", "target_speed",
        DataType.INT32, Access.RW, scale=10.0, unit="rps",
    ),
    "acceleration": RegisterDef(
        0x6083, "加速度", "acceleration",
        DataType.UINT16, Access.RW, scale=10.0, unit="rps/s²",
    ),
    "deceleration": RegisterDef(
        0x6084, "减速度", "deceleration",
        DataType.UINT16, Access.RW, scale=10.0, unit="rps/s²",
    ),
    "halt_deceleration": RegisterDef(
        0x6085, "停止减速度", "halt_deceleration",
        DataType.UINT16, Access.RW, scale=10.0, unit="rps/s²",
    ),
    "homing_method": RegisterDef(
        0x6098, "回零方式", "homing_method",
        DataType.INT16, Access.RW,
    ),
    "homing_speed": RegisterDef(
        0x6099, "回零速度", "homing_speed",
        DataType.UINT32, Access.RW, unit="rps",
        description="取值范围 0~100000",
    ),
    "homing_accel": RegisterDef(
        0x609A, "回零加减速", "homing_accel",
        DataType.UINT16, Access.RW, scale=10.0, unit="rps/s²",
    ),
    "homing_offset_speed": RegisterDef(
        0x609B, "偏移速度", "homing_offset_speed",
        DataType.UINT32, Access.RW, unit="rps",
        description="取值范围 0~100000",
    ),
}


def encode_value(reg_def: RegisterDef, actual_value: float) -> int:
    """将实际值编码为寄存器值(应用缩放系数)"""
    return int(actual_value * reg_def.scale)


def decode_value(reg_def: RegisterDef, reg_value: int) -> float:
    """将寄存器值解码为实际值(应用缩放系数)"""
    if reg_def.scale == 1.0:
        return reg_value
    return reg_value / reg_def.scale


def get_register_by_address(address: int) -> RegisterDef | None:
    """根据地址查找寄存器定义"""
    for reg in REGISTERS.values():
        if reg.address == address:
            return reg
    return None
