# Copyright (C) 2009, Hyves (Startphone Ltd.)
#
# This module is part of the Concurrence Framework and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php

from __future__ import with_statement

import httplib
import inspect
import logging

from routes import Mapper

from webob import Request, Response

from concurrence import TaskInstance
from concurrence.wsgi import WSGIServer, WSGISimpleResponse

class web(object):
    def __init__(self):
        self.paths = []
        self.filters = []
        
    @classmethod
    def _get_web(cls, f):
        if not hasattr(f, '__web__'):
            f.__web__ = web()
        return f.__web__
        
    @classmethod
    def route(cls, path):
        def x(f):
            w = cls._get_web(f)
            w.paths.append(path)
            return f
        return x
    
    @classmethod    
    def filter(cls, filter_):
        def x(f):
            w = cls._get_web(f)
            w.filters.insert(0, filter_)
            return f
        return x

class Filter(object):
    def __call__(self, next, *args, **kwargs):
        return next(*args, **kwargs)

class Controller(object):
    __filters__ = []

    def __init__(self):
        self.application = None
        
    def __call__(self, action, *args, **kwargs):
        return action(*args, **kwargs)

class Application(object):
    log = logging.getLogger('Application')

    _scoped_response = TaskInstance(True)
    _scoped_request = TaskInstance(True)
    
    default_content_type = 'text/html'
    default_charset = 'UTF-8'
    
    def __init__(self):
        self._controllers = {} #name->instance
        self._template_lookup = None
        self._mapper = Mapper()
        self._not_found = WSGISimpleResponse(httplib.NOT_FOUND) #default not found wsgi app
        self._filters = {} #(controller, action): [filter, filter, ...]
        self._filter_chain = {} #(controller, action): filter_chain

    @classmethod
    def get_instance_from_request(cls):
        return cls._scoped_request.environ['concurrence.application']

    def configure(self):
        """configures the application, must be called after all controllers have been added"""        
        self._mapper.create_regs(self._controllers.keys())
        
    def _add_route(self, path, controller_name, action_name):
        self._mapper.connect(path, controller = controller_name, action = action_name)
        
    def _add_filter(self, filter, controller_name, action_name):
        filter.request = self._scoped_request
        filter.response = self._scoped_response
        filter_key = (controller_name, action_name)
        if not filter_key in self._filters:
            self._filters[filter_key] = []
        self._filters[filter_key].append(filter)
        
    def add_controller(self, controller):
        """adds a controller_class to the application.
        the controllers methods will be scanned for @web attributes to 
        connect the methods of the controller to the correct urls"""
        assert isinstance(controller, Controller), "controller must be instance of Controller"
        controller.application = self
        controller_name = controller.__class__.__module__ + '.' + controller.__class__.__name__
        self.log.debug("adding controller %s", controller_name)
        self._controllers[controller_name] = controller
        #add the scoped request and response classes
        controller.request = self._scoped_request
        controller.response = self._scoped_response
        
        #check its members for special @web attribute. these members are 'actions'
        for action_name, member in inspect.getmembers(controller):
            if inspect.ismethod(member) and hasattr(member, '__web__'):
                #this will setup path routing, filters etc:
                w = member.__web__
                for path in w.paths:
                    self._add_route(path, controller_name, action_name) 
                #add controller filters
                for filter in controller.__filters__:
                    self._add_filter(filter, controller_name, action_name) 
                #add action filters
                for filter in w.filters:
                    self._add_filter(filter, controller_name, action_name)
        return controller
        
    def set_template_lookup(self, template_lookup):
        self._template_lookup = template_lookup

    def call_controller(self, controller_name, action_name, *args, **kwargs):
        """provided for override"""
        controller = self._controllers[controller_name]
        action = getattr(controller, action_name)
        return controller(action, *args, **kwargs)
        
    def __call__(self, environ, start_response):

        match =  self._mapper.match(environ['PATH_INFO'])
        if not match:
            return self._not_found(environ, start_response)

        controller_name = match['controller']
        action_name = match['action']        
        controller_action = (controller_name, action_name)

        del match['controller']
        del match['action']

        environ['concurrence.application'] = self

        #the actual request and response instances
        request = Request(environ)
        response = Response(content_type = self.default_content_type, charset = self.default_charset)

        #they will be added to the task local scope here:
        with self._scoped_request.set(request):
            with self._scoped_response.set(response):
                if not controller_action in self._filter_chain:
                    #we still need to setup call chain for this controller:action
                    #calling the controller is the last thing todo in the chain:
                    def last(next, *args, **kwargs):
                        return self.call_controller(controller_name, action_name, *args, **kwargs)
                    #set up call chain
                    filter_chain = []
                    for i, filter in enumerate(self._filters.get(controller_action, []) + [last, None]):
                        def create_next(_i, _filter):                        
                            def next(*args, **kwargs):
                                return _filter(filter_chain[_i + 1], *args, **kwargs)
                            return next
                        filter_chain.append(create_next(i, filter))
                    self._filter_chain[controller_action] = filter_chain
                #this will call the filter chain and produce the result
                result = self._filter_chain[controller_action][0](**match)
        
        if type(result) == str:
            response.body = result
        elif type(result) == unicode:
            response.unicode_body = result
        elif result is None:
            response.body = ''
        elif type(result) == type(response):
            response = result
        else:
            assert False, "result must be None, str, unicode or response object, found: %s" % type(result)

        return response(environ, start_response)

    def render(self, template_path, **kwargs):
        assert self._template_lookup is not None, "template lookup must be set to use render"
        template = self._template_lookup.get_template(template_path)
        return template.render(**kwargs)

    def serve(self, endpoint):
        server = WSGIServer(self)
        return server.serve(endpoint)
        
def render(template_path, **kwargs):
    application = Application.get_instance_from_request()
    return application.render(template_path, **kwargs)

def serve(endpoint = ('0.0.0.0', 8080), controllers = []):
    """a convenience method to quickly start an application for testing"""
    application = Application()
    for controller in controllers:
        application.add_controller(controller)
    application.configure()
    application.serve(endpoint)
    
    from concurrence import dispatch
    dispatch()
