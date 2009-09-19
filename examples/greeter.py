from concurrence import dispatch, Tasklet
from concurrence.io import BufferedStream, Socket

def handler(client_socket):
    """writes the familiar greeting to client"""
    stream = BufferedStream(client_socket)
    writer = stream.writer    
    writer.write_bytes("HTTP/1.0 200 OK\r\n")
    writer.write_bytes("Content-Length: 12\r\n")    
    writer.write_bytes("\r\n")
    writer.write_bytes("Hello World!")
    writer.flush()
    stream.close()
       
def server():
    """accepts connections on a socket, and dispatches
    new tasks for handling the incoming requests"""
    server_socket = Socket.new()
    server_socket.bind(('localhost', 8080))
    server_socket.listen()

    while True:
        client_socket = server_socket.accept()
        Tasklet.new(handler)(client_socket)

if __name__ == '__main__':
    dispatch(server)
