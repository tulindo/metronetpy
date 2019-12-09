"""The Metronet IESS Online bridge."""
import logging
import threading

from .iess import Controller

_LOGGER = logging.getLogger(__name__)


class MetronetBridge:
    """The Metronet Bridge class.

    The class is the public interface exposed to client.
    """

    def __init__(self, username, password):
        """Init for data."""
        self.controller = Controller(username, password)
        self._thread = None

    def register_callback(self, sensor_id, func):
        """Store callback in list.

        The callback should accept a dict as argument.
        For each update in sensor states request from
        the alarm control panel, all callbacks will be called with a dict
        containing the new status of the alarm.
        """
        if sensor_id not in self.controller.callbacks:
            self.controller.callbacks[sensor_id] = []
        self.controller.callbacks[sensor_id].append(func)

    def load_config(self, sensors):
        """Initialize controller with sensor configuration."""
        self.controller.set_sensors(sensors)

    def connect(self):
        """Connect to metronet."""
        # Imposta logging chiave ssl
        # sslkeylog.set_keylog("/home/tuni/sslkey.log")
        _LOGGER.debug("Connect")

        self.controller.init_session()

        _LOGGER.debug("Logging in")
        return self.controller.login()

    def get_sensors(self):
        """Get sensor list and initial value."""
        self.controller.get_strings()

        self.controller.get_inputs()

        return self.controller.sensors

    def main_loop(self):
        """Start main loop in a separate thread."""
        self.controller.run = True
        self._thread = threading.Thread(
            target=self.controller.message_loop, name="Metronet", daemon=True
        )
        self._thread.start()

    def stop(self):
        """Stop main loop."""
        if self.controller.run:
            self.controller.stop_loop()
            self._thread.join()
