import machine
import math
import network
import os
import time
import gc
import pycom
import socket
import ssl
import rsa
import microjwt as jwt
import urequests as requests
from machine import RTC
from machine import SD
from L76GNSS_fork import L76GNSS
from pytrack import Pytrack
from network import WLAN
from network import LTE
from LIS2HH12 import LIS2HH12
#from mqtt import MQTTClient
from ubinascii import b2a_base64
import string
import config
#from http.client import HTTPConnection

gc.enable()
pycom.heartbeat(False)
lte = None
wlan = None
current_jwt = None
py = Pytrack()
l76 = L76GNSS(py, timeout=30)
acc = LIS2HH12()
TOKEN_VALIDITY = 3600

def rgb_to_hex(red, green, blue):
    "Return color as #rrggbb for the given color values."
    return '%02x%02x%02x' % (red, green, blue)

def led_color(brightness):
    if not wlan == None:
        return rgb_to_hex(0, brightness, 0)
    if not lte == None:
        return rgb_to_hex(0, 0, brightness)
    return rgb_to_hex(brightness, 0, 0)

def led_Breathe():
    for i in range(0,75):
        color = led_color(i)
        pycom.rgbled(int(color,16))
        time.sleep(0.040)
    for i in range(75,0,-1):
        color = led_color(i)
        pycom.rgbled(int(color,16))
        time.sleep(0.040)
    pycom.rgbled(0x000000)

# Returns True when lte global has an LTE object with an active Internet connection.
# Always first update the gpy to latest modem firmware
# https://docs.pycom.io/tutorials/lte/firmware.html
def get_LTE():
    global lte
    if lte == None:
        lte = LTE()
    if lte.isconnected():
        return True
    # lte.reset()
    # lte.send_at_cmd('AT+CGDCONT=1,"IP","nbiot.iot"')
    lte.attach(band=20, apn="nbiot.iot")
    while not lte.isattached():
        print('Attaching...')
        time.sleep(1)
    print('LTE attach succeeded!')
    lte.connect()
    while not lte.isconnected():
        print('Connecting...')
        time.sleep(1)
    print('LTE connection succeeded!')
    return True

# Clean disconnection of the LTE network is required for future
# successful connections without a complete power cycle between.
def end_LTE():
    global lte
    if lte == None:
        return
    print("Disonnecting LTE ... ")
    lte.disconnect()
    print("OK")
    print("Detaching LTE ... ")
    lte.dettach()
    print("OK")
    print("Shuttting down LTE...")
    lte.deinit()
    print("OK")
    lte = None

def get_WLAN():
    global wlan
    if wlan == None:
        wlan = WLAN(mode=WLAN.STA)
    if wlan.isconnected():
        return True
    nets = wlan.scan()
    for net in nets:
        if net.ssid == config.WLAN_SSID:
            print('Network found!')
            wlan.connect(net.ssid, auth=(net.sec, config.WLAN_WPA), timeout=5000)
            attempts = 0
            while (not wlan.isconnected()) and (attempts < 10):
                print('Connecting...')
                attempts = attempts + 1
                time.sleep(1)
            if wlan.isconnected():
                print('WLAN connection succeeded')
                return True
            else:
                print('WLAN connection failed')
                end_WLAN()
                return False
        else:
            end_WLAN()
            return False

def end_WLAN():
    global wlan
    if wlan == None:
        return
    print("Disonnecting WLAN ... ")
    wlan.disconnect()
    print("OK")
    print("Shuttting down WLAN...")
    wlan.deinit()
    print("OK")
    wlan = None
            
# Set the internal real-time clock.
def set_RTC():
    rtc = machine.RTC()
    # dns lookup on nb-iot does not work...
    # rtc.ntp_sync("pool.ntp.org")
    rtc.ntp_sync('193.190.253.212')
    time.sleep_ms(750)
    print('\nRTC Set from NTP to UTC:', rtc.now())
    time.timezone(3600)
    print('Adjusted from UTC to EST timezone', time.localtime(), '\n')

def b42_urlsafe_encode(payload):
    return string.translate(b2a_base64(payload)[:-1].decode('utf-8'),{ ord('+'):'-', ord('/'):'_' })

# def get_mqtt_client(project_id, cloud_region, registry_id, device_id, private_key):
#     """Create our MQTT client. The client_id is a unique string that identifies
#     this device. For Google Cloud IoT Core, it must be in the format below."""
#     client_id = 'projects/{}/locations/{}/registries/{}/devices/{}'.format(project_id, cloud_region, registry_id, device_id)
#     password = create_jwt(project_id, private_key, 'RS256')
#     print('Sending message with password {}'.format(password))
#     return MQTTClient(client_id,'mqtt.googleapis.com',8883,user='ignored',password=password,ssl=True)

def send_http_payload(project_id, cloud_region, registry_id, device_id, private_key, payload):
    global current_jwt
    if current_jwt == None or not current_jwt.isValid():
        current_jwt = jwt.new(project_id, private_key, 'RS256', TOKEN_VALIDITY)
    url = 'https://cloudiotdevice.googleapis.com/v1/projects/{}/locations/{}/registries/{}/devices/{}:publishEvent'.format(project_id, cloud_region, registry_id, device_id)
    print('sending...')
    print(payload)    
    # payload = '{}/{}/payload-{}'.format(registry_id, device_id, payload)
    data = { 'binary_data': b42_urlsafe_encode(payload) }
    request = requests.post(url, json=data, headers={"authorization": "Bearer {}".format(current_jwt.encodedValue()), "cache-control": "no-cache"})
    print('sent!')
    request.close()

# sd = SD()
# os.mount(sd, '/sd')
# f = open('/sd/gps-record.txt', 'w')​

def ensure_network():
    if get_WLAN():
        if not lte == None:
            end_LTE()
    if wlan == None:
        get_LTE()
    if lte == None:
        return False
    else:
        return True

def end_network():
    if not lte == None:
        end_LTE()
    if not wlan == None:
        end_WLAN()

try:
    ensure_network()
    set_RTC()
    while (True):
        led_Breathe()
        coord = l76.position()
        pitch = acc.pitch() 
        roll = acc.roll()
        if not coord[0] == None:
            ensure_network()
            now = machine.RTC().now()
            isodatetime = "{}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}+00:00".format(now[0],now[1],now[2],now[3],now[4],now[5],now[6])
            volt = py.read_battery_voltage()
            send_http_payload(config.project_id, config.cloud_region, config.registry_id, config.device_id, config.private_key,
                              '{{"timestamp":"{}","lat":{},"lon":{},"alt":{},"pitch":{},"roll":{},"volt":{}}}'.format(isodatetime,coord[0], coord[1], coord[2], pitch, roll,volt))
        else:
            print('No position to send')
        time.sleep(60)

finally:
    end_network()