"""
Lennox iComfort Wifi API.

Support added for AirEase MyComfortSync thermostats.

By Jacob Southard (github.com/voltagesource)
Based on the work done by Jerome Avondo (github.com/ut666)

Notes:
  This API currently only supports manual mode (no programs) on the thermostat.

Cloud API Response Notes:
  Pref_Temp_Units: [0='F', 1='C']
  Operation_Mode: [0='Off', 1='Heat only', 2='Cool only', 3='Heat & Cool', 4='Emergency Heat']
  Fan_Mode: [0='Auto', 1='On', 2='Circulate']
  System_Status: [0='Idle', 1='Heating', 2='Cooling', 3='System Waiting']

Issues:
  I don't have this thermostat anymore so I need to work with someone to add features.

Ideas/Future:
  Support thermostat programs
  Set Away temps - Research if possible through cloud API
  Support other states - dehumidify

Change log:

v0.7.0 - Expose system number, serial number, and zone as properties. 
v0.6.0 - System Waiting state idetified as state = 3. Added to state list.
v0.5.1 - Clean up - Add missing change logs and documentation.
v0.5.0 - Feature - Add support for Emergency Heat mode. Changed set_points logic to properly 
           handle mode=4.
v0.4.1 - Bug Fix - Change get_json() to use OrderedDict per reature request.
v0.4.0 - Feature - Add method get_json(). Returns current status as json.
v0.3.1 - Bug Fix - self.zone set to 0 after initial pull if cloud service fails
                   to respond.
v0.3.0 - Add support for AirEase cloud API.
           New class attribute 'svc' allows selection of cloud API.
           If svc='lennox' (defoult) API connects to Lennox MyiComfort.
           If svc='airease' API connects to AirEase MyComffortSync.
         Added connected property. Returns True if able to pull system info
         from cloud API.
v0.2.1 - Fix issue with set_points setter. Code cleanup.
v0.2.0 - Initial Release

"""

import logging
import json
import requests
from collections import OrderedDict

_LOGGER = logging.getLogger(__name__)


LENNOX_SERVICE_URL = "https://services.myicomfort.com/DBAcessService.svc/"
AIREASE_SERVICE_URL = "https://services.mycomfortsync.com/DBAcessService.svc/"

OP_MODE_LIST = ['Off', 'Heat only', 'Cool only', 'Heat or Cool', 'Emergency Heat']
FAN_MODE_LIST = ['Auto', 'On', 'Circulate']
STATE_LIST = ['Idle', 'Heating', 'Cooling', 'System Waiting']
TEMP_UNTIS_LIST = [chr(176) + 'F', chr(176) + 'C']


class Tstat():
    """Representation of the Lennox iComfort thermostat."""

    def __init__(self, username, password,
                 system=0, zone=0, svc='Lennox', units=9):
        """Initialize the API interface."""
        _LOGGER.info('Initializing Thermostat')

        if svc.lower() == 'airease':
            self._service_url = AIREASE_SERVICE_URL
            _LOGGER.info('Connecting to AirEase MyComfortSync')
        else:
            self._service_url = LENNOX_SERVICE_URL
            _LOGGER.info('Connecting to Lennox MyiComfort')

        # Service/system details.
        self._credentials = (username, password)
        self._system = system
        self._zone = zone
        self._serial_number = None

        # Use specified units if value is 0 (F) or 1 (C)
        if units in (0, 1):
            self._temperature_units = units
            self._use_tstat_units = False
        else:
            self._temperature_units = 0
            self._use_tstat_units = True

        # Set point variables.
        self._heat_to = None
        self._cool_to = None

        # Current mode/state.
        self._away_mode = None
        self._state = None
        self._op_mode = None
        self._fan_mode = None

        # Current sensor values.
        self._current_temperature = None
        self._current_humidity = None

        # Connect to service and collect initial values.
        self._get_serial_number()
        self.pull_status(True)

        # If we are using thermostat units we must re-request status now that
        # we know the appropriate units
        if self._use_tstat_units:
            self.pull_status()

    @property
    def connected(self):
        """Return connected status."""
        if self._serial_number is not None:
            return True
        return False

    @property
    def serial_number(self):
        return self._serial_number
    
    @property
    def zone(self):
        return self._zone

    @property
    def system(self):
        return self._system
    
    @property
    def state_list(self):
        """Return list of states."""
        return STATE_LIST

    @property
    def state(self):
        """Return current operational state."""
        return self._state

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def current_humidity(self):
        """Return the current humidity."""
        return self._current_humidity

    @property
    def temp_units_list(self):
        """Return list of termperature units."""
        return TEMP_UNTIS_LIST

    @property
    def temperature_units(self):
        """Return current temperature units."""
        return self._temperature_units

    @temperature_units.setter
    def temperature_units(self, value):
        """Set Temperature units."""
        if value in (0, 1):
            self._temperature_units = value
            self._use_tstat_units = False
            # Since we aren't changing a setting on the thermostat there is no
            # reason to push settings.
            # Desired units are passed with every call to the cloud API.
            self.pull_status()

    @property
    def op_mode_list(self):
        """Return list of operational modes."""
        return OP_MODE_LIST

    @property
    def op_mode(self):
        """Return current operational mode."""
        return self._op_mode

    @op_mode.setter
    def op_mode(self, value):
        """Set operational mode."""
        self._op_mode = value
        self._push_settings()

    @property
    def fan_mode_list(self):
        """Return list of fan modes."""
        return FAN_MODE_LIST

    @property
    def fan_mode(self):
        """Return current fan mode."""
        return self._fan_mode

    @fan_mode.setter
    def fan_mode(self, value):
        """Set fan mode."""
        self._fan_mode = value
        self._push_settings()

    @property
    def set_points(self):
        """Return current set points as a tuple (heat_to, cool_to)."""
        return (self._heat_to, self._cool_to)

    @set_points.setter
    def set_points(self, value):
        """Set temperature set points based on mode and provided data."""
        if isinstance(value, tuple):
            # If we get a tuple we set based on size of tuple or mode.
            if len(value) == 2:
                self._heat_to = min(value)
                self._cool_to = max(value)
            elif self._op_mode == 2:
                self._cool_to = max(value)
            elif self._op_mode in (1, 4):
                self._heat_to = min(value)
        elif isinstance(value, (float, int)):
            # If we were provided a single value, set temp for current mode.
            if self._op_mode == 2:
                self._cool_to = value
            elif self._op_mode in (1, 4):
                self._heat_to = value
        self._push_settings()

    @property
    def away_mode(self):
        """Return away mode status."""
        return self._away_mode

    @away_mode.setter
    def away_mode(self, value):
        """Set away mode."""
        if self._serial_number is not None:
            command_url = (self._service_url
                           + "SetAwayModeNew?gatewaysn="
                           + self._serial_number
                           + "&awaymode="
                           + str(value))
            resp = requests.put(command_url, auth=self._credentials)
            if resp.status_code == 200:
                _LOGGER.debug(resp.json())
            else:
                _LOGGER.error('Thermostat cloud service not responding.')

    def pull_status(self, initial=False):
        """Retrieve current thermostat status/settings."""
        if self._serial_number is not None:
            command_url = (self._service_url
                           + "GetTStatInfoList?gatewaysn="
                           + self._serial_number
                           + "&TempUnit="
                           + str(self._temperature_units))
            stat_info = None
            resp = requests.get(command_url, auth=self._credentials)
            if resp.status_code == 200:
                _LOGGER.debug(resp.json())
                try:
                    stat_info = resp.json()['tStatInfo'][self._zone]
                except IndexError:
                    if initial:
                        _LOGGER.warning(
                            "Specfied zone doesn't exist. "
                            "Switching to first zone."
                        )
                        self._zone = 0
                        try:
                            stat_info = resp.json()['tStatInfo'][self._zone]
                        except IndexError:
                            _LOGGER.error('No Zones Found.')
                    else:
                        _LOGGER.error('Problem pulling zone data')
            else:
                _LOGGER.error('Thermostat cloud service not responding.')

            if stat_info is not None:
                if self._use_tstat_units:
                    self._temperature_units = int(stat_info['Pref_Temp_Units'])
                self._state = int(stat_info['System_Status'])
                self._op_mode = int(stat_info['Operation_Mode'])
                self._fan_mode = int(stat_info['Fan_Mode'])
                self._away_mode = int(stat_info['Away_Mode'])
                self._current_temperature = float(stat_info['Indoor_Temp'])
                self._current_humidity = float(stat_info['Indoor_Humidity'])
                self._heat_to = float(stat_info['Heat_Set_Point'])
                self._cool_to = float(stat_info['Cool_Set_Point'])

    def get_json(self, indent=None):
        """Return status as ordered JSON."""
        data = OrderedDict()
        self.pull_status()
        data["serial_number"] = self._serial_number
        data["state"] = self.state
        data["state_text"] = self.state_list[self.state]
        data["op_mode"] = self.op_mode
        data["op_mode_text"] = self.op_mode_list[self.op_mode]
        data["fan_mode"] = self.fan_mode
        data["fan_mode_text"] = self.fan_mode_list[self._fan_mode]
        data["away_mode"] = self.away_mode
        data["temperature_units"] = self.temperature_units
        data["temperature_units_text"] = self.temp_units_list[
            self.temperature_units
            ]
        data["current_temperature"] = self.current_temperature
        data["current_humidity"] = self.current_humidity
        data["heat_to"] = self.set_points[0]
        data["cool_to"] = self.set_points[1]
        return json.dumps(data, indent=indent)

    def _push_settings(self):
        """Push settings to Lennox Cloud API."""
        if self._serial_number is not None:
            data = {
                'Cool_Set_Point': self._cool_to,
                'Heat_Set_Point': self._heat_to,
                'Fan_Mode': self._fan_mode,
                'Operation_Mode': self._op_mode,
                'Pref_Temp_Units': self._temperature_units,
                'Zone_Number': self._zone,
                'GatewaySN': self._serial_number
            }

            command_url = self._service_url + "SetTStatInfo"
            headers = {'contentType': 'application/x-www-form-urlencoded',
                       'requestContentType': 'application/json; charset=utf-8'}
            resp = requests.put(command_url, auth=self._credentials,
                                json=data, headers=headers)
            if resp.status_code == 200:
                _LOGGER.debug(resp.json())
            else:
                _LOGGER.error('Thermostat cloud service not responding.')

    def _get_serial_number(self):
        """Retrieve serial number for specified system."""
        command_url = (self._service_url
                       + "GetSystemsInfo?UserId="
                       + self._credentials[0])
        resp = requests.get(command_url, auth=self._credentials)
        if resp.status_code == 200:
            _LOGGER.debug(resp.json())
            try:
                self._serial_number = (resp.json()["Systems"]
                                       [self._system]["Gateway_SN"])
            except IndexError:
                _LOGGER.warning(
                    'Specfied system not found. Switching to first system'
                )
                self._system = 0
                try:
                    self._serial_number = (resp.json()["Systems"]
                                           [self._system]["Gateway_SN"])
                except IndexError:
                    _LOGGER.error('No Systems Found.')
        elif resp.status_code == 401:
            _LOGGER.error('Username or password incorrect.')
        else:
            _LOGGER.error('Thermostat cloud service not responding.')
