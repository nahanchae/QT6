import pytest

from slmp.client import DEVICE_CODES, SLMP3EClient, SLMPError
from slmp.mock_server import MockSLMPServer


@pytest.fixture
def plc():
    server = MockSLMPServer(host="127.0.0.1", port=0)
    server.start()
    yield server
    server.stop()


def test_read_single_d_register(plc):
    plc.set_word(DEVICE_CODES["D"], 100, 1234)
    with SLMP3EClient("127.0.0.1", plc.port) as client:
        assert client.read_word("D", 100) == 1234


def test_read_negative_value_as_signed(plc):
    plc.set_word(DEVICE_CODES["D"], 100, 0xFFFF)  # -1 as a signed 16-bit word
    with SLMP3EClient("127.0.0.1", plc.port) as client:
        assert client.read_word("D", 100) == 0xFFFF
        assert client.read_word_signed("D", 100) == -1


def test_read_multiple_consecutive_words(plc):
    plc.set_word(DEVICE_CODES["D"], 100, 10)
    plc.set_word(DEVICE_CODES["D"], 101, 20)
    plc.set_word(DEVICE_CODES["D"], 102, 30)
    with SLMP3EClient("127.0.0.1", plc.port) as client:
        assert client.read_words("D", 100, 3) == [10, 20, 30]


def test_unsupported_command_raises_slmp_error(plc):
    with SLMP3EClient("127.0.0.1", plc.port) as client:
        with pytest.raises(SLMPError):
            client._send_command(0x9999, 0x0000, b"")
