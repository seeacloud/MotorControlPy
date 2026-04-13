"""单元测试 - 32位数据编解码"""

import pytest
from protocol.data_types import split_32bit, combine_32bit


class TestSplit32bit:
    """split_32bit 拆分测试"""

    def test_positive_signed_high_first(self):
        # 100000 = 0x000186A0 -> high=0x0001, low=0x86A0
        result = split_32bit(100000, signed=True, word_order=0)
        assert result == [0x0001, 0x86A0]

    def test_positive_signed_low_first(self):
        result = split_32bit(100000, signed=True, word_order=1)
        assert result == [0x86A0, 0x0001]

    def test_negative_signed(self):
        # -1 = 0xFFFFFFFF -> high=0xFFFF, low=0xFFFF
        result = split_32bit(-1, signed=True, word_order=0)
        assert result == [0xFFFF, 0xFFFF]

    def test_zero(self):
        result = split_32bit(0, signed=True, word_order=0)
        assert result == [0, 0]

    def test_unsigned(self):
        result = split_32bit(0xDEADBEEF, signed=False, word_order=0)
        assert result == [0xDEAD, 0xBEEF]


class TestCombine32bit:
    """combine_32bit 合并测试"""

    def test_positive_signed_high_first(self):
        result = combine_32bit([0x0001, 0x86A0], signed=True, word_order=0)
        assert result == 100000

    def test_positive_signed_low_first(self):
        result = combine_32bit([0x86A0, 0x0001], signed=True, word_order=1)
        assert result == 100000

    def test_negative_signed(self):
        result = combine_32bit([0xFFFF, 0xFFFF], signed=True, word_order=0)
        assert result == -1

    def test_zero(self):
        result = combine_32bit([0, 0], signed=True, word_order=0)
        assert result == 0

    def test_unsigned(self):
        result = combine_32bit([0xDEAD, 0xBEEF], signed=False, word_order=0)
        assert result == 0xDEADBEEF


class TestRoundTrip:
    """编解码往返测试"""

    @pytest.mark.parametrize("value", [0, 1, -1, 100000, -100000, 2147483647, -2147483648])
    def test_signed_roundtrip(self, value):
        words = split_32bit(value, signed=True, word_order=0)
        assert combine_32bit(words, signed=True, word_order=0) == value

    @pytest.mark.parametrize("value", [0, 1, 100000, 0xFFFFFFFF])
    def test_unsigned_roundtrip(self, value):
        words = split_32bit(value, signed=False, word_order=0)
        assert combine_32bit(words, signed=False, word_order=0) == value

    @pytest.mark.parametrize("word_order", [0, 1])
    def test_word_order_roundtrip(self, word_order):
        value = 123456
        words = split_32bit(value, signed=True, word_order=word_order)
        assert combine_32bit(words, signed=True, word_order=word_order) == value
