from concurrence import dispatch
from concurrence.wsgi import WSGIServer, WSGISimpleRouter

def show_form(environ, start_response):
    print environ
    start_response("200 OK", [('Content-type', 'text/html')])

    html = """
    <html>
    <body>
        <form method='post' action='/process'>
            <input name='a'></input>
            <input name='b'></input>
            <input type='submit' value='click!'></input>
        </form>
    </body>
    </html>
    """
    return [html]

def upload_form(environ, start_response):
    print environ
    start_response("200 OK", [])

    html = """
    <html>
    <body>
        <form method='post' action='/process' enctype='multipart/form-data'>
            <input type='file' name='thefile'></input>
            <input type='a' name='a' value='klaas'></input>
            <input type='b' name='b' value='piet'></input>
            <input type='submit' value='click!'></input>
        </form>
    </body>
    </html>
    """
    return [html]

def process_form(environ, start_response):
    print 'proc form'    
    print environ
    
    fp = environ['wsgi.input']
    while True:
        data = fp.read(1024)
        if not data: break
        print 'read', repr(data)

    start_response("200 OK", [])

    html = """
    <html>
    <body>
        <h1>blaat</h1>
    </body>
    </html>
    """
    return [html]

def main():
    application = WSGISimpleRouter()

    from wsgiref.validate import validator

    application.map('/form', validator(show_form))
    application.map('/upload', upload_form)
    application.map('/process', process_form)

    server = WSGIServer(application)
    server.serve(('localhost', 8080))

if __name__ == '__main__':
    import logging
    logging.basicConfig(level = logging.DEBUG)
    dispatch(main)
