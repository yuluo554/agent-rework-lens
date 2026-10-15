"""编码护栏复现测试（★ K10）：cp1252 崩溃场景 → 护栏后正常；cp936 不被乱动。"""

from io import BytesIO, TextIOWrapper

import pytest

from agent_rework_lens.stdio import _ensure_utf8_stdio, _stream_needs_utf8

SAMPLE = "会话返工体检中文"


def _stream(encoding, errors="strict"):
    buffer = BytesIO()
    return buffer, TextIOWrapper(buffer, encoding=encoding, errors=errors)


def test_cp1252_without_guard_would_crash():
    """阳性对照：证明护栏防的是真实崩溃（不是假想问题）。"""
    _, stream = _stream("cp1252")
    with pytest.raises(UnicodeEncodeError):
        stream.write(SAMPLE)


def test_cp1252_detected_and_recovered():
    buffer, stream = _stream("cp1252")
    assert _stream_needs_utf8(stream) is True
    _ensure_utf8_stdio([stream])
    stream.write(SAMPLE)
    stream.flush()
    assert buffer.getvalue().decode("utf-8") == SAMPLE


def test_cp936_kept_untouched():
    buffer, stream = _stream("cp936")
    assert _stream_needs_utf8(stream) is False
    _ensure_utf8_stdio([stream])
    stream.write(SAMPLE)
    stream.flush()
    assert buffer.getvalue().decode("cp936") == SAMPLE


def test_ascii_reconfigured():
    buffer, stream = _stream("ascii")
    assert _stream_needs_utf8(stream) is True
    _ensure_utf8_stdio([stream])
    stream.write(SAMPLE)
    stream.flush()
    assert buffer.getvalue().decode("utf-8") == SAMPLE


def test_stream_without_reconfigure_is_safe():
    class NoReconfigure:
        encoding = "cp1252"

        def write(self, text):
            return len(text)

    _ensure_utf8_stdio([NoReconfigure()])  # 不抛错即通过


def test_stream_without_encoding_attribute_is_safe():
    class Bare:
        pass

    _ensure_utf8_stdio([Bare()])


def test_guard_idempotent():
    buffer, stream = _stream("cp1252")
    _ensure_utf8_stdio([stream])
    _ensure_utf8_stdio([stream])
    stream.write(SAMPLE)
    stream.flush()
    assert buffer.getvalue().decode("utf-8") == SAMPLE


def test_default_streams_callable():
    _ensure_utf8_stdio()  # 对真实 stdio：探针判定后原样或切换；不得抛错
