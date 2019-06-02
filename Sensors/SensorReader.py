import subprocess
import logging
import re
import sys

from w1thermsensor import W1ThermSensor
from Utility.TemperatureConverter import TemperatureConverter

# TODO is there an Adafruit API that could be used instead of using
# subprocess in _getSensorReadings?


class DS18B20SensorReader():
    '''Class for reading DS18B20 sensors. Will replace the DHT22 code
    eventually. For now this just has a bunch of code from my old version
    pasted in...'''

    def __init__(self, configurations, dbControl):
        self.logger = logging.getLogger(__name__)
        self.logger.info("SensorReader instantiation started")

        # Check from config if data provided by sensors is to be stored as F
        self.fahrenheitConfig = configurations.get("useFahrenheitsConfig")
        # Passed in data to variables for easier use
        self.dbControl = dbControl
        self.configurations = configurations

        self.logger.info("SensorReader instantiated")

    def getSensorReadings(self):
        '''Function for reading data from sensors and collecting it'''
        # Empty list to gather sensor provided readings
        readingsFromSensors = {}

        # Store names of sensors that failed to give information
        # for debugging purposes
        failedSensors = []

        # Sensor readings
        self.logger.info('Starting to collect temperature and humidity data \
        from the the sensors')
        for sensor in self.configurations["sensorConfig"]:
            sensorName = sensor['name']
            # Log entry to indicate what sensor
            self.logger.info(
                'Collecting data for sensor: {0}'.format(sensorName))

            sensorType = sensor['sensorType']
            sensorID = sensor['id']
            temperatureLowLimit = sensor['temperatureLowLimit']
            temperatureHighLimit = sensor['temperatureHighLimit']
            temperatureThreshold = sensor['temperatureThreshold']
            # HumidityLowLimit = sensor['humidityLowLimit']
            # HumidityHighLimit = sensor['humidityHighLimit']
            # humidityThreshold = sensor['humidityThreshold']
            # Try to read values from sensor
            try:
                # Get results for the sensor
                self.logger.info('Get readings for the sensor %s', sensorName)
                # temperature, humidity = self._getSensorReadings(sensorType,
                # gpio)
                temperature = self._getSensorReadings(sensorID, sensorType)

                # Insert inner dictionary with sensor name.
                # Will hold humidity and temperature for the sensor.
                readingsFromSensors[sensorName] = {}

                # Store sensor readings for further use
                # self.logger.info(
                #     'Readings: Temperature: %s , Humidity: %s. Store sensor \
                #     readings for handling', temperature, humidity)
                self.logger.info(
                    'Reading: Temperature: %s. Store sensor \
                    reading for handling', temperature)
                # Float conversions already done in _getSensorReadings
                readingsFromSensors[sensorName]['temperature'] = temperature
                # readingsFromSensors[sensorName]['humidity'] = humidity

                # Store sensor limits for further use
                readingsFromSensors[sensorName]['temperatureLowLimit'] = \
                    float(temperatureLowLimit)
                readingsFromSensors[sensorName]['temperatureHighLimit'] = \
                    float(temperatureHighLimit)
                readingsFromSensors[sensorName]['temperatureThreshold'] = \
                    float(temperatureThreshold)
                # readingsFromSensors[sensorName]['humidityLowLimit'] = \
                #     float(HumidityLowLimit)
                # readingsFromSensors[sensorName]['humidityhighLimit'] = \
                #     float(HumidityHighLimit)
                # readingsFromSensors[sensorName]['humidityThreshold'] = \
                #     float(humidityThreshold)

                # Set data for None
                readingsFromSensors[sensorName]['lastMailSent'] = ""
                readingsFromSensors[sensorName]['lastMeasuredTemperature'] = ""
                # readingsFromSensors[sensorName]['lastMeasuredHumidity'] = ""
                # readingsFromSensors[sensorName]['lastMailSent'] = \
                # "2018-02-21 23:01:42" --testdata

                # self.logger.info(
                #     'Temperature and humidity data from sensor {0} collected'
                #     .format(sensorName))
                self.logger.info(
                    'Temperature data from sensor {0} collected'.format(
                        sensorName))

            except Exception as e:
                self.logger.error(
                    'Failed to get reading for sensor: ' + sensorName + '\n',
                    exc_info=True)
                # If sensor reading raised exception, add sensor to
                # failedSensors list
                failedSensors.append(sensorName)
                continue

            try:
                self.logger.info('Checking when last mail regarding this \
                sensor was sent out. Sensor=%s', sensorName)
                # Check when last warning/email was sent for this sensor
                mailSentTime = \
                    self.dbControl.getLastSensorMailSentTime(sensorName)

                # If there weren't any entries in database and mailSenTime is
                # empty, then it is assumed that this is fresh database
                if mailSentTime is None:
                    self.logger.warning('No entry for last mail sent')
                else:
                    self.logger.info('Last mail regarding this sensor was \
                    sent out on: %s', mailSentTime)
                    readingsFromSensors[sensorName]['lastMailSent'] = \
                        mailSentTime
            except Exception as e:
                self.logger.error('Failed to get entry when last mail \
                regarding this sensor was sent out.\n', exc_info=True)
                raise

            # Get and store information about the last measured temperature
            # and humidity, used later for comparison
            # Testdata:
            # readingsFromSensors[sensorName]['lastMeasuredTemperature'] = 23
            # readingsFromSensors[sensorName]['lastMeasuredHumidity'] = 70
            try:
                self.logger.info('Collecting previously measured values for \
                sensor=%s', sensorName)

                lastMeasuredValues = \
                    self.dbControl.getLastSensorMeasurements(sensorName)
                if lastMeasuredValues is None:
                    self.logger.warning('No previous data found')
                else:
                    # Set data that was read to currently empty variables
                    # TODO: check this against my database structure!
                    readingsFromSensors[sensorName]['lastMeasuredTemperature']\
                        = lastMeasuredValues[2]
                    # readingsFromSensors[sensorName]['lastMeasuredHumidity']\
                    #     = lastMeasuredValues[3]
                    self.logger.info('Previously measured values collected')
            except Exception as e:
                self.logger.error('Failed to get previously measured values \
                for the sensor', exc_info=True)
                raise

        self.logger.info('Sensor readings collected')
        return readingsFromSensors, failedSensors

    def _getSensorReadings(self, sensorID, sensorType):
        '''Private function for reading sensor data. Needs sensor index and
        type in order to work correctly.'''

        self.logger.info(
            "Start reading values for sensor type {0}, ID {1}"
            .format(sensorType, sensorID))

        sensor = W1ThermSensor(_getSensorTypeNum(sensorType), sensorID)

        sensorTemp = sensor.get_temperature(sensor.DEGREES_C)

        self.logger.info("Values from sensor: %s", sensorTemp)

        # If there was no readings, raise exception to indicate that something
        # is wrong with the sensor, somehow...
        if not sensorTemp:
            raise Exception('Failed to get temperature reading')

        self.logger.info('Sensor value reading finished')

        # Finally, check if fahrenheits are wanted
        if self.fahrenheitConfig.lower() == "y":
            self.logger.warning("Fahrenheits enabled in configurations. \
            Converting sensor temperature reading to fahrenheits")

            # If yes, instantiate converter and convert celsius to fahrenheits
            converter = TemperatureConverter()
            sensorTemp = converter.celsiusToFahrenheits(sensorTemp)
        else:
            self.logger.info('Sensor temperature values as celsius')

        # not needed right now, I don't think
        # sensorTemperatureF = sensorTemperature * 1.8 + 32

        return sensorTemp

    def _getSensorTypeNum(self, typeString):
        '''private function for converting sensor type name to sensor type
        numerical code. Only needed because the w1thermsensor library doesn't
        let you pass the type name to __init__...'''
        conversion = {"DS18S20": 0x10,
                      "DS1822": 0x22,
                      "DS18B20": 0x28,
                      "DS1825": 0x3B,
                      "DS28EA00": 0x42,
                      "MAX31850K": 0x3B}

        return conversion[typeString]


class SensorReader():
    '''Class for reading DHT22 sensors'''

    def __init__(self, configurations, dbControl):
        self.logger = logging.getLogger(__name__)
        self.logger.info("SensorReader instantiation started")

        # Get path where sensor library is
        self.adafruitPathConfig = configurations.get("adafruitPathConfig")
        # Check from config if data provided by sensors is to be stored as F
        self.fahrenheitConfig = configurations.get("useFahrenheitsConfig")
        # Passed in data to variables for easier use
        self.dbControl = dbControl
        self.configurations = configurations

        self.logger.info("SensorReader instantiated")

    def getSensorReadings(self):
        '''Function for reading data from sensors and collecting it'''
        # Empty list to gather sensor provided readings
        readingsFromSensors = {}

        # Store names of sensors that failed to give information
        # for debugging purposes
        failedSensors = []

        # Sensor readings
        self.logger.info('Starting to collect temperature and humidity data \
        from the the sensors')
        for sensor in self.configurations["sensorConfig"]:

            # Set sensor name, gpio and type to variables for easier use
            sensorName = sensor[0]['name']
            # Log entry to indicate what sensor
            self.logger.info(
                'Collecting data for sensor: {0}'.format(sensorName))

            gpio = sensor[1]['gpio']
            sensorType = sensor[2]['sensorType']
            temperatureLowLimit = sensor[3]['temperatureLowLimit']
            temperatureHighLimit = sensor[4]['temperatureHighLimit']
            temperatureThreshold = sensor[5]['temperatureThreshold']
            HumidityLowLimit = sensor[6]['humidityLowLimit']
            HumidityHighLimit = sensor[7]['humidityHighLimit']
            humidityThreshold = sensor[8]['humidityThreshold']

            # Try to read values from sensor
            try:
                # Get results for the sensor
                self.logger.info('Get readings for the sensor %s', sensorName)
                temperature, humidity = \
                    self._getSensorReadings(sensorType, gpio)

                # Insert inner dictionary with sensor name.
                # Will hold humidity and temperature for the sensor.
                readingsFromSensors[sensorName] = {}

                # Store sensor readings for further use
                self.logger.info(
                    'Readings: Temperature: %s , Humidity: %s. Store sensor \
                    readings for handling', temperature, humidity)
                # Float conversions already done in _getSensorReadings
                readingsFromSensors[sensorName]['temperature'] = temperature
                readingsFromSensors[sensorName]['humidity'] = humidity

                # Store sensor limits for further use
                readingsFromSensors[sensorName]['temperatureLowLimit'] = \
                    float(temperatureLowLimit)
                readingsFromSensors[sensorName]['temperatureHighLimit'] = \
                    float(temperatureHighLimit)
                readingsFromSensors[sensorName]['temperatureThreshold'] = \
                    float(temperatureThreshold)
                readingsFromSensors[sensorName]['humidityLowLimit'] = \
                    float(HumidityLowLimit)
                readingsFromSensors[sensorName]['humidityhighLimit'] = \
                    float(HumidityHighLimit)
                readingsFromSensors[sensorName]['humidityThreshold'] = \
                    float(humidityThreshold)

                # Set data for None
                readingsFromSensors[sensorName]['lastMailSent'] = ""
                readingsFromSensors[sensorName]['lastMeasuredTemperature'] = ""
                readingsFromSensors[sensorName]['lastMeasuredHumidity'] = ""
                # readingsFromSensors[sensorName]['lastMailSent'] = \
                # "2018-02-21 23:01:42" --testdata

                self.logger.info(
                    'Temperature and humidity data from sensor {0} collected'
                    .format(sensorName))

            except Exception as e:
                self.logger.error(
                    'Failed to get readings for sensor: ' + sensorName + '\n',
                    exc_info=True)
                # If sensor reading raised exception, add sensor to
                # failedSensors list
                failedSensors.append(sensorName)
                continue

            try:
                self.logger.info('Checking when last mail regarding this \
                sensor was sent out. Sensor=%s', sensorName)
                # Check when last warning/email was sent for this sensor
                mailSentTime = \
                    self.dbControl.getLastSensorMailSentTime(sensorName)

                # If there weren't any entries in database and mailSenTime is
                # empty, then it is assumed that this is fresh database
                if mailSentTime is None:
                    self.logger.warning('No entry for last mail sent')
                else:
                    self.logger.info('Last mail regarding this sensor was \
                    sent out on: %s', mailSentTime)
                    readingsFromSensors[sensorName]['lastMailSent'] = \
                        mailSentTime
            except Exception as e:
                self.logger.error('Failed to get entry when last mail \
                regarding this sensor was sent out.\n', exc_info=True)
                raise

            # Get and store information about the last measured temperature
            # and humidity, used later for comparison
            # Testdata:
            # readingsFromSensors[sensorName]['lastMeasuredTemperature'] = 23
            # readingsFromSensors[sensorName]['lastMeasuredHumidity'] = 70
            try:
                self.logger.info('Collecting previously measured values for \
                sensor=%s', sensorName)

                lastMeasuredValues = \
                    self.dbControl.getLastSensorMeasurements(sensorName)
                if lastMeasuredValues is None:
                    self.logger.warning('No previous data found')
                else:
                    # Set data that was read to currently empty variables
                    readingsFromSensors[sensorName]['lastMeasuredTemperature']\
                        = lastMeasuredValues[2]
                    readingsFromSensors[sensorName]['lastMeasuredHumidity']\
                        = lastMeasuredValues[3]
                    self.logger.info('Previously measured values collected')
            except Exception as e:
                self.logger.error('Failed to get previously measured values \
                for the sensor', exc_info=True)
                raise

        self.logger.info('Sensor readings collected')
        return readingsFromSensors, failedSensors

    def _getSensorReadings(self, sensorType, gpio):
        '''Private function for reading sensor data. Needs sensor type e.g. 22
        and gpio where it is attached in RPI'''
        self.logger.info(
            "Start reading values for sensor type {0} in gpio {1}"
            .format(sensorType, gpio))

        # Pop up subprocess and use adafruit library to get readings
        sensorReadings = subprocess.check_output(
            ['sudo', self.adafruitPathConfig, sensorType, gpio])
        # Test readings, uncomment if needed:
        # sensorReadings = "Temp=23.0 Humidity=58.6%"

        self.logger.info("Values from sensor: %s", sensorReadings)

        # It there was no readings, raise exception to indicate that something
        # is wrong with gpio xx
        # If there is nothing in sensor readings, or it contains words
        # 'Try again!' we know that something went wrong
        if not sensorReadings or re.search('Try again!', sensorReadings):
            raise Exception('Failed to get readings')

        # Check if values are negative or positive
        try:
            # try to read neagtive numbers
            self.logger.info(
                'Check is measured temperature negative or positive')
            # Search for 'Temp=-' if it is found, then value is negative
            negative = re.search('Temp=-', sensorReadings)
            # If nothing found, then value is assumed to be positive
            if negative is None:
                self.logger.info('Value is positive')
                temperature = re.findall(r"Temp=(\d+.\d+)", sensorReadings)[0]
            else:
                self.logger.info('Value is negative')
                temperature = re.findall(r"Temp=(-\d+.\d+)", sensorReadings)[0]

            self.logger.info('Read humidity readings')
            # Read humidity
            humidity = re.findall(r"Humidity=(\d+.\d+)", sensorReadings)[0]
        except:
            raise Exception('Error reading temperature/humidity values from \
            string returned by sensor')

        self.logger.info('Cast temperature and humidity readings to float')
        # Casting to float
        floatTemp = float(temperature)
        floatHumidity = float(humidity)

        self.logger.info('Sensor value reading finished')

        # Finally check if fahrenheits are wanted
        if self.fahrenheitConfig.lower() == "y":
            self.logger.warning("Fahrenheits enabled in configurations. \
            Converting sensor temperature reading to fahrenheits")

            # If yes, instantiate converter and convert celsius to fahrenheits
            converter = TemperatureConverter()
            floatTemp = converter.celsiusToFahrenheits(floatTemp)
        else:
            self.logger.info('Sensor temperature values as celsius')

        return floatTemp, floatHumidity
