from concurrence import dispatch
from concurrence.http import HTTPConnection

def main():
    
    cnn = HTTPConnection()
    cnn.connect(('www.google.com', 80))

    request = cnn.get('/')

    #you can send multiple http requests on the same connection:
    cnn.send(request) #request 1
    cnn.send(request) #request 2

    #and receive the corresponding responses    
    response1 = cnn.receive()
    response2 = cnn.receive()

    print response1.status
    print response1.headers
    print response1.body

    print response2.status
    print response2.headers
    print response2.body

    cnn.close()

if __name__ == '__main__':
    dispatch(main)
