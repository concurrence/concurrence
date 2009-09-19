from concurrence import dispatch

def hello():
    print "Hello World!"
    
if __name__ == '__main__':
    dispatch(hello)  
