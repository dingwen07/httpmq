import time
import os
import sys
import io
import platform
import requests
import json

class HTTPMQClient:
    def __init__(self, server_url, session_id = None, stat = True):
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
                'server_url': server_url,
                'session_id': session_id
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

    def publish(self, topic: str, ttl: int, data: str | dict) -> dict:
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
    
    def ack_all(self, messages: list[dict], output: io.TextIOWrapper = sys.stdout) -> list[dict]:
        resp = []
        messages_len = len(messages)
        for i in range(messages_len):
            message = messages[i]
            topic = message['topic']
            message_id = message['message_id']
            data = message['data']
            if len(data) > 10:
                data = data[:7] + '...'
            ack_resp = {
                'success': False,
                'response': None,
                'error': None
            }
            try:
                ack_resp['response'] = self.acknowledge(topic, message_id)
                ack_resp['success'] = True
                print(f'[{i+1}/{messages_len}] Acked message {message_id} on topic {topic}: {data}', file=output)
            except requests.exceptions.RequestException as e:
                print(f'Acknowledge request failed: {e}')
                ack_resp['error'] = e
            resp.append(ack_resp)
        return resp
    
    @staticmethod
    def auto_register(server_url: str, key: str = 'auto_register/test7246', ttl: int = 86400, stat: bool = True) -> 'HTTPMQClient':
            meta_client = HTTPMQClient(server_url, stat=False)
            meta_client.subscribe(key)
            meta_response = meta_client.receive()
            messages = meta_response.get('messages')
            if messages and isinstance(messages, list) and len(messages) > 0:
                metadata_raw = messages[0].get('data')
                metadata = json.loads(metadata_raw)
                if 'session_id' in metadata:
                    session_id = metadata['session_id']
                    return HTTPMQClient(server_url, session_id, stat=stat)
            client = HTTPMQClient(server_url, stat=stat)
            metadata = json.dumps({'session_id': client.session_id})
            meta_client.publish(key, ttl, metadata)
            return client
