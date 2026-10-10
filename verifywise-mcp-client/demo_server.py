"""Local sample-data MCP backend. Not a VerifyWise API adapter or production server."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TOOLS = [{'name': 'demo_list_projects', 'description': 'Return fictional sample projects.',
          'inputSchema': {'type': 'object', 'properties': {}, 'additionalProperties': False}}]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def reply(self, status, payload=None):
        data = json.dumps(payload).encode() if payload is not None else b''
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self.reply(405)

    def do_POST(self):
        if self.path != '/mcp':
            return self.reply(404)
        if self.headers.get('Origin'):
            return self.reply(403)
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 65536:
                return self.reply(413)
            message = json.loads(self.rfile.read(size))
            method = message['method']
        except (ValueError, KeyError, TypeError):
            return self.reply(400)
        if 'id' not in message:
            return self.reply(202)
        payload = {'jsonrpc': '2.0', 'id': message['id']}
        if method == 'initialize':
            payload['result'] = {'protocolVersion': '2025-03-26', 'capabilities': {'tools': {}},
                                 'serverInfo': {'name': 'sample-data-backend', 'version': '1.0.0'}}
        elif method == 'tools/list':
            payload['result'] = {'tools': TOOLS}
        elif method == 'tools/call':
            params = message.get('params', {})
            if params.get('name') != 'demo_list_projects':
                payload['error'] = {'code': -32602, 'message': 'Unknown tool'}
            elif params.get('arguments', {}) != {}:
                payload['error'] = {'code': -32602, 'message': 'Tool takes no arguments'}
            else:
                data = {'sample_data': True, 'projects': [{'id': 'demo-1', 'name': 'Example AI project'}]}
                payload['result'] = {'content': [{'type': 'text', 'text': json.dumps(data)}], 'isError': False}
        else:
            payload['error'] = {'code': -32601, 'message': 'Method not found'}
        self.reply(200, payload)


if __name__ == '__main__':
    print('Sample MCP backend: http://127.0.0.1:8000/mcp', flush=True)
    ThreadingHTTPServer(('127.0.0.1', 8000), Handler).serve_forever()
