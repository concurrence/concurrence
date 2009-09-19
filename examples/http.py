from concurrence import dispatch
from concurrence.http import WSGIServer

def hello_world(environ, start_response):
    start_response("200 OK", [])
    return ["<html>Hello, world!</html>"]

def main():
    server = WSGIServer(hello_world)
    server.serve(('localhost', 8080))

if __name__ == '__main__':
    dispatch(main)
