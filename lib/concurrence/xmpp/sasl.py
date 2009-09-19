# Copyright (C) 2009, Hyves (Startphone Ltd.)
#
# This module is part of the Concurrence Framework and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php

import binascii
import base64
import md5
import random

def H(s):
    return md5.new(s).digest()

def KD(k, s):
    return H(k + ":" + s)
    
def HEX(n):
    return binascii.hexlify(n)

def UNHEX(h):
    return binascii.unhexlify(h)

def response(challenge, user, password, realm, digest_uri):
    #parse challenge
    c = {}
    for x in base64.decodestring(challenge).split(","):
        i = x.find('=')
        if i == -1: continue        
        key = x[:i].strip()
        value = x[i+1:].strip()
        if value[0] == '"' and value[-1] == '"': value = value[1:-1]
        key = key.replace('-', '_')
        c[key] = value
    
    #calculate response
    nonce = c['nonce']    
    cnonce = hex(random.getrandbits(128))[2:-1].lower()
    nc = "00000001"
    qop = "auth"
    digest = HEX(H("%s:%s:%s" % (user, realm, password)))

    A2 = "AUTHENTICATE:" + digest_uri
    A1 = UNHEX( digest ) + ":" + nonce + ":" + cnonce
    response = HEX(KD(HEX(H(A1)), nonce + ":" + nc + ":" + cnonce + ":" + qop + ":" + HEX(H(A2))))

    response = """username="%s",realm="%s",nonce="%s",cnonce="%s",nc=00000001,qop=auth,digest-uri="%s",response=%s,charset=utf-8""" % \
                (user, realm, nonce, cnonce, digest_uri, response)

    return "".join(base64.encodestring(response).split("\n"))