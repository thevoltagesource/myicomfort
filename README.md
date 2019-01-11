# PyPI - myicomfort
### API Wrapper for www.myicomfort.com

By Jacob Southard (https://github.com/thevoltagesource)  
Based on the work of Jerome Avondo (https://github.com/ut666)

Read and adjust your Lennox iComfort WiFi thermostat thru the Lennox cloud API
at www.myicomfort.com. You must have an existing myicomfort account and
have your iComfort WiFi thermostat configured to work with the cloud service.
If you can control your thermostat from your iPhone or Android you are ready to
use this wrapper.

This was created primarly to provide an API for use with https://www.home-assistant.io/
but should work on any project you have in mind.

##### Class:  
myicomfort.api.Tstat (username, password, system, zone, units)

* username: your myicomfort account username
* password: your myicomfort account password
* system: Zero-based index of systems in your myicomfort account (default = 0)
* zone: Zero-based index of zones for selected system (default = 0)
* units: F = 0, C = 1, Use thermostat setting = 9 (default = 9)

##### Example:
```python
from myicomfort.api import Tstat

t = Tstat('username', 'password', 0, 0, 0)
t.current_temperature
t.set_points((68, 75))
```

##### Notes:
* This API currently only supports manual mode (no programs) on the thermostat. 

##### Cloud API Response Notes:
* Pref_Temp_Units: [0='F', 1='C']
* Operation_Mode: [0='Off', 1='Heat only', 2='Cool only', 3='Heat & Cool']
* Fan_Mode: [0='Auto', 1='On', 2='Circulate']
* System_Status: [0='Idle', 1='Heating', 2='Cooling']

##### Ideas/Future:
* Support thermostat programs
* Set Away temps - Research if possible through cloud API
* Support other states - dehumidify / waiting
