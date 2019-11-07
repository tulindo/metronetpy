import argparse
import logging
import time
from pathlib import Path

from .bridge import MetronetBridge
from .config import Configuration

console = logging.StreamHandler()
console.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    "%(asctime)s %(name)-12s: %(levelname)-8s %(message)s", "%Y-%m-%d %H:%M:%S"
)
console.setFormatter(formatter)

_LOGGER = logging.getLogger("hpack")
_LOGGER.setLevel(logging.ERROR)
_LOGGER = logging.getLogger("hyper")
_LOGGER.setLevel(logging.ERROR)
_LOGGER = logging.getLogger()
_LOGGER.addHandler(console)
_LOGGER.setLevel(logging.DEBUG)


def callback(data):
    _LOGGER.info(f"Received {data}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        default=f"{Path.home()}/.metronet/configuration.yaml",
        metavar="FILE",
        help="Path to config file",
    )
    parser.add_argument(
        "--debug", default=False, action="store_true", help="Enable debug"
    )
    parser.add_argument("--log", default=None, metavar="FILE", help="Path to log file")
    args = parser.parse_args()

    _LOGGER.info("Starting")

    cfg = Configuration(args.config)
    bridge = MetronetBridge(cfg)

    bridge.register_callback(callback)

    bridge.connect()

    sensors = bridge.get_sensors()
    _LOGGER.info(sensors)

    bridge.main_loop()

    while True:

        time.sleep(1)

    bridge.stop()
