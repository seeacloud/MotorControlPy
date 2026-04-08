"""32位数据编解码与字序处理"""

import struct


def split_32bit(value: int, signed: bool = True, word_order: int = 0) -> list[int]:
    """将32位整数拆分为两个16位寄存器值。

    Args:
        value: 32位整数值
        signed: 是否为有符号整数
        word_order: 0=高位在前(默认), 1=低位在前
    Returns:
        [word1, word2] 两个16位无符号整数
    """
    fmt = '>i' if signed else '>I'
    raw = struct.pack(fmt, value)
    high = (raw[0] << 8) | raw[1]
    low = (raw[2] << 8) | raw[3]
    if word_order == 0:
        return [high, low]
    else:
        return [low, high]


def combine_32bit(words: list[int], signed: bool = True, word_order: int = 0) -> int:
    """将两个16位寄存器值合并为32位整数。

    Args:
        words: [word1, word2] 两个16位无符号整数
        signed: 是否为有符号整数
        word_order: 0=高位在前(默认), 1=低位在前
    Returns:
        32位整数值
    """
    if word_order == 0:
        high, low = words[0], words[1]
    else:
        low, high = words[0], words[1]

    raw = struct.pack('>HH', high, low)
    fmt = '>i' if signed else '>I'
    return struct.unpack(fmt, raw)[0]
