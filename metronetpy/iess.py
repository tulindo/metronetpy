import json
import logging
import re
from datetime import datetime
from urllib.parse import urlencode

import sslkeylog
from hyper import HTTP20Connection

_LOGGER = logging.getLogger(__name__)

METRONET = "metronet.iessonline.com"
METRONET_URL = f"https://{METRONET}/"


class Controller(object):
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.sensors = []
        self.lookup = {}
        self.callbacks = []
        self.run = False
        self.connection = None
        self.session_cookie = None
        self.headers = None
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
            for func in self.callbacks:
                _LOGGER.debug("Notify callback with data: %s", data)
                func(data)
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Could not notify callback")

    def init_connection(self):
        self.connection = HTTP20Connection(METRONET)

    def init_session_cookie(self):
        # GET ASP Session Cookie
        headers = {
            "upgrade-insecure-requests": "1",
            "sec-fetch-mode": "navigate",
            "sec-fetch-user": "?1",
            "sec-fetch-site": "none",
            "accept-encoding": "gzip",
        }

        self.connection.request("GET", "/", headers=headers)
        resp = self.connection.get_response()

        for i in resp.headers.get("set-cookie"):
            str = i.decode("UTF-8")
            if str.startswith("ASP.NET_SessionId="):
                self.session_cookie = str.split(";")[0]
                self.headers = self.get_headers()

    def login(self):
        # Login to metronet
        headers = {
            "cache-control": "max-age=0",
            "origin": METRONET_URL,
            "upgrade-insecure-requests": "1",
            "content-type": "application/x-www-form-urlencoded",
            "sec-fetch-mode": "navigate",
            "sec-fetch-user": "?1",
            "sec-fetch-site": "same-origin",
            "referer": METRONET_URL,
            "accept-encoding": "gzip",
            "cookie": self.session_cookie,
        }

        data = {
            "IsDisableAccountCreation": "False",
            "IsAllowThemeChange": "False",
            "UserName": self.username,
            "Password": self.password,
            "RememberMe": "false",
        }

        self.connection.request("POST", "/", body=urlencode(data), headers=headers)

        resp = self.connection.get_response()

        logged_in = False
        if resp.status == 302:
            found_username = False
            found_password = False
            for i in resp.headers.get("set-cookie"):
                str = i.decode("UTF-8")
                if not found_username:
                    found_username = "username" in str
                if not found_password:
                    found_password = "password" in str
            if found_username and found_password:
                logged_in = True
        return logged_in

    def get_variable(self, page, name):
        # Legge variabile da pagina html.
        regex = f"var\s+{name!s}\s+=\s+'[0-9a-f-]+';"
        match = re.search(regex, page)
        if match != None:
            line = match.group()
            index = line.find("'")
            return line[index + 1 : -2]

    def init_session_data(self):
        headers = {
            "cache-control": "max-age=0",
            "upgrade-insecure-requests": "1",
            "sec-fetch-mode": "navigate",
            "sec-fetch-user": "?1",
            "sec-fetch-site": "same-origin",
            "referer": METRONET_URL,
            "accept-encoding": "gzip",
            "cookie": self.session_cookie,
        }
        self.connection.request("GET", "/Status", headers=headers)
        resp = self.connection.get_response()

        page = resp.read().decode("UTF-8")

        self.session_id = self.get_variable(page, "sessionId")
        self.last_input = self.get_variable(page, "lastInputId")

    def get_strings(self):
        data = {"sessionId": self.session_id}

        self.connection.request(
            "POST", "/api/strings", body=urlencode(data), headers=self.headers
        )

        resp = self.connection.get_response()
        page = resp.read().decode("UTF-8")
        page = json.loads(page)

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

    def get_inputs(self, notify=True, is_retry=False):
        data = {"sessionId": self.session_id}

        self.connection.request(
            "POST", "/api/inputs", body=urlencode(data), headers=self.headers
        )

        resp = self.connection.get_response()
        if resp.status == 200:
            page = resp.read().decode("UTF-8")
            page = json.loads(page)

            is_changed = False
            notify_data = []
            for obj in page:
                idx = obj["Index"]
                if idx in self.lookup:
                    # The input is in the list of configured sensors.
                    sensor = self.lookup[idx]
                    if not notify or sensor["active"] != obj["Alarm"]:
                        is_changed = True
                        sensor["active"] = obj["Alarm"]
                    notify_data.append((idx, obj["Alarm"]))
                self.last_input = obj["Id"]
            _LOGGER.debug(self.sensors)
            if notify and is_changed:
                self.notify(notify_data)
        elif is_retry:
            _LOGGER.error("Error after relogin")
            exit()
        else:
            _LOGGER.info("Inputs Relogin")
            self.login()
            _LOGGER.info("Re Init Session Data")
            self.init_session_data()
            # Try again.
            self.get_inputs(True)

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

        self.connection.request(
            "POST", "/api/updates", body=urlencode(data), headers=self.headers
        )

        resp = self.connection.get_response()
        if resp.status == 200:
            page = resp.read().decode("UTF-8")

            pagej = json.loads(page)

            changes = pagej["HasChanges"]
            _LOGGER.debug(f"Updates {self.last_input} -> Changes {changes}")

            return changes
        else:
            _LOGGER.info("Updates Relogin")
            logged_in = self.login()
            if not logged_in:
                _LOGGER.error("Failed to login")
                return False
            _LOGGER.info("Re Init Session Data")
            self.init_session_data()
            return True

    def get_headers(self):
        return {
            "x-requested-with": "XMLHttpReques",
            "sec-fetch-mode": "cors",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "origin": METRONET_URL,
            "sec-fetch-site": "same-origin",
            "referer": f"{METRONET_URL}Status",
            "accept-encoding": "gzip",
            "cookie": self.session_cookie,
        }

    def message_loop(self):
        while self.run:
            # Loop forever
            update = self.get_updates()
            # Ask for update
            if update:
                # Get inputs
                self.get_inputs()

    def stop_loop(self):
        self.run = False
