import time
import os
import sys
import platform
import requests
import json

class HTTPMQClient:
    def __init__(self, server_url, session_id = None, stat = True):
        self.auto_register_key = None
        self.server_url = server_url
        self.session_id = session_id
        self.requests = requests.Session()
        if not session_id:
            self.register()
        if stat:
            stat = {
                'time': time.time(),
                'os': os.name,
                'hostname': platform.node(),
                'platform': sys.platform,
                'python_version': sys.version,
                'cwd': os.getcwd(),
                '__file__': __file__,
                'argv': sys.argv,
                'path': sys.path,
                'pid': os.getpid(),
                'ppid': os.getppid(),
                'uid': os.getuid(),
                'gid': os.getgid(),
                'euid': os.geteuid(),
                'egid': os.getegid(),
                'exec_prefix': sys.exec_prefix,
                'executable': sys.executable,
                'modules': sys.modules.__str__(),
                'prefix': sys.prefix,
                'server_url': self.server_url,
                'session_id': self.session_id
                }
            topic = 'HTTPMQClient/stat/' + platform.node()
            self.publish(topic, 86400 * 365 * 10000, stat)

    def register(self) -> dict:
        url = f"{self.server_url}/api/register"
        try:
            response = self.requests.post(url)
            response.raise_for_status()
            self.session_id = response.json()['session_id']
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f'Registration request failed: {e}')
            return None

    def publish(self, topic: str, ttl: int, data) -> dict:
        if isinstance(data, dict):
            data = json.dumps(data)
        url = f"{self.server_url}/api/publish/{topic}"
        try:
            response = self.requests.post(url, headers={"Content-Type": "application/json; charset=utf-8"},
                                     data=json.dumps({"ttl": ttl, "data": data}))
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f'Publish request failed: {e}')
            return None

    def subscribe(self, topic: str) -> dict:
        url = f"{self.server_url}/api/subscribe/{topic}"
        try:
            response = self.requests.post(url, headers={"Content-Type": "application/json; charset=utf-8"},
                                     data=json.dumps({"session_id": self.session_id}))
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f'Subscribe request failed: {e}')
            return None

    def unsubscribe(self, topic: str) -> dict:
        url = f"{self.server_url}/api/subscribe/{topic}"
        try:
            response = self.requests.delete(url, headers={"Content-Type": "application/json; charset=utf-8"},
                                       data=json.dumps({"session_id": self.session_id}))
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f'Unsubscribe request failed: {e}')
            return None

    def receive(self) -> dict:
        url = f"{self.server_url}/api/receive"
        try:
            response = self.requests.get(url, params={"session_id": self.session_id})
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f'Receive request failed: {e}')
            return None

    def acknowledge(self, topic: str, message_id: str) -> dict:
        url = f"{self.server_url}/api/acknowledge"
        try:
            response = self.requests.post(url, headers={"Content-Type": "application/json; charset=utf-8"},
                                     data=json.dumps({"topic": topic, "message_id": message_id, "session_id": self.session_id}))
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f'Acknowledge request failed: {e}')
            return None
    
    def ack_all(self, messages: list[dict], output: bool = True) -> list[dict]:
        resp = []
        messages_len = len(messages)
        for i in range(messages_len):
            message = messages[i]
            topic = message['topic']
            message_id = message['message_id']
            data = message['data']
            if isinstance(data, str) and len(data) > 80:
                data = data[:80] + '...'
            ack_resp = {
                'success': False,
                'response': None,
                'error': None
            }
            try:
                ack_resp['response'] = self.acknowledge(topic, message_id)
                ack_resp['success'] = True
                if output:
                    print(f'\033[K[{i+1}/{len(messages)}] Acked message {message_id} on topic {topic}: {data}', end='\r')
            except requests.exceptions.RequestException as e:
                print(f'Acknowledge request failed: {e}')
                ack_resp['error'] = e
            resp.append(ack_resp)
        if output:
            print(f'\033[K', end='\r')
        return resp

    @staticmethod
    def auto_register(server_url: str, key: str = 'auto-register/test7246', ttl: int = 7200, stat: bool = True) -> 'HTTPMQClient':
        meta_client = HTTPMQClient(server_url, stat=False)
        meta_client.subscribe(key)
        meta_response = meta_client.receive()
        messages = meta_response.get('messages')
        client = None
        if messages and isinstance(messages, list) and len(messages) > 0:
            metadata_raw = messages[0].get('data')
            metadata = json.loads(metadata_raw)
            if 'session_id' in metadata:
                session_id = metadata['session_id']
                client = HTTPMQClient(server_url, session_id, stat=stat)
        if not client:
            client = HTTPMQClient(server_url, stat=stat)
        client.auto_register_key = key
        metadata = json.dumps({'session_id': client.session_id})
        meta_client.publish(key, ttl, metadata)
        return client
