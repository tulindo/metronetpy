import json
import logging
import re
import time
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
        self.callbacks = {}
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
            for id, active in data:
                if id in self.callbacks:
                    for func in self.callbacks[id]:
                        _LOGGER.debug("Notify sensor %d  with data: %s", id, active)
                        func(id, active)
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
        _LOGGER.debug(f"Init Session Cookie -> response code: {resp.status}")

        for i in resp.headers.get("set-cookie"):
            str = i.decode("UTF-8")
            if str.startswith("ASP.NET_SessionId="):
                self.session_cookie = str.split(";")[0]
                _LOGGER.debug(f"Init Session Cookie -> cookie: {self.session_cookie}")
                self.headers = self.get_headers()
                _LOGGER.debug(f"Init Session Cookie -> Headers: {self.headers}")

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
        _LOGGER.debug(f"Login -> response code: {resp.status}")

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

        _LOGGER.debug(f"Login -> logged in: {logged_in}")
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
        _LOGGER.debug(f"Init Session Data -> response code: {resp.status}")
        page = resp.read().decode("UTF-8")

        self.session_id = self.get_variable(page, "sessionId")
        _LOGGER.debug(f"Init Session Data -> sessionId {self.session_id}")
        self.last_input = self.get_variable(page, "lastInputId")
        _LOGGER.debug(f"Init Session Data -> LastInput {self.last_input}")

    def get_strings(self):
        data = {"sessionId": self.session_id}

        self.connection.request(
            "POST", "/api/strings", body=urlencode(data), headers=self.headers
        )

        resp = self.connection.get_response()
        _LOGGER.debug(f"Strings-> response code: {resp.status}")
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
        _LOGGER.debug(f"Init Session Data -> sensors: {self.sensors}")

    def get_inputs(self, is_retry=False):
        data = {"sessionId": self.session_id}
        _LOGGER.debug(f"Get Inputs -> data {data}")

        self.connection.request(
            "POST", "/api/inputs", body=urlencode(data), headers=self.headers
        )

        resp = self.connection.get_response()
        _LOGGER.debug(f"Get Inputs -> response code: {resp.status}")
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
            _LOGGER.info("Get Inputs -> Re Init Session Data")
            self.init_session_data()
            # Try again.
            self.get_inputs(is_retry=True)
        else:
            _LOGGER.info("Get Inputs -> Relogin")
            self.login()
            _LOGGER.info("Get Inputs -> Re Init Session Data")
            self.init_session_data()
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

        self.connection.request(
            "POST", "/api/updates", body=urlencode(data), headers=self.headers
        )

        resp = self.connection.get_response()
        _LOGGER.debug(f"Updates -> response code: {resp.status}")
        if resp.status == 200:
            page = resp.read().decode("UTF-8")

            pagej = json.loads(page)

            changes = pagej["HasChanges"]
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
            _LOGGER.info("Updates -> Re Init Session Data")
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
        """
        Main message loop.

        Asks for sensor updates,
        if the metronet cloud replies that something has changed,
        asks or updated sensor values and repeat the process.
        """
        _LOGGER.info("Mainloop: Started")
        while self.run:
            # Loop forever
            _LOGGER.debug("Mainloop: Getting Updates")
            update = self.get_updates()
            # Ask for update
            if update:
                # Get inputs
                _LOGGER.debug("Mainloop: Getting Inputs")
                self.get_inputs()
        _LOGGER.info("Mainloop: ended")

    def stop_loop(self):
        _LOGGER.debug("Ending Main Loop")
        self.run = False
