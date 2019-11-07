import logging
import threading

from .iess import Controller

_LOGGER = logging.getLogger(__name__)


class MetronetBridge(object):
    def __init__(self, config):
        self.controller = Controller(config)
        self._thread = None

    def register_callback(self, func):
        """Store callback in list.

        The callback should accept a dict as argument. 
        For each update in sensor states request from
        the alarm control panel, all callbacks will be called with a dict
        containing the new status of the alarm.
        """
        self.controller.callbacks.append(func)

    def connect(self):

        # Imposta logging chiave ssl
        # sslkeylog.set_keylog("/home/tuni/sslkey.log")

        self.controller.init_connection()

        self.controller.init_session_cookie()
        _LOGGER.debug(f"Cookie: {self.controller.session_cookie!s}")

        self.controller.login()
        _LOGGER.debug("Loggedin")

    def get_sensors(self):
        self.controller.init_session_data()

        _LOGGER.debug(f"SessionID: {self.controller.session_id}")
        _LOGGER.debug(f"Last Input: {self.controller.last_input}")

        self.controller.get_strings()

        self.controller.get_inputs(notify=False)

        return self.controller.sensors

    def main_loop(self):
        self._thread = threading.Thread(
            target=self.controller.message_loop, daemon=True
        )
        self._thread.start()

    def stop(self):
        self.controller.stop_loop()
        self._thread.join()
