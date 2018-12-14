import ujson
import string
from ubinascii import b2a_base64
from hashlib import sha256
import rsa
import time

def create_jwt(project_id, private_key, algorithm):
    token = {
            # The time that the token was issued at
            'iat': time.time(),
            # The time the token expires.
            'exp': time.time() + TOKEN_VALIDITY,
            # The audience field should always be set to the GCP project id.
            'aud': project_id
    }


class MicroJWT:

    def __init__(self, project_id, private_key, algorithm, validity):
        self.token = {
            # The time that the token was issued at
            'iat': time.time(),
            # The time the token expires.
            'exp': time.time() + validity,
            # The audience field should always be set to the GCP project id.
            'aud': project_id
        }
        print('Creating JWT with token {}'.format(self.token))
        self.encoded = self.encode(self.token, private_key, algorithm)

    def isValid(self):
        return time.time() < self.token['exp']

    def encodedValue(self):
        return self.encoded
    
    def b42_urlsafe_encode(self, payload):
        return string.translate(b2a_base64(payload)[:-1].decode('utf-8'),{ ord('+'):'-', ord('/'):'_' })

    def encode(self, payload, private_key, algorithm):
        headerfields = { 'typ': 'JWT', 'alg': algorithm }
        content = self.b42_urlsafe_encode(ujson.dumps(headerfields).encode('utf-8'))
        content = content + '.' + self.b42_urlsafe_encode(ujson.dumps(payload).encode('utf-8'))
        # TODO: algorithm selection (now assumes RS256)
        signature = self.b42_urlsafe_encode(rsa.sign(content,private_key,'SHA-256'))
        return content + '.' + signature

def new(project_id, private_key, algorithm, validity):
    return MicroJWT(project_id, private_key, algorithm, validity)