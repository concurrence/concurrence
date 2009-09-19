# Copyright (C) 2009, Hyves (Startphone Ltd.)
#
# This module is part of the Concurrence Framework and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php

from xml.etree.cElementTree import iterparse, dump

from concurrence.io import Buffer
from concurrence.io.buffered import BufferedStream

class XMPPStream:
    MAJOR_VERSION = 1
    MINOR_VERSION = 0
    DEFAULT_LANGUAGE = "en"
    NS_XMPP_STREAM_STREAM = "http://etherx.jabber.org/streams"
    
    NS_JABBER_CLIENT = "jabber:client"
    
    def __init__(self, stream, stream_uri = NS_XMPP_STREAM_STREAM, default_ns = NS_JABBER_CLIENT):
        self.stream = BufferedStream(stream)
        self.stream_uri = stream_uri
        self.default_ns = default_ns
        self.reset()
        
    def reset(self):
        self.parser = None
        self.root = None
        
    def write_bytes(self, s):
        self.stream.writer.clear()
        self.stream.writer.write_bytes(s)
        self.stream.writer.flush()
        
    def write_start(self, _id, lang = DEFAULT_LANGUAGE, major_version = MAJOR_VERSION, minor_version = MINOR_VERSION, _to = "", _from = "", include_xml_pi = True):
        if include_xml_pi:         
            start = """<?xml version='1.0' encoding='utf-8'?>"""
        else:
            start = ""

        start += """<stream:stream xmlns:stream="%s" xmlns="%s" id="%s" xml:lang="%s" version="%d.%d" """ 
        start = start % (self.stream_uri, self.default_ns, _id, lang, major_version, minor_version)
    
        if _from: start += ' from="%s"' % _from
        if _to: start += ' to="%s"' % _to
    
        start += ">"
 
        self.write_bytes(start)
        
    def write_end(self):
        self.write_bytes("</stream:stream>")
                
    def write_auth(self, mechanism = 'DIGEST-MD5'):
        self.write_bytes("""<auth xmlns='urn:ietf:params:xml:ns:xmpp-sasl' mechanism='%s'/>""" % mechanism)
    
    def write_sasl_response(self, response = ''):
        if response:        
            self.write_bytes("""<response xmlns='urn:ietf:params:xml:ns:xmpp-sasl'>%s</response>""" % response)
        else:
            self.write_bytes("""<response xmlns='urn:ietf:params:xml:ns:xmpp-sasl'/>""")
    
    def write_bind_request(self, _id, resource):
        self.write_bytes("""<iq id='%s' type='set'>
          <bind xmlns='urn:ietf:params:xml:ns:xmpp-bind'>
            <resource>%s</resource>
          </bind>
        </iq>""" % (_id, resource))
        
    def write_session_request(self, domain, _id):
        self.write_bytes("""
        <iq id='%s' type='set' to='%s'>
          <session xmlns='urn:ietf:params:xml:ns:xmpp-session'/>
        </iq>""" % (_id, domain))
        
    def write_presence(self, priority):
        self.write_bytes("""<presence><priority>%d</priority></presence>""" % priority)

    def write_message(self, to_jid, msg):
        self.write_bytes(str("<message to='%s' type='chat'><body>%s</body></message>" % (to_jid, msg)))
    
    def elements(self):
        
        if not self.parser:
            reader = self.stream.reader
            class f(object):
                def read(self, n):
                    if reader.buffer.remaining == 0:
                        #read more data into buffer
                        reader._read_more()
                    return reader.buffer.read_bytes(min(n, reader.buffer.remaining))

            self.parser = iter(iterparse(f(), events=("start", "end")))
            event, self.root = self.parser.next()
            level = 0
        
        for event, element in self.parser:
            if event == 'start':
                level += 1
            elif event == 'end':
                level -= 1
                if level == 0:
                    yield element
                #TODO clear root
            else:
                assert False, "unexpected event"
                
