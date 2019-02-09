import machine
import math
import network
import socket
import os
import time
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
from network import Server
import string
import config

lte = None
wlan = None
server = None
current_jwt = None
py = Pytrack()
l76 = L76GNSS(py, timeout=30)
acc = LIS2HH12()
sd = SD()
os.mount(sd, '/sd')
TOKEN_VALIDITY = 3600
MEASURE_INTERVAL = 60

def debugprint(string):
    now = machine.RTC().now()
    isodatetime = "{}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}+00:00 - ".format(now[0],now[1],now[2],now[3],now[4],now[5],now[6])
    print(isodatetime + string)
    debuglog = open('/sd/debuglog.txt', 'a')
    debuglog.write(isodatetime + string + '\n')
    debuglog.close()

def loggps(coord):
    gpslog = open('/sd/gpslog.txt', 'a')
    gpslog.write(coord+'\n')
    gpslog.close()

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
        time.sleep(0.010)
    time.sleep(0.500)
    for i in range(75,0,-1):
        color = led_color(i)
        pycom.rgbled(int(color,16))
        time.sleep(0.010)
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
    if (not lte.isattached()):
        lte.attach(band=20, apn="nbiot.iot")
    while not lte.isattached():
        debugprint('Attaching...')
        time.sleep(1)
    debugprint('LTE is attached')
    return True

def connect_LTE():
    if (lte == None):
        return
    if (not lte.isconnected()):
        lte.connect()
    while not lte.isconnected():
        debugprint('Connecting...')
        time.sleep(1)
    debugprint('LTE is connected!')
    socket.dnsserver(0,'8.8.8.8')
    socket.dnsserver(1,'4.4.4.4')

def disconnect_LTE():
    if (lte == None):
        return
    if (lte.isconnected()):
        debugprint("Disonnecting LTE... ")
        lte.disconnect()
    debugprint("LTE is disconnected")

# Clean disconnection of the LTE network is required for future
# successful connections without a complete power cycle between.
def end_LTE():
    global lte
    if lte == None:
        return
    if (lte.isconnected()):
        debugprint("Disonnecting LTE ... ")
        lte.disconnect()
        debugprint("LTE disconnected")
    debugprint("Detaching LTE ... ")
    lte.dettach()
    debugprint("LTE detached")
    debugprint("Shuttting down LTE...")
    lte.deinit()
    debugprint("LTE shutdown")
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
            debugprint('Network found!')
            wlan.connect(net.ssid, auth=(net.sec, config.WLAN_WPA), timeout=5000)
            attempts = 0
            while (not wlan.isconnected()) and (attempts < 10):
                debugprint('Connecting...')
                attempts = attempts + 1
                time.sleep(1)
            if wlan.isconnected():
                debugprint('WLAN connection succeeded')
                return True
            else:
                debugprint('WLAN connection failed')
                end_WLAN()
                return False
    debugprint('No known WLAN SSID found')
    wlan.deinit()
    wlan = None
    return False

def end_WLAN():
    global wlan
    if wlan == None:
        return
    debugprint("Disconnecting WLAN ... ")
    wlan.disconnect()
    debugprint("OK")
    debugprint("Shuttting down WLAN...")
    wlan.deinit()
    debugprint("OK")
    wlan = None
            
# Set the internal real-time clock.
def set_RTC():
    connect_LTE()
    rtc = machine.RTC()
    rtc.ntp_sync("pool.ntp.org",3600)
    while not rtc.synced():
        debugprint('Syncing RTC...')
        time.sleep_ms(750)
    debugprint('RTC Set from NTP to UTC: ' + str(rtc.now()))
    time.timezone(3600)
    debugprint('Adjusted from UTC to EST timezone: ' + str(time.localtime()))
    disconnect_LTE()

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
        print('Creating JWT...')
        current_jwt = jwt.new(project_id, private_key, 'RS256', TOKEN_VALIDITY)
    url = 'https://cloudiotdevice.googleapis.com/v1/projects/{}/locations/{}/registries/{}/devices/{}:publishEvent'.format(project_id, cloud_region, registry_id, device_id)
    data = { 'binary_data': b42_urlsafe_encode(payload) }
    try:
        connect_LTE()
        debugprint('sending...')
        debugprint(payload)
        response = requests.post(url, json=data, headers={"authorization": "Bearer {}".format(current_jwt.encodedValue()), "cache-control": "no-cache"})
        # conn = HTTPSConnection("172.217.20.106")
        # conn.request("POST", url, body=ujson.dumps(data) ,headers={"authorization": "Bearer {}".format(current_jwt.encodedValue())})
        # response = conn.getresponse()
        debugprint('sent!')
        print(response.text)
        #response.close()
    except:
        debugprint('!!! sending failed')
    finally:
        disconnect_LTE()

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
    if (not wlan == None):
        debugprint('Starting ftp server')
        server = Server(login=(config.ftpuser, config.ftppassword), timeout=60)
    last_measurement = -MEASURE_INTERVAL - 1
    while (True):
        led_Breathe()
        now = time.time()
        if (last_measurement + MEASURE_INTERVAL < now):
            coord = l76.position()
            pitch = acc.pitch() 
            roll = acc.roll()
            last_measurement = now
            # if not coord[0] == None:
            ensure_network()
            now = machine.RTC().now()
            isodatetime = "{}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}+00:00".format(now[0],now[1],now[2],now[3],now[4],now[5],now[6])
            volt = py.read_battery_voltage()
            send_http_payload(config.project_id, config.cloud_region, config.registry_id, config.device_id, config.private_key,
                                  '{{"timestamp":"{}","lat":{},"lon":{},"alt":{},"pitch":{},"roll":{},"volt":{}}}'.format(isodatetime, coord[0] if coord[0] != None else 'null', coord[1] if coord[1] != None else 'null', coord[2] if coord[2] != '' else 'null', pitch, roll, volt))
            # else:
            #     debugprint('No position to send')
        time.sleep(5)
        if (not wlan == None and (server == None or not server.isrunning())):
            debugprint('Restarting ftp server')
            server = Server(login=(config.ftpuser, config.ftppassword), timeout=60)

except Exception as e:
    debugprint('Exception occurred: '+ str(e))

finally:
    if (not server == None):
        server.deinit()
    end_network()
debugprint('Resetting...')
machine.reset()