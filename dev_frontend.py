"""Loopback-only static frontend. No API proxy or raw query access logging."""
import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

WEB = Path(__file__).resolve().parent / 'web'


class FrontendHandler(SimpleHTTPRequestHandler):
    def log_request(self, code='-', size='-'):
        # Only a source-file path from the public web tree, never URL parameters.
        path = urlsplit(self.path).path
        target = (WEB / path.lstrip('/')).resolve()
        safe = path if target.is_relative_to(WEB) and (target.is_file() or path == '/') else '[unmatched]'
        print(json.dumps({'event': 'frontend_request', 'method': self.command if self.command in {'GET', 'HEAD'} else 'OTHER',
                          'path': safe, 'status': code}), flush=True)

    def log_message(self, format, *args):
        pass


if __name__ == '__main__':
    server = ThreadingHTTPServer(('127.0.0.1', 8080), partial(FrontendHandler, directory=str(WEB)))
    print('Frontend: http://127.0.0.1:8080/ (static only, no API proxy)', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
