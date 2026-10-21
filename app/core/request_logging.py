"""Metadata-only HTTP diagnostics. Never log headers, bodies or raw URLs."""
import json
import logging
import re
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from time import perf_counter
from urllib.parse import parse_qs, urlsplit
from uuid import UUID, uuid4

from starlette.datastructures import Headers, MutableHeaders

LOG_PATH = Path(__file__).resolve().parents[2] / 'logs' / 'http.jsonl'
_KNOWN_PATHS = {'/', '/app.js', '/config.js', '/styles.css', '/cherry-blossom.svg',
                '/docs', '/openapi.json', '/user/login', '/user/signUp',
                '/auth/me', '/auth/logout', '/auth/providers',
                '/auth/kakao/login', '/auth/kakao/callback'}
_KNOWN_PATHS |= {'/api' + path for path in tuple(_KNOWN_PATHS) if path.startswith(('/auth/', '/user/'))}
_KNOWN_PATHS |= {'/api/courses', '/api/my/courses', '/api/demo/courses', '/api/demo/purchases',
                 '/api/payments/config', '/api/payments/orders', '/api/payments/confirm', '/api/payments/webhook'}
_AUTH_ERRORS = {'invalid_state', 'kakao_cancelled', 'kakao_unavailable', 'kakao_failed'}


def safe_path(path):
    path = str(path).split('?', 1)[0]
    if re.fullmatch(r'/api/courses/[1-9][0-9]*', path):
        return '/api/courses/{course_id}'
    return path if path in _KNOWN_PATHS else '[unmatched]'


class SafeAccessFilter(logging.Filter):
    def filter(self, record):
        # Uvicorn's five access arguments include a URL with OAuth query values.
        if isinstance(record.args, tuple) and len(record.args) == 5:
            client, method, path, version, status = record.args
            record.args = ('[client]', method if method in {'GET', 'POST', 'OPTIONS', 'HEAD'} else 'OTHER',
                           safe_path(path), version, status)
        return True


def configure_logging():
    logger = logging.getLogger('qwer.http')
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not logger.handlers:
        LOG_PATH.parent.mkdir(exist_ok=True)
        file_handler = RotatingFileHandler(LOG_PATH, maxBytes=1_000_000, backupCount=3,
                                          encoding='utf-8', delay=True)
        file_handler.setFormatter(logging.Formatter('%(message)s'))
        logger.addHandler(file_handler)
        logger.addHandler(logging.StreamHandler())
    access = logging.getLogger('uvicorn.access')
    if not any(isinstance(item, SafeAccessFilter) for item in access.filters):
        access.addFilter(SafeAccessFilter())
    return logger


class RequestLogMiddleware:
    def __init__(self, app):
        self.app = app
        self.logger = configure_logging()

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        supplied_id = Headers(scope=scope).get('x-request-id', '')
        try:
            request_id = str(UUID(supplied_id)) if len(supplied_id) == 36 else str(uuid4())
        except ValueError:
            request_id = str(uuid4())
        started, status, auth_result = perf_counter(), 500, None
        path = safe_path(scope['path'])
        method = scope['method'] if scope['method'] in {'GET', 'POST', 'OPTIONS', 'HEAD'} else 'OTHER'

        async def logged_send(message):
            nonlocal status, auth_result
            if message['type'] == 'http.response.start':
                status = message['status']
                headers = MutableHeaders(scope=message)
                headers['X-Request-ID'] = request_id
                if path.endswith('/auth/kakao/callback') and status == 303:
                    code = parse_qs(urlsplit(headers.get('location', '')).query).get('auth_error', [''])[0]
                    auth_result = code if code in _AUTH_ERRORS else 'success' if not code else 'failed'
            await send(message)

        try:
            await self.app(scope, receive, logged_send)
        finally:
            entry = {'time': datetime.now(timezone.utc).isoformat(),
                     'event': 'http_request', 'request_id': request_id, 'method': method,
                     'path': path, 'status': status,
                     'duration_ms': round((perf_counter() - started) * 1000, 2)}
            if auth_result:
                entry['auth_result'] = auth_result
            self.logger.info(json.dumps(entry, ensure_ascii=True))
