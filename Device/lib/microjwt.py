import ujson
import string
from ubinascii import b2a_base64
from hashlib import sha256
import rsa

headerfields = { 'typ': 'JWT', 'alg': 'RS256' }

def b42_urlsafe_encode(payload):
    return string.translate(b2a_base64(payload)[:-1].decode('utf-8'),{ ord('+'):'-', ord('/'):'_' })

def encode(payload,private_key):
    content = b42_urlsafe_encode(ujson.dumps(headerfields).encode('utf-8'))
    content = content + '.' + b42_urlsafe_encode(ujson.dumps(payload).encode('utf-8'))
    signature = b42_urlsafe_encode(rsa.sign(content,private_key,'SHA-256'))
    return content + '.' + signature