from concurrence import dispatch, Tasklet, Message
from concurrence.io import BufferedStream, Socket, Server

class MSG_WRITE_LINE(Message): pass
class MSG_QUIT(Message): pass
class MSG_LINE_READ(Message): pass

connected_clients = set() #set of currently connected clients (tasks)
        
def handle(client_socket):
    """handles a single client connected to the chat server"""
    stream = BufferedStream(client_socket)

    client_task = Tasklet.current() #this is the current task as started by server
    connected_clients.add(client_task)
    
    def writer():
        for msg, args, kwargs in Tasklet.receive():
            if msg.match(MSG_WRITE_LINE):
                stream.writer.write_bytes(args[0] + '\n')
                stream.writer.flush()
            
    def reader():
        for line in stream.reader.read_lines():
            line = line.strip()
            if line == 'quit': 
                MSG_QUIT.send(client_task)()
            else:
                MSG_LINE_READ.send(client_task)(line)
    
    reader_task = Tasklet.new(reader)()
    writer_task = Tasklet.new(writer)()

    MSG_WRITE_LINE.send(writer_task)("type 'quit' to exit..")
    
    for msg, args, kwargs in Tasklet.receive():
        if msg.match(MSG_QUIT):
            break
        elif msg.match(MSG_LINE_READ):
            #a line was recv from our client, multicast it to the other clients
            for task in connected_clients:
                if task != client_task: #don't echo the line back to myself
                    MSG_WRITE_LINE.send(task)(args[0])
        elif msg.match(MSG_WRITE_LINE):
            MSG_WRITE_LINE.send(writer_task)(args[0])
        
    connected_clients.remove(client_task)
    reader_task.kill()
    writer_task.kill()
    client_socket.close()
           
def server():
    """accepts connections on a socket, and dispatches
    new tasks for handling the incoming requests"""
    print 'listening for connections on port 9010'
    Server.serve(('localhost', 9010), handle)

if __name__ == '__main__':
    dispatch(server)
