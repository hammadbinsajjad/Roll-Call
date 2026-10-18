#!/usr/bin/env python3
"""Roll-Call mock API — stdlib only, port 8787, CORS on. Delete with temp-mock/."""
import json
import os
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')

# In-memory store for chats created during this run.
CHATS = {}
NEXT_CHAT = [1]


def load(name, default):
    try:
        with open(os.path.join(DIR, name)) as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def save(name, obj):
    with open(os.path.join(DIR, name), 'w') as f:
        json.dump(obj, f, indent=2)


CONFIG = load('config.json', {'repos': [], 'team_members': []})
AUTH = load('auth.json', {'users': []})
REPLY = load('chat-reply.json', {'reply': 'Mock reply.'})


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()
        self.wfile.write(body)

    def _authed(self):
        token = self.headers.get('Authorization', '')
        return token.startswith('Bearer ') and len(token) > 10

    def _body(self):
        n = int(self.headers.get('Content-Length') or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n))
        except json.JSONDecodeError:
            return {}

    def do_OPTIONS(self):
        self._send(204, None)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == '/config':
            return self._send(200, CONFIG)

        if u.path == '/member-summary':
            date = parse_qs(u.query).get('date', [''])[0]
            return self._send(200, load(f'member-summary-{date}.json', []))

        if u.path == '/chats':
            if not self._authed():
                return self._send(401, {'error': 'unauthorized'})
            return self._send(200, load('chats.json', []))

        if u.path.startswith('/chat/'):
            if not self._authed():
                return self._send(401, {'error': 'unauthorized'})
            chat_id = u.path.rsplit('/', 1)[1]
            chat = CHATS.get(chat_id) or load(f'chat-{chat_id}.json', None)
            if chat is None:
                return self._send(404, {'error': 'chat not found'})
            return self._send(200, chat)

        self._send(404, {'error': 'not found'})

    def do_POST(self):
        u = urlparse(self.path)
        body = self._body()

        if u.path == '/auth/register':
            for user in AUTH['users']:
                if user['username'] == body.get('username'):
                    return self._send(409, {'error': 'username already taken'})
            AUTH['users'].append({'username': body.get('username'), 'password': body.get('password')})
            save('auth.json', AUTH)
            return self._send(201, {'token': 'mock-' + uuid.uuid4().hex, 'username': body.get('username')})

        if u.path == '/auth/login':
            for user in AUTH['users']:
                if user['username'] == body.get('username') and user['password'] == body.get('password'):
                    return self._send(200, {'token': 'mock-' + uuid.uuid4().hex, 'username': user['username']})
            return self._send(401, {'error': 'invalid username or password'})

        if not self._authed():
            return self._send(401, {'error': 'unauthorized'})

        if u.path == '/config/repos':
            name = (body.get('name') or '').strip()
            if name not in CONFIG['repos']:
                CONFIG['repos'].append(name)
                save('config.json', CONFIG)
            return self._send(200, {'ok': True, 'repos': CONFIG['repos']})

        if u.path == '/config/members':
            member = {k: body.get(k, '') for k in ('github_username', 'linear_email', 'member_name')}
            CONFIG['team_members'] = [m for m in CONFIG['team_members']
                                      if m['github_username'] != member['github_username']]
            CONFIG['team_members'].append(member)
            save('config.json', CONFIG)
            return self._send(200, {'ok': True, 'team_members': CONFIG['team_members']})

        if u.path == '/chat':
            chat_id = str(NEXT_CHAT[0])
            NEXT_CHAT[0] += 1
            now = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            CHATS[chat_id] = {'chat_id': chat_id, 'messages': [
                {'role': 'user', 'content': body.get('message', ''), 'created_at': now},
                {'role': 'assistant', 'content': REPLY['reply'], 'created_at': now},
            ]}
            return self._send(200, {'chat_id': chat_id, 'reply': REPLY['reply']})

        if u.path.startswith('/chat/'):
            chat_id = u.path.rsplit('/', 1)[1]
            now = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            chat = CHATS.setdefault(chat_id, {'chat_id': chat_id, 'messages': []})
            chat['messages'].append({'role': 'user', 'content': body.get('message', ''), 'created_at': now})
            chat['messages'].append({'role': 'assistant', 'content': REPLY['reply'], 'created_at': now})
            return self._send(200, {'reply': REPLY['reply']})

        self._send(404, {'error': 'not found'})

    def do_DELETE(self):
        u = urlparse(self.path)
        if not self._authed():
            return self._send(401, {'error': 'unauthorized'})
        body = self._body()

        if u.path == '/config/repos':
            CONFIG['repos'] = [r for r in CONFIG['repos'] if r != body.get('name')]
            save('config.json', CONFIG)
            return self._send(200, {'ok': True, 'repos': CONFIG['repos']})

        if u.path == '/config/members':
            CONFIG['team_members'] = [m for m in CONFIG['team_members']
                                      if m['github_username'] != body.get('github_username')]
            save('config.json', CONFIG)
            return self._send(200, {'ok': True, 'team_members': CONFIG['team_members']})

        self._send(404, {'error': 'not found'})

    def log_message(self, fmt, *args):
        print('%s %s' % (self.command, self.path))


if __name__ == '__main__':
    print('Roll-Call mock API on http://localhost:8787')
    ThreadingHTTPServer(('127.0.0.1', 8787), Handler).serve_forever()
