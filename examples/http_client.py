from concurrence import dispatch
from concurrence.http import HTTPConnection

def main():
    
    cnn = HTTPConnection()
    cnn.connect(('www.google.com', 80))

    request = cnn.get('/')
    response = cnn.perform(request)
    
    print response.status
    print response.headers
    print response.body

    cnn.close()

if __name__ == '__main__':
    dispatch(main)
