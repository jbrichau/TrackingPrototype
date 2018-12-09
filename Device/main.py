import machine
import math
import network
import os
import time
import utime
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
py = Pytrack()
l76 = L76GNSS(py, timeout=30)
acc = LIS2HH12()
TOKEN_VALIDITY = 3600

def led_Breathe():
    if not wlan == None:
        color = 0x84de02
    if not lte == None:
        color = 0x3355ff
    pycom.rgbled(color)
    time.sleep(1)
    # for i in range(256):
    #     pycom.rgbled(i)
    #     time.sleep(0.005)
    # for i in range(256):
    #     pycom.rgbled(256-i)
    #     time.sleep(0.005)
    pycom.rgbled(0x000000)

# Returns a network.LTE object with an active Internet connection.
# Always first update the gpy to latest modem firmware
# https://docs.pycom.io/tutorials/lte/firmware.html
def get_LTE():
    global lte
    if lte == None:
        lte = LTE()
    if lte.isconnected():
        return lte
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
        return wlan
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
    utime.sleep_ms(750)
    print('\nRTC Set from NTP to UTC:', rtc.now())
    utime.timezone(3600)
    print('Adjusted from UTC to EST timezone', utime.localtime(), '\n')

def b42_urlsafe_encode(payload):
    return string.translate(b2a_base64(payload)[:-1].decode('utf-8'),{ ord('+'):'-', ord('/'):'_' })

def create_jwt(project_id, private_key, algorithm):
    token = {
            # The time that the token was issued at
            'iat': utime.time(),
            # The time the token expires.
            'exp': utime.time() + TOKEN_VALIDITY,
            # The audience field should always be set to the GCP project id.
            'aud': project_id
    }
    print('Creating JWT with token {}'.format(token))
    return jwt.encode(token, private_key, algorithm)

# def get_mqtt_client(project_id, cloud_region, registry_id, device_id, private_key):
#     """Create our MQTT client. The client_id is a unique string that identifies
#     this device. For Google Cloud IoT Core, it must be in the format below."""
#     client_id = 'projects/{}/locations/{}/registries/{}/devices/{}'.format(project_id, cloud_region, registry_id, device_id)
#     password = create_jwt(project_id, private_key, 'RS256')
#     print('Sending message with password {}'.format(password))
#     return MQTTClient(client_id,'mqtt.googleapis.com',8883,user='ignored',password=password,ssl=True)

def send_http_payload(project_id, cloud_region, registry_id, device_id, private_key, payload):
    jwt = create_jwt(project_id, private_key, 'RS256')
    url = 'https://cloudiotdevice.googleapis.com/v1/projects/{}/locations/{}/registries/{}/devices/{}:publishEvent'.format(project_id, cloud_region, registry_id, device_id)
    payload = '{}/{}/payload-{}'.format(registry_id, device_id, payload)
    data = { 'binary_data': b42_urlsafe_encode(payload) }
    request = requests.post(url, json=data, headers={"authorization": "Bearer {}".format(jwt), "cache-control": "no-cache"})
    print(request.text)
    request.close()

# sd = SD()
# os.mount(sd, '/sd')
# f = open('/sd/gps-record.txt', 'w')​

# main program
try:
    # get_WLAN()
    get_LTE()

    set_RTC()
    coord = l76.position()
    pitch = acc.pitch() 
    roll = acc.roll() 

    led_Breathe()
    send_http_payload(config.project_id, config.cloud_region, config.registry_id, config.device_id, config.private_key,
                      "{} - {} - {},{}".format(coord, machine.RTC().now(), pitch, roll))

finally:
    if not lte == None:
        end_LTE()
    if not wlan == None:
        end_WLAN()

# while (True):
#     led_Breathe()
