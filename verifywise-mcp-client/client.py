"""Small synchronous MCP Streamable HTTP client, Python 3.10+, no dependencies."""
import argparse
import json
import os
import sys
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.parse import urlsplit


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class MCPError(RuntimeError):
    def __init__(self, error):
        self.error = error
        super().__init__(json.dumps(error))


class Client:
    def __init__(self, url, key=None, timeout=30):
        parts = urlsplit(url)
        if parts.username or parts.password or parts.fragment:
            raise ValueError('URL must not contain credentials or fragments')
        if parts.scheme != 'https' and not (
            parts.scheme == 'http' and parts.hostname in ('localhost', '127.0.0.1', '::1')
        ):
            raise ValueError('Use HTTPS; HTTP is allowed only for localhost')
        self.url, self.key, self.timeout = url, key, timeout
        self.session = None
        self.counter = 0
        self.opener = build_opener(NoRedirect())

    def headers(self):
        headers = {'Content-Type': 'application/json',
                   'Accept': 'application/json, text/event-stream'}
        if self.key:
            headers['Authorization'] = 'Bearer ' + self.key
        if self.session:
            headers['Mcp-Session-Id'] = self.session
        return headers

    def send(self, method, params=None, notification=False):
        message = {'jsonrpc': '2.0', 'method': method}
        if params is not None:
            message['params'] = params
        if not notification:
            self.counter += 1
            message['id'] = self.counter
        request = Request(self.url, data=json.dumps(message).encode(),
                          headers=self.headers(), method='POST')
        with self.opener.open(request, timeout=self.timeout) as response:
            if response.headers.get('Mcp-Session-Id'):
                self.session = response.headers['Mcp-Session-Id']
            if notification:
                if response.status != 202:
                    raise RuntimeError('Expected HTTP 202 for notification')
                return None
            content_type = response.headers.get('Content-Type', '').split(';')[0]
            if content_type == 'application/json':
                payload = json.load(response)
            elif content_type == 'text/event-stream':
                payload = self.read_sse(response, message['id'])
            else:
                raise RuntimeError('Unexpected response content type')
        if payload.get('jsonrpc') != '2.0' or payload.get('id') != message['id']:
            raise RuntimeError('Invalid or mismatched JSON-RPC response')
        if 'error' in payload:
            raise MCPError(payload['error'])
        if 'result' not in payload:
            raise RuntimeError('Missing JSON-RPC result')
        return payload['result']

    @staticmethod
    def read_sse(response, request_id):
        data = []
        for raw in response:
            line = raw.decode('utf-8').rstrip('\r\n')
            if line.startswith('data:'):
                data.append(line[5:].lstrip(' '))
            elif not line and data:
                payload = json.loads('\n'.join(data))
                data = []
                messages = payload if isinstance(payload, list) else [payload]
                for message in messages:
                    if message.get('id') == request_id and ('result' in message or 'error' in message):
                        return message
                    if 'method' in message and 'id' in message:
                        raise RuntimeError('Server-initiated requests are unsupported by this example')
        raise RuntimeError('SSE stream ended without a matching response')

    def initialize(self):
        result = self.send('initialize', {
            'protocolVersion': '2025-03-26', 'capabilities': {},
            'clientInfo': {'name': 'verifywise-example-client', 'version': '1.0.0'}})
        if result.get('protocolVersion') != '2025-03-26':
            raise RuntimeError('Server negotiated an unsupported protocol version')
        self.send('notifications/initialized', notification=True)
        return result

    def list_tools(self):
        tools, cursor, seen = [], None, set()
        while True:
            result = self.send('tools/list', {'cursor': cursor} if cursor else {})
            tools.extend(result.get('tools', []))
            cursor = result.get('nextCursor')
            if not cursor:
                return tools
            if cursor in seen:
                raise RuntimeError('Server repeated a pagination cursor')
            seen.add(cursor)

    def close(self):
        if self.session:
            try:
                with self.opener.open(Request(self.url, headers=self.headers(), method='DELETE'),
                                      timeout=self.timeout):
                    pass
            except Exception:
                pass  # Session cleanup must not hide the original operation result.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default=os.getenv('VERIFYWISE_MCP_URL'))
    parser.add_argument('--demo', action='store_true', help='Use local sample server without a key')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('list')
    call = sub.add_parser('call')
    call.add_argument('tool')
    call.add_argument('--args', default='{}', help='JSON object matching the discovered inputSchema')
    args = parser.parse_args()
    key = None if args.demo else os.getenv('VERIFYWISE_AGENT_KEY')
    url = args.url or ('http://127.0.0.1:8000/mcp' if args.demo else None)
    if not url or (not args.demo and not key):
        parser.error('Set VERIFYWISE_MCP_URL and VERIFYWISE_AGENT_KEY, or use --demo')
    client = None
    try:
        arguments = json.loads(args.args) if args.command == 'call' else {}
        if not isinstance(arguments, dict):
            raise ValueError('--args must be a JSON object')
        client = Client(url, key)
        client.initialize()
        result = client.list_tools() if args.command == 'list' else client.send(
            'tools/call', {'name': args.tool, 'arguments': arguments})
        print(json.dumps(result, indent=2))
        return 2 if isinstance(result, dict) and result.get('isError') else 0
    except MCPError as error:
        print(json.dumps({'mcp_error': error.error}, indent=2), file=sys.stderr)
        return 2  # Includes approval-required errors; never automatically retry calls.
    except Exception as error:
        message = str(error)
        if key:
            message = message.replace(key, '[REDACTED]')
        print('Connection/call failed: ' + message, file=sys.stderr)
        return 1
    finally:
        if client:
            client.close()


if __name__ == '__main__':
    sys.exit(main())
