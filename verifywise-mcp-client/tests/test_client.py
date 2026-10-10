import io
import threading
import unittest
from http.server import ThreadingHTTPServer
from client import Client, MCPError
from demo_server import Handler


class ClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}/mcp'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def test_end_to_end(self):
        client = Client(self.url)
        client.initialize()
        self.assertEqual(client.list_tools()[0]['name'], 'demo_list_projects')
        result = client.send('tools/call', {'name': 'demo_list_projects', 'arguments': {}})
        self.assertIn('demo-1', result['content'][0]['text'])
        with self.assertRaises(MCPError):
            client.send('tools/call', {'name': 'missing', 'arguments': {}})

    def test_sse_notification_and_matching_response(self):
        stream = io.BytesIO(b': heartbeat\n\ndata: {"jsonrpc":"2.0","method":"notifications/message"}\n\n'
                            b'data: {"jsonrpc":"2.0","id":2,"result":{"ok":true}}\n\n')
        self.assertEqual(Client.read_sse(stream, 2)['result'], {'ok': True})

    def test_unsafe_url_rejected(self):
        for url in ['http://example.com/mcp', 'https://user:secret@example.com/mcp']:
            with self.assertRaises(ValueError):
                Client(url)

    def test_pagination(self):
        client = Client(self.url)
        results = iter([{'tools': [{'name': 'one'}], 'nextCursor': 'page2'},
                        {'tools': [{'name': 'two'}]}])
        client.send = lambda *args: next(results)
        self.assertEqual([t['name'] for t in client.list_tools()], ['one', 'two'])


if __name__ == '__main__':
    unittest.main()
