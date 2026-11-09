"""Stand-in Mitsubishi PLC for local testing: exposes D100 over SLMP on port 5007."""

import sys
import time

sys.path.insert(0, __file__.rsplit("/", 2)[0])

from slmp.client import DEVICE_CODES
from slmp.mock_server import MockSLMPServer


def main() -> None:
    server = MockSLMPServer(host="127.0.0.1", port=5007)
    server.set_word(DEVICE_CODES["D"], 100, 1234)
    server.start()
    print(f"Mock PLC listening on 127.0.0.1:{server.port} (D100=1234). Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.stop()


if __name__ == "__main__":
    main()
