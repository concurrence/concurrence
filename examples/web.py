from concurrence import dispatch
from concurrence.web import Application, Controller, Filter, web

class PageFilter(Filter):
    """A filter that surrounds the upstream response with a complete html page"""
    def __call__(self, next, *args, **kwargs):
        #A Filter is a callable object and is part of a chain of filters configured for
        #a certain Action. A filter uses the `next` argument to call the next filter in the chain.
        return """
        <html>
            <head>
                <title>Example Page</title>
            </head>
            <body style='background-color: #a0f0f0'>
            %s
            </body>
        </html>""" % next(*args, **kwargs)
    
class WrapperFilter(Filter):
    """A filter that surrounds the upstream response with a tag"""
    def __init__(self, tag):
        self.tag = tag
        
    def __call__(self, next, *args, **kwargs):
        return "<%s>%s</%s>" % (self.tag,  next(*args, **kwargs), self.tag)
    
class ExampleController(Controller):
    """A Controller contains multiple Actions. A controller
    method becomes an Action by adding a `web.route` decorator that links the method to an url."""
    
    #controller level filters are applied to all actions in the controller
    __filters__ = [PageFilter()]  
    
    #a action may be linked to multiple urls
    @web.route('/greeting')
    @web.route('/welcome')
    def hello(self):
        return "Hello World" 

    @web.route('/farewell')
    def goodbye(self):
        return "Goodbye" 
	
    @web.route('/sum') 
    def sum(self):
	
        msg = self.request.params.getone('msg')
        a = int(self.request.params.getone('a'))
        b = int(self.request.params.getone('b'))

        return '%s %d' % (msg, a + b)

    #in addition to the controller level filters, an action may also supply its own filters
    @web.route('/wrapper')
    @web.filter(WrapperFilter('h1'))
    @web.filter(WrapperFilter('strong'))    
    def wrapper(self):
        return "Testing 132"
    
def main():
    #create a web application
    application = Application()
    application.add_controller(ExampleController())
    application.configure()
    application.serve(('localhost', 8080))

if __name__ == '__main__':
    dispatch(main)
