from concurrence import Tasklet, Message, dispatch

class MSG_GREETING(Message): pass
class MSG_FAREWELL(Message): pass

def printer():
    for msg, args, kwargs in Tasklet.receive():
        if msg.match(MSG_GREETING):
            print 'Hello', args[0]
        elif msg.match(MSG_FAREWELL):
            print 'Goodbye', args[0]
        else:
            pass #unknown msg
    
def main():
    
    printer_task = Tasklet.new(printer)()
    
    MSG_GREETING.send(printer_task)('World')
    MSG_FAREWELL.send(printer_task)('World')
        
if __name__ == '__main__':
    dispatch(main)  
