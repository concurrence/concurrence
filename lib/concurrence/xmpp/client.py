# Copyright (C) 2009, Hyves (Startphone Ltd.)
#
# This module is part of the Concurrence Framework and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php

#TODO heartbeat
from __future__ import with_statement

from xml.etree.cElementTree import dump, tostring

from concurrence.timer import Timeout
from concurrence.io import Connector 
from concurrence.xmpp import sasl
from concurrence.xmpp.stream import XMPPStream

import logging

class XMPPError(Exception):
    pass
        
class XMPPClient(object):
    log = logging.getLogger('XMPPClient')
        
    def __init__(self):
        self.socket = None
        self.elements = None
        
    def close(self):
        if not self.socket.is_closed():
            self.stream.write_end()
            self.socket.close()
        
    def _handshake(self, username, password, realm):
        #perform SASL handshake
        element_features = self.elements.next()
        if element_features.tag != '{http://etherx.jabber.org/streams}features':
            self.log.error(tostring(element_features))
            assert False, 'unexpected tag: %s expected features' % element_features.tag

        self.stream.write_auth()
            
        element_challenge = self.elements.next()
        if element_challenge.tag != '{urn:ietf:params:xml:ns:xmpp-sasl}challenge':
            assert False, 'unexpected element: %s' % element_challenge.tag 

        response = sasl.response(element_challenge.text, username, password, realm, 'xmpp/' + realm)

        self.stream.write_sasl_response(response)
        
        element = self.elements.next()
        
        if element.tag == '{urn:ietf:params:xml:ns:xmpp-sasl}failure':
            assert False, "login failure"
        elif element.tag == '{urn:ietf:params:xml:ns:xmpp-sasl}challenge':
            pass #OK
        else:
            assert False, "unexpected element: %s" % element.tag
        
        self.stream.write_sasl_response()

        element = self.elements.next()
        if element.tag != '{urn:ietf:params:xml:ns:xmpp-sasl}success':
            assert False, "error %s" % element.tag 
        
    def connect(self, endpoint, username, password, realm, resource):
        
        self.socket = Connector.connect(endpoint)

        #start xml stream
        self.stream = XMPPStream(self.socket)

        self.stream.write_start(1)
        self.elements = self.stream.elements()

        #perform auth handshake
        self._handshake(username, password, realm)

        #after SASL-auth we are supposed to restart the xml stream:
        self.stream.reset()
        self.stream.write_start(2, include_xml_pi = False)
        self.elements = self.stream.elements()

        #read stream features
        element = self.elements.next()
        if element.tag != '{http://etherx.jabber.org/streams}features':
            assert False, "expected stream features, got: %s" % element.tag
            
        #bind resource
        self.stream.write_bind_request('bind', resource)
            
        element = self.elements.next()
        #TODO assert more on bind result
        if element.tag != '{jabber:client}iq':
            assert False, "expected iq, got: %s" % element.tag

        #send session request
        self.stream.write_session_request(realm, 3)
            
        element = self.elements.next()
        #TODO check result
        if element.tag != '{jabber:client}iq':
            assert False, 'expected iq result got: %s' % element.tag

        #now we are ready and fully logged in
        self.jid = '%s@%s/%s' % (username, realm, 'henktest')
    
    def send_presence(self, priority):
        self.stream.write_presence(priority)

    def send_message(self, to_jid, msg):
        self.stream.write_message(to_jid, msg)
            
            
            
            
