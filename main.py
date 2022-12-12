# The final one?

import time
import board

import adafruit_gps


import subprocess
from digitalio import DigitalInOut, Direction
from PIL import Image, ImageDraw, ImageFont
from adafruit_rgb_display import st7789

import adafruit_bme680

import sys

# for a computer, use the pyserial library for uart access
import serial
from tinydb import TinyDB, Query
from datetime import datetime

import logging

# Input pins:
button_A = DigitalInOut(board.D5)
button_A.direction = Direction.INPUT

if not button_A.value:  # pressed when start
    print("MANUAL EXIT!!!!")
    sys.exit()

temp5 = str(datetime.now()).replace(" ", "_")+".log"

logging.basicConfig(filename='logs/logFile_'+temp5, encoding='utf-8', level=logging.DEBUG)


class envSen():

    def __init__(self):
    
    
        self.debug = False
        self.tacTime = 20. # seconds
        self.dbEntryLimit = 1000 # DB entry limit
        
        self.bme688_temp_offset = -2.5
        
        self.var_gpsFix = None
        self.var_IP = None
        self.var_CPU = None
        self.var_MemUsage = None
        self.var_Disk = None
        self.var_Temp = None
        
        
    def initGPS(self):
        
        try:
            gps_uart = serial.Serial("/dev/ttyUSB0", baudrate=9600, timeout=int(self.tacTime) + 5)
            self.bt_ser = serial.Serial()

            # Create a GPS module instance.
            self.gps = adafruit_gps.GPS(gps_uart, debug=False)  # Use UART/pyserial

            # Initialize the GPS module by changing what data it sends and at what rate.
            # These are NMEA extensions for PMTK_314_SET_NMEA_OUTPUT and
            # PMTK_220_SET_NMEA_UPDATERATE but you can send anything from here to adjust
            # the GPS module behavior:
            #   https://cdn-shop.adafruit.com/datasheets/PMTK_A11.pdf

            # Turn on the basic GGA and RMC info (what you typically want)
            self.gps.send_command(b"PMTK314,0,1,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0")
            
            # Turn on just minimum info (RMC only, location):
            # gps.send_command(b'PMTK314,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0')
            
            # Turn off everything:
            # gps.send_command(b'PMTK314,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0')
            
            # Turn on everything (not all of it is parsed!)
            # gps.send_command(b'PMTK314,1,1,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0')

            # Set update rate to once a second (1hz) which is what you typically want.
            
            updateRateCmd = f"PMTK220,{int(self.tacTime * 1000)}"
            
            self.gps.send_command(updateRateCmd.encode('ascii'))
            # Or decrease to once every two seconds by doubling the millisecond value.
            # Be sure to also increase your UART timeout above!
            # gps.send_command(b'PMTK220,2000')
            # You can also speed up the rate, but don't go too fast or else you can lose
            # data during parsing.  This would be twice a second (2hz, 500ms delay):
            # gps.send_command(b'PMTK220,500')

            # Main loop runs forever printing the location, etc. every second.
            self.last_print = time.monotonic()
            
            return True
            
        except Exception as e:
            logging.critical(e)
            return False


    def initBME688(self):

        try:
            ## SME SENSOR RELATED
            # Configuring the BME688 sensor
            i2c = board.I2C()
            self.bme688_sensor = adafruit_bme680.Adafruit_BME680_I2C(i2c)
            self.bme688_sensor.sea_level_pressure = 1028.25
            
            return True
            
        except Exception as e:
            logging.critical(e)
            return False

    def initDisplay(self):

        try:

            ## SPI DISPLAY RELATED

            # Setup SPI bus using hardware SPI:
            spi = board.SPI()

            # Create the display
            cs_pin = DigitalInOut(board.CE0)
            dc_pin = DigitalInOut(board.D25)
            reset_pin = DigitalInOut(board.D24)
            BAUDRATE = 24000000

            # Create the ST7789 display:
            self.disp = st7789.ST7789(
                spi,
                height=240,
                y_offset=80,
                rotation=180,
                cs=cs_pin,
                dc=dc_pin,
                rst=reset_pin,
                baudrate=BAUDRATE,
            )

            # Turn on the Backlight
            backlight = DigitalInOut(board.D26)
            backlight.switch_to_output()
            backlight.value = True

            # Create blank image for drawing.
            # Make sure to create image with mode 'RGB' for full color.
            self.height = self.disp.width  # we swap height/width to rotate it to landscape!
            self.width = self.disp.height
            self.image = Image.new("RGB", (self.width, self.height))
            self.rotation = 90

            # Get drawing object to draw on image.
            self.draw = ImageDraw.Draw(self.image)

            # Draw a black filled box to clear the image.
            self.draw.rectangle((0, 0, self.width, self.height), outline=0, fill=(255, 0, 0))
            self.disp.image(self.image, self.rotation)
            # Draw some shapes.
            # First define some constants to allow easy resizing of shapes.
            padding = -2
            self.top = padding
            self.bottom = self.height - padding
            # Move left to right keeping track of the current x position for drawing shapes.
            self.x = 0


            # Alternatively load a TTF font.  Make sure the .ttf font file is in the
            # same directory as the python script!
            # Some other nice fonts to try: http://www.dafont.com/bitmap.php
            self.font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
            
            return True
            
        except Exception as e:
            logging.critical(e)
            return False

    def initDB(self):
    
        try: 

            # Creating Tiny DB
            current_datetime = datetime.now()
            print("Current date & time : ", current_datetime)
            str_current_datetime = str(current_datetime)
            
            self.db = TinyDB("logs/"+str_current_datetime.replace(" ", "_")+".json")
            
            self.dbEntryNo = 0
            
            return True
            
        except Exception as e:
            logging.critical(e)
            return False


    def printBoth(self,msg):

        if self.debug:
            print(msg)
            
        msg = msg + "\n"
        
        
        try:
            self.bt_ser.port = '/dev/rfcomm0'
            self.bt_ser.open()# open serial port
            self.bt_ser.write(msg.encode('UTF-8'))
            self.bt_ser.close()
            
            return True
            
        except Exception as e:
        
            if self.debug:
        
                print("no Bluetooth device found")
                logging.critical(e)
                
            return False
            


    def getGPSupdate(self):
        # Make sure to call gps.update() every loop iteration and at least twice
        # as fast as data comes from the GPS unit (usually every second).
        # This returns a bool that's true if it parsed new data (you can ignore it
        # though if you don't care and instead look at the has_fix property).
        
        '''
        
        ################## VAR LIST ######################
        
        self._uart = uart
        # Initialize null starting values for GPS attributes.
        self.timestamp_utc = None
        self.latitude = None
        self.latitude_degrees = None
        self.latitude_minutes = None  # Use for full precision minutes
        self.longitude = None
        self.longitude_degrees = None
        self.longitude_minutes = None  # Use for full precision minutes
        self.fix_quality = 0
        self.fix_quality_3d = 0
        self.satellites = None
        self.satellites_prev = None
        self.horizontal_dilution = None
        self.altitude_m = None
        self.height_geoid = None
        self.speed_knots = None
        self.track_angle_deg = None
        self._sats = None  # Temporary holder for information from GSV messages
        self.sats = None  # Completed information from GSV messages
        self.isactivedata = None
        self.true_track = None
        self.mag_track = None
        self.sat_prns = None
        self.sel_mode = None
        self.pdop = None
        self.hdop = None
        self.vdop = None
        self.total_mess_num = None
        self.mess_num = None
        self._raw_sentence = None
        self._mode_indicator = None
        self._magnetic_variation = None
        self.debug = debug
        
        '''
        
        try:
        
            self.gps.update()
            # Every second print out current location details if there's a fix.
            self.current = time.monotonic()
            if self.current - self.last_print >= self.tacTime:
                self.last_print = self.current
                if not self.gps.has_fix:
                    # Try again if we don't have a fix yet.
                    printStat = self.printBoth("Waiting for fix...")
                    self.var_gpsFix = False
                    return False
                
                self.var_gpsFix = True
                return True

        except Exception as e:
            logging.critical(e)
        
            self.var_gpsFix = "GPS Error"
            return False

    def printGPS(self):

        # Print out details about the fix like location, date, etc.
        self.printBoth("=" * 40)  # Print a separator line.
        self.printBoth(
            "Fix timestamp: {}/{}/{} {:02}:{:02}:{:02}".format(
                self.gps.timestamp_utc.tm_mon,  # Grab parts of the time from the
                self.gps.timestamp_utc.tm_mday,  # struct_time object that holds
                self.gps.timestamp_utc.tm_year,  # the fix time.  Note you might
                self.gps.timestamp_utc.tm_hour,  # not get all data like year, day,
                self.gps.timestamp_utc.tm_min,  # month!
                self.gps.timestamp_utc.tm_sec,
            )
        )
        self.printBoth("Latitude: {0:.6f} degrees".format(self.gps.latitude))
        self.printBoth("Longitude: {0:.6f} degrees".format(self.gps.longitude))
        # self.printBoth(
            # "Precise Latitude: {:2.f}{:2.4f} degrees".format(
                # self.gps.latitude_degrees, self.gps.latitude_minutes
            # )
        # )
        # self.printBoth(
            # "Precise Longitude: {:2.f}{:2.4f} degrees".format(
                # self.gps.longitude_degrees, self.gps.longitude_minutes
            # )
        # )
        self.printBoth("Fix quality: {}".format(self.gps.fix_quality))
        # Some attributes beyond latitude, longitude and timestamp are optional
        # and might not be present.  Check if they're None before trying to use!
        if self.gps.satellites is not None:
            self.printBoth("# satellites: {}".format(self.gps.satellites))
            
        if self.gps.altitude_m is not None:
            self.printBoth("Altitude: {} meters".format(self.gps.altitude_m))
            
        if self.gps.speed_knots is not None:
            self.printBoth("Speed: {} knots".format(self.gps.speed_knots))
            
        if self.gps.track_angle_deg is not None:
            self.printBoth("Track angle: {} degrees".format(self.gps.track_angle_deg))
            
        if self.gps.horizontal_dilution is not None:
            self.printBoth("Horizontal dilution: {}".format(self.gps.horizontal_dilution))
            
        if self.gps.height_geoid is not None:
            self.printBoth("Height geoid: {} meters".format(self.gps.height_geoid))
            
        self.printBoth("=" * 40)  # Print a separator line.


    def getSysParams(self):
    
        try:
    
            # Shell scripts for system monitoring from here:
            # https://unix.stackexchange.com/questions/119126/command-to-display-memory-usage-disk-usage-and-cpu-load
            cmd = "hostname -I | cut -d' ' -f1"
            self.var_IP = subprocess.check_output(cmd, shell=True).decode("utf-8")
            cmd = "top -bn1 | grep load | awk '{printf \"CPU Load: %.2f\", $(NF-2)}'"
            self.var_CPU = subprocess.check_output(cmd, shell=True).decode("utf-8")
            cmd = "free -m | awk 'NR==2{printf \"Mem: %s/%s MB  %.2f%%\", $3,$2,$3*100/$2 }'"
            self.var_MemUsage = subprocess.check_output(cmd, shell=True).decode("utf-8")
            cmd = 'df -h | awk \'$NF=="/"{printf "Disk: %d/%d GB  %s", $3,$2,$5}\''
            self.var_Disk = subprocess.check_output(cmd, shell=True).decode("utf-8")
            cmd = "cat /sys/class/thermal/thermal_zone0/temp |  awk '{printf \"CPU Temp: %.1f C\", $(NF-0) / 1000}'"  # pylint: disable=line-too-long
            self.var_Temp = subprocess.check_output(cmd, shell=True).decode("utf-8")
            
            return True
            
        except Exception as e:
            logging.critical(e)

            return False
            


    def updateScreen(self):
    
        # Draw a black filled box to clear the image.
        self.draw.rectangle((0, 0, self.width, self.height), outline=0, fill=0)
        
        y = self.top
        x = self.x
        for key in self.vars2disp:
        
            if isinstance(self.vars2disp[key], float):
                dispString = f"{key}: {self.vars2disp[key]:.4f}"
            else:
                dispString = f"{key}: {self.vars2disp[key]}"
            
            self.draw.text((x,y), dispString, font = self.font, fill="#FFFFFF")
            y += self.font.getsize(dispString)[1]
        self.disp.image(self.image, self.rotation)

        

    def writeScreenDB(self):
        for key in self.vars2disp:
            dispString = f"{key}: {self.vars2disp[key]}"
            self.printBoth(dispString)
        
        self.printBoth("\n")        
        self.dbEntryNo = self.db.insert(self.vars2disp | self.vars2log)
        
        time.sleep(self.tacTime)
        
        
    def setVars(self):
    
        '''
        "Fix timestamp: {}/{}/{} {:02}:{:02}:{:02}".format(
        self.gps.timestamp_utc.tm_mon,  # Grab parts of the time from the
        self.gps.timestamp_utc.tm_mday,  # struct_time object that holds
        self.gps.timestamp_utc.tm_year,  # the fix time.  Note you might
        self.gps.timestamp_utc.tm_hour,  # not get all data like year, day,
        self.gps.timestamp_utc.tm_min,  # month!
        self.gps.timestamp_utc.tm_sec,
        '''
        
        if self.gps.timestamp_utc != None:
    
            timeStamp = "{}/{}/{} {:02}:{:02}:{:02}".format(
            self.gps.timestamp_utc.tm_mday,  # Grab parts of the time from the
            self.gps.timestamp_utc.tm_mon,  # struct_time object that holds
            self.gps.timestamp_utc.tm_year,  # the fix time.  Note you might
            self.gps.timestamp_utc.tm_hour,  # not get all data like year, day,
            self.gps.timestamp_utc.tm_min,  # month!
            self.gps.timestamp_utc.tm_sec)
            
        else:
        
            timeStamp = None
        
        self.vars2disp = { 'Time': timeStamp,
                            'IP': self.var_IP[:-1],
                            'Temp    (C)': self.bme688_sensor.temperature + self.bme688_temp_offset,
                            'Humidity(%)': self.bme688_sensor.humidity,
                            'Press (mPa)': self.bme688_sensor.pressure,
                            'Sen-Alt (m)': self.bme688_sensor.altitude,
                            'senGas(ohm)': self.bme688_sensor.gas,
                            'GPS-Fix (m)': self.var_gpsFix,
                            'GPS-Alt (m)': self.gps.altitude_m,
                            'Latitude   ': self.gps.latitude,
                            'Longitude  ': self.gps.longitude,
                            'NoOfSats(#)': self.gps.satellites,
                            
        
        }
        
        self.vars2log = { 'GPSraw': self.gps._raw_sentence,
                          'temp-Offset': self.bme688_temp_offset,
                        }

    



    def updateErrorOnScreen(self,e):
    
        # Draw a black filled box to clear the image.
        self.draw.rectangle((0, 0, self.width, self.height), outline=0, fill=0)
        
        y = self.top
        x = self.x
        
        self.draw.text((x,y), "***********************", font = self.font, fill="#FFFFFF")
        y += self.font.getsize("******")[1]
        self.draw.text((x,y), e, font = self.font, fill="#FFFFFF")
        y += self.font.getsize("******")[1]
        self.draw.text((x,y), "***********************", font = self.font, fill="#FFFFFF")
        y += self.font.getsize("******")[1]
        
        self.disp.image(self.image, self.rotation)

def main():

    sensorInstance = envSen()
    
    gpsStat = sensorInstance.initGPS()
    dispStat = sensorInstance.initDisplay()
    bmeStat = sensorInstance.initBME688()
    dbStat = sensorInstance.initDB()
    
    
    print(f'GPS Stat: {gpsStat}')
    # print(f'Disp Stat: {dispStat}')
    print(f'BME Stat: {bmeStat}')
    print(f'DB Stat: {dbStat}')

    while True:
        
#        try:
        
        if sensorInstance.getGPSupdate():
            sensorInstance.printGPS()
            
         # # re-initiate the GPS incase of error due to startup serial coms issue
        # if sensorInstance.var_gpsFix == "GPS Error":
            # gpsStat = sensorInstance.initGPS()
            
        sensorInstance.getSysParams()
        
        sensorInstance.setVars()
        
        sensorInstance.updateScreen()
        sensorInstance.writeScreenDB()
        
        if sensorInstance.dbEntryNo == sensorInstance.dbEntryLimit:
            dbStat = sensorInstance.initDB()
                
#        except Exception as e:
#            sensorInstance.updateErrorOnScreen('Borked!!')
#            break
#            sensorInstance.updateErrorOnScreen('Not Exiting!!')


if __name__ == "__main__":
    print('**************** STARTING PROGRAM AS MAIN FILE!!!')

    # Comment to stop CRON job
    
    main()

