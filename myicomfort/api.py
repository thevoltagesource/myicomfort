"""
Lennox iComfort Wifi API
By Jacob Southard (github.com/voltagesource)
Based on the work done by Jerome Avondo (github.com/ut666)

Notes: 
  This API currently only supports manual mode (no programs) on the thermostat. 

Cloud API Response Notes:
  Pref_Temp_Units: [0='F', 1='C']
  Operation_Mode: [0='Off', 1='Heat only', 2='Cool only', 3='Heat & Cool']
  Fan_Mode: [0='Auto', 1='On', 2='Circulate']
  System_Status: [0='Idle', 1='Heating', 2='Cooling']

Issues:

Ideas/Future:
  Support thermostat programs
  Set Away temps - Research if possible through cloud API
  Support other states - dehumidify / waiting

Change log:

"""

import logging
import requests

_LOGGER = logging.getLogger(__name__)
SERVICE_URL = "https://services.myicomfort.com/DBAcessService.svc/"

class Tstat():
    """ Representation of the Lennox iComfort thermostat. """

    def __init__(self, username, password, system=0, zone=0, units=9):
        """ Initialize the API interface. """
        _LOGGER.info('Initializing Thermostat')

        # Service/system details.
        self._credentials = (username, password)
        self._system = system 
        self._zone = zone
        self._serial_number = None

        # Use specified units if value is 0 (F) or 1 (C)
        if units == 0 or units == 1:
            self._temperature_units = units
            self._use_tstat_units = False
        else:
            self._temperature_units = 0
            self._use_tstat_units = True

        # Readable mode/state lists.
        self._op_mode_list = ['Off', 'Heat only', 'Cool only', 'Heat or Cool']
        self._fan_mode_list = ['Auto', 'On', 'Circulate']
        self._state_list = ['Idle', 'Heating', 'Cooling']
        self._temp_units_list = [chr(176) + 'F', chr(176) + 'C']

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
        self.pull_status()

        # If we are using thermostat units we must re-request status now that
        # we know the appropriate units
        if self._use_tstat_units:
            self.pull_status()

    @property
    def state_list(self):
        """ Return list of states """
        return self._state_list

    @property
    def state(self):
        """ Return current operational state. """
        return self._state

    @property
    def current_temperature(self):
        """ Return the current temperature. """
        return self._current_temperature

    @property
    def current_humidity(self):
        """ Return the current humidity. """
        return self._current_humidity

    @property
    def temp_units_list(self):
        """ Return list of termperature units """
        return self._temp_units_list

    @property
    def temperature_units(self):
        """ Return current temperature units. """
        return self._temperature_units

    @temperature_units.setter
    def temperature_units(self, value):
        """ Set Temperature units. """
        if value == 0 or value == 1:
            self._temperature_units = value
            self._use_tstat_units = False
            # Since we aren't changing a setting on the thermostat there is no
            # reason to push settings.
            # Desired units are passed with every call to the cloud API.
            self.pull_status()

    @property
    def op_mode_list(self):
        """ Return list of states """
        return self._op_mode_list   

    @property
    def op_mode(self):
        """ Return current operational mode. """
        return self._op_mode

    @op_mode.setter
    def op_mode(self, value):
        """ Set operational mode. """
        self._op_mode = value
        self._push_settings()

    @property
    def fan_mode_list(self):
        """ Return list of fan modes """
        return self._fan_mode_list

    @property
    def fan_mode(self):
        """ Return current fan mode. """
        return self._fan_mode

    @fan_mode.setter
    def fan_mode(self, value):
        """ Set fan mode. """
        self._fan_mode = value
        self._push_settings()

    @property
    def set_points(self):
        """ Return current set points as a tuple (heat_to, cool_to). """
        return (self._heat_to, self._cool_to)

    @set_points.setter
    def set_points(self, value):
        """ Set temperature set points based on mode and provided data. """
        if isinstance(value, tuple):
            # If we get a tuple we set based on size of tuple or mode.
            if len(value) == 2:
                self._heat_to = min(value)
                self._cool_to = max(value)
            elif self._op_mode == 2:
                self._cool_to = max(value)
            elif self._op_mode == 1:
                self._heat_to = min(value)
        elif isinstance(value, int) or instinstance(value, float):
            # If we were provided a single value, set temp for current mode.
            if self._op_mode == 2:
                self._cool_to = value
            elif self._op_mode == 1:
                self._heat_to = value
        self._push_settings()

    @property
    def away_mode(self):
        """ Return away mode status. """
        return self._away_mode

    @away_mode.setter
    def away_mode(self, value):
        """ Set away mode. """
        if self._serial_number is not None:
            commandURL = ( SERVICE_URL
                           + "SetAwayModeNew?gatewaysn="
                           + self._serial_number
                           + "&awaymode="
                           + str(value) )
            resp = requests.put(commandURL, auth=self._credentials)
            if resp.status_code == 200:
                _LOGGER.debug(resp.json())
            else:
                _LOGGER.error('MyiComfort cloud service not responding.')

    def pull_status(self):
        """ Retrieve current thermostat status/settings. """
        if self._serial_number is not None:
            commandURL = ( SERVICE_URL
                           + "GetTStatInfoList?gatewaysn=" 
                           + self._serial_number
                           + "&TempUnit="
                           + str(self._temperature_units) )
            resp = requests.get(commandURL, auth=self._credentials)
            if resp.status_code == 200:
                _LOGGER.debug(resp.json())
                try:
                    statInfo = resp.json()['tStatInfo'][self._zone]
                except IndexError:
                    _LOGGER.warning('Specfied zone doesn\'t exist. Switching'
                                    + ' to first zone.')
                    self._zone = 0
                    try:
                        statInfo = resp.json()['tStatInfo'][self._zone]
                    except IndexError:
                        _LOGGER.error('No Zones Found.')
            else:
                _LOGGER.error('MyiComfort cloud service not responding.')

            if self._use_tstat_units:
                self._temperature_units = int(statInfo['Pref_Temp_Units']) 
            self._state = int(statInfo['System_Status'])
            self._op_mode = int(statInfo['Operation_Mode'])
            self._fan_mode = int(statInfo['Fan_Mode'])
            self._away_mode = int(statInfo['Away_Mode'])
            self._current_temperature = float(statInfo['Indoor_Temp'])
            self._current_humidity = float(statInfo['Indoor_Humidity'])
            self._heat_to = float(statInfo['Heat_Set_Point'])
            self._cool_to = float(statInfo['Cool_Set_Point'])

    def _push_settings(self):
        """ Push settings to Lennox Cloud API. """
        if self._serial_number is not None:
            data = {
                'Cool_Set_Point':self._cool_to, 
                'Heat_Set_Point':self._heat_to, 
                'Fan_Mode':self._fan_mode, 
                'Operation_Mode':self._op_mode, 
                'Pref_Temp_Units':self._temperature_units, 
                'Zone_Number':self._zone, 
                'GatewaySN':self._serial_number
            }

            commandURL = SERVICE_URL + "SetTStatInfo"
            headers = {'contentType': 'application/x-www-form-urlencoded',
                       'requestContentType': 'application/json; charset=utf-8'}
            resp = requests.put(commandURL, auth=self._credentials,
                                json=data, headers=headers)
            if resp.status_code == 200:
                _LOGGER.debug(resp.json())
            else:
                _LOGGER.error('MyiComfort cloud service not responding.')

    def _get_serial_number(self):
        """" Retrieve serial number for specified system. """
        commandURL = ( SERVICE_URL
                       + "GetSystemsInfo?UserId="
                       + self._credentials[0] )
        resp = requests.get(commandURL, auth=self._credentials)
        if resp.status_code == 200:
            _LOGGER.debug(resp.json())
            try:
                self._serial_number = ( resp.json()["Systems"]
                                        [self._system]["Gateway_SN"] )
            except IndexError:
                _LOGGER.warning('Specfied system not found. Switching to'
                                + ' first system')
                self._system = 0
                try:
                    self._serial_number= ( resp.json()["Systems"]
                                           [self._system]["Gateway_SN"] )
                except IndexError:
                    _LOGGER.error('No Systems Found.')
        elif resp.status_code == 401:
            _LOGGER.error('Username or password incorrect.')
        else:
            _LOGGER.error('MyiComfort cloud service not responding.')

