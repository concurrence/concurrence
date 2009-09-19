"""a small IOC container"""
#TODO services (parallel for same runlevel)

import inspect

class Context(object): 
    @classmethod
    def set_attribute(cls, obj, key, val):
        """recurisivly adds fields to obj according to key
        the final field will have val"""
        idx_dot = key.find('.')
        if idx_dot == -1: #single key
            setattr(obj, key, val)
        else: #dotted key
            keyhead, keyrest = key[:idx_dot], key[idx_dot+1:]
            if hasattr(obj, keyhead):
                p = getattr(obj, keyhead)            
                cls.set_attribute(p, keyrest, val)
            else:
                p = Context()
                cls.set_attribute(p, keyrest, val)
                setattr(obj, key[:idx_dot], p)

context = Context()

class Container(object):
    def __init__(self):
        self.resources = {}

    def add(self, key, resource):
        self.resources[key] = resource
    
    def configure(self, parameters, prefix = 'config'):  
        """adds all key, value pairs in dict config as resources to the container, prefixed by prefix"""
        if not parameters:
            return
        for key, val in parameters.items():
            self.resources[prefix + '.' + key] = val

    def finalize(self):
        """configures all resources that need configuring"""
        Context.set_attribute(context, 'container', self)
        for k in sorted(self.resources.keys()):        
            #print k, self.resources[k]
            Context.set_attribute(context, k, self.resources[k])
            
    def _find_members(self, filter):
        import re
        for name, resource in self.resources.items():
            for member_name, member in inspect.getmembers(resource, inspect.ismethod):
                fa = re.findall(filter, member_name)
                if fa:
                    yield name, resource, fa, getattr(resource, member_name)
        
    def statistics(self):
        """return all the statistics from all the resources that define them"""
        stats = {}
        for name, resource, fa, member in self._find_members('__statistics__'):
            stats[name] = member()
        return stats
    
    def start(self):
        """starts up services, services are started up by calling their
        __startXX__ methods, start methods in the same runlevel are started
        concurrently (TODO)"""
        for _, resource, fa, member in self._find_members(r'__start(\d\d)__'):
            try:
                level = int(fa[0])
            except:
                level = -1
                
            if level != -1:
                #start the service
                member()
                
container = Container()

