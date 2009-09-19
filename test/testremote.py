from concurrence import unittest, Message, Tasklet, TimeoutError
from concurrence.remote import RemoteServer, RemoteTasklet, RemoteClient

import logging

#we need to define the msgs at the module level
#otherwise the remoting cannot use pickle to serialize them
class MSG_TEST(Message): pass
class MSG_SUM(Message): pass
class MSG_QUIT(Message): pass
class MSG_SLEEP(Message): pass

class RemoteTest(unittest.TestCase):

    def testRemote(self):
        
        client_results = []
        server_results = []

        def server():
            server_endpoint = None
            try:
                remote_server = RemoteServer()
                server_endpoint = remote_server.serve(('localhost', 9081))
                remote_server.register('testing123')
                for msg, args, kwargs in Tasklet.receive():
                    if msg.match(MSG_SUM):
                        server_results.append('s')
                        msg.reply(sum(args))
                    elif msg.match(MSG_TEST):
                        server_results.append('t')
                    elif msg.match(MSG_QUIT):
                        server_results.append('q')
                        break
                    elif msg.match(MSG_SLEEP):
                        server_results.append('sl')
                        Tasklet.sleep(args[0])
                        msg.reply(True)
            except Exception:
                logging.exception("")
                self.fail("")
            finally:
                if server_endpoint is not None: 
                    server_endpoint.close()
            
        def client():
            try:
                remote_client = RemoteClient()
                remote_client.connect(('localhost', 9081))
                remote_task = remote_client.lookup('testing123')
                self.assertFalse(remote_task is None)
                MSG_TEST.send(remote_task)(20, 30)
                MSG_TEST.send(remote_task)(30, 40)
                client_results.append(MSG_SUM.call(remote_task)(10, 20, 30))
                client_results.append(MSG_SUM.call(remote_task)(10, 20, 30))
                MSG_TEST.send(remote_task)(20, 30)
                MSG_TEST.send(remote_task)(30, 40)

                MSG_SLEEP.call(remote_task)(1)

                try:
                    MSG_SLEEP.call(remote_task, timeout = 1)(2)
                    self.fail("expected timeout")
                except TimeoutError:
                    pass #expected

                MSG_QUIT.send(remote_task)()
                Tasklet.sleep(2)
                remote_client.close()
            except Exception:
                logging.exception("")
                self.fail("")
        
        server_task = Tasklet.new(server)()
        client_task = Tasklet.new(client)()

        Tasklet.join_children()
        
        self.assertEquals([60,60], client_results)
        self.assertEquals(['t', 't', 's', 's', 't', 't', 'sl', 'sl', 'q'], server_results)




        
if __name__ == '__main__':
    unittest.main(timeout = 5)
