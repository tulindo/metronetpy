import logging
import re
import requests
import time


# import sslkeylog

_LOGGER = logging.getLogger(__name__)

METRONET = "metronet.iessonline.com"
METRONET_URL = f"https://{METRONET}/"
METRONET_STATUS = f"https://{METRONET}/Status"
METRONET_API_STRINGS = f"https://{METRONET}/api/strings"
METRONET_API_INPUTS = f"https://{METRONET}/api/inputs"
METRONET_API_UPDATES = f"https://{METRONET}/api/updates"


class Controller(object):
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.sensors = []
        self.lookup = {}
        self.callbacks = {}
        self.run = False
        self.session = None
        self.session_id = None
        self.last_input = None

    def set_sensors(self, sensors):
        self.sensors = sensors
        self.__create_lookup()

    def __create_lookup(self):
        self.lookup = {}
        for sensor in self.sensors:
            self.lookup[sensor["id"]] = sensor

    def notify(self, data):
        """Call callbacks with event data."""
        try:
            for id, active in data:
                if id in self.callbacks:
                    for func in self.callbacks[id]:
                        _LOGGER.debug("Notify sensor %d  with data: %s", id, active)
                        func(id, active)
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Could not notify callback")

    def init_session(self):
        self.session = requests.Session()

        resp = self.session.get(METRONET_URL)
        _LOGGER.debug(f"Init Session Cookie -> response code: {resp.status_code}")

        self.session.headers.update(
            {
                "x-requested-with": "XMLHttpReques",
                "sec-fetch-mode": "cors",
                "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
                "origin": METRONET_URL,
                "sec-fetch-site": "same-origin",
                "referer": f"{METRONET_URL}Status",
            }
        )

        _LOGGER.debug(f"Init Session Cookie -> Headers: {self.session.headers}")

    def login(self):
        # Login to metronet
        self.session.headers.update(
            {
                "sec-fetch-mode": "navigate",
                "sec-fetch-user": "?1",
                "sec-fetch-site": "same-origin",
                "referer": METRONET_URL,
            }
        )
        _LOGGER.debug(f"Init Login -> Headers: {self.session.headers}")
        data = {
            "IsDisableAccountCreation": "False",
            "IsAllowThemeChange": "False",
            "UserName": self.username,
            "Password": self.password,
            "RememberMe": "false",
        }

        resp = self.session.post(METRONET_URL, data=data)
        _LOGGER.debug(f"Init Login -> Cookies: {self.session.cookies}")

        _LOGGER.debug(f"Login -> response code: {resp.status_code}")

        logged_in = resp.url == METRONET_STATUS
        _LOGGER.debug(f"Login -> logged in: {logged_in}")
        if logged_in:
            self.parse_status_page(resp.text)
        return logged_in

    def get_variable(self, page, name):
        # Legge variabile da pagina html.
        regex = f"var\s+{name!s}\s+=\s+'[0-9a-f-]+';"
        match = re.search(regex, page)
        if match is not None:
            line = match.group()
            index = line.find("'")
            return line[index + 1 : -2]

    def parse_status_page(self, page):
        self.session_id = self.get_variable(page, "sessionId")
        _LOGGER.debug(f"Parse Status Page -> sessionId {self.session_id}")
        self.last_input = self.get_variable(page, "lastInputId")
        _LOGGER.debug(f"Parse Status Page -> LastInput {self.last_input}")

    def get_strings(self):
        data = {"sessionId": self.session_id}

        resp = self.session.post(METRONET_API_STRINGS, data=data)

        _LOGGER.debug(f"Strings-> response code: {resp.status_code}")

        page = resp.json()

        for str in page:
            if str["Class"] == 10:
                # Found an input
                idx = str["Index"]
                if not self.lookup:
                    # No configuration provided. Get all sensors.
                    self.sensors.append(
                        {"id": idx, "type": None, "name": str["Description"]}
                    )
                elif idx in self.lookup:
                    # Consider only configured sensors.
                    sensor = self.lookup[idx]
                    if not sensor["name"]:
                        # Configured without name... get it from metronet.
                        sensor["name"] = str["Description"]
        if not self.lookup:
            self.__create_lookup()
        _LOGGER.debug(f"Init Session Data -> sensors: {self.sensors}")

    def get_inputs(self, is_retry=False):
        data = {"sessionId": self.session_id}
        _LOGGER.debug(f"Get Inputs -> data {data}")

        try:
            resp = self.session.post(METRONET_API_INPUTS, data=data, timeout=10)
        except:
            _LOGGER.error("Get Inputs -> Exception!")
        if resp is not None:
            _LOGGER.debug(f"Get Inputs -> response code: {resp.status_code}")
        if resp is not None and resp.status_code == 200:
            page = resp.json()

            is_changed = False
            notify_data = []
            for obj in page:
                idx = obj["Index"]
                if idx in self.lookup:
                    # The input is in the list of configured sensors.
                    sensor = self.lookup[idx]
                    if "active" not in sensor:
                        sensor["active"] = obj["Alarm"]
                    elif sensor["active"] != obj["Alarm"]:
                        is_changed = True
                        sensor["active"] = obj["Alarm"]
                        notify_data.append((idx, obj["Alarm"]))
                self.last_input = obj["Id"]
            _LOGGER.debug(f"Get Inputs -> sensors: {self.sensors}")
            if is_changed:
                _LOGGER.debug(f"Get Inputs -> notify : {notify_data}")
                self.notify(notify_data)
        elif is_retry:
            _LOGGER.warning("Get Inputs -> Error after relogin")
            _LOGGER.debug("Get Inputs -> Wait 15 seconds")
            # Wait 15 seconds and retry
            time.sleep(15)
            _LOGGER.info("Get Inputs -> Relogin")
            self.login()
            # Try again.
            self.get_inputs(is_retry=True)
        else:
            _LOGGER.info("Get Inputs -> Relogin")
            self.login()
            # Try again.
            self.get_inputs(is_retry=True)

    def get_updates(self):
        data = {
            "sessionId": self.session_id,
            "CanElevate": "1",
            "ConnectionStatus": "1",
            "Inputs": self.last_input,
            "LoggedIn": "0",
            "LoginInProgress": "0",
            "ReadStringsInProgress": "0",
            "Strings": "1",
        }
        _LOGGER.debug(f"Updates -> data {data}")

        try:
            resp = self.session.post(METRONET_API_UPDATES, data=data, timeout=30)
        except:
            _LOGGER.error("Updates -> Exception!")
            return False
        _LOGGER.debug(f"Updates -> response code: {resp.status_code}")
        if resp.status_code == 200:
            page = resp.json()

            changes = page["HasChanges"]
            # if changes:
            _LOGGER.debug(
                f"Updates -> Last Input: {self.last_input} -> Changes: {changes}"
            )

            return changes
        else:
            _LOGGER.info("Updates -> Relogin")
            logged_in = self.login()
            if not logged_in:
                _LOGGER.error("Updates -> Failed to login")
                return False
            return True

    def message_loop(self):
        """
        Main message loop.

        Asks for sensor updates,
        if the metronet cloud replies that something has changed,
        asks or updated sensor values and repeat the process.
        """
        _LOGGER.info("Mainloop: Started")
        while self.run:
            # Loop forever
            _LOGGER.info("Mainloop: Getting Updates")
            update = self.get_updates()
            _LOGGER.debug("Mainloop: End Getting Updates")
            # Ask for update
            if update:
                # Get inputs
                _LOGGER.debug("Mainloop: Getting Inputs")
                self.get_inputs()
                _LOGGER.debug("Mainloop: End Getting Inputs")
        _LOGGER.info("Mainloop: ended")

    def stop_loop(self):
        _LOGGER.debug("Ending Main Loop")
        self.run = False
