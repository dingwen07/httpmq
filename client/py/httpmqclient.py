import requests
import json

class HTTPMQClient:
    def __init__(self, server_url, session_id=None):
        self.server_url = server_url
        self.session_id = session_id

    def register(self):
        url = f"{self.server_url}/api/register"
        try:
            response = requests.post(url)
            response.raise_for_status()
            self.session_id = response.json()['session_id']
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f'Registration request failed: {e}')
            return None

    def publish(self, topic, ttl, data):
        url = f"{self.server_url}/api/publish/{topic}"
        try:
            response = requests.post(url, headers={"Content-Type": "application/json; charset=utf-8"},
                                     data=json.dumps({"ttl": ttl, "data": data}))
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f'Publish request failed: {e}')
            return None

    def subscribe(self, topic):
        url = f"{self.server_url}/api/subscribe/{topic}"
        try:
            response = requests.post(url, headers={"Content-Type": "application/json; charset=utf-8"},
                                     data=json.dumps({"session_id": self.session_id}))
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f'Subscribe request failed: {e}')
            return None

    def unsubscribe(self, topic):
        url = f"{self.server_url}/api/subscribe/{topic}"
        try:
            response = requests.delete(url, headers={"Content-Type": "application/json; charset=utf-8"},
                                       data=json.dumps({"session_id": self.session_id}))
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f'Unsubscribe request failed: {e}')
            return None

    def receive(self):
        url = f"{self.server_url}/api/receive"
        try:
            response = requests.get(url, params={"session_id": self.session_id})
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f'Receive request failed: {e}')
            return None

    def acknowledge(self, topic, message_id):
        url = f"{self.server_url}/api/acknowledge"
        try:
            response = requests.post(url, headers={"Content-Type": "application/json; charset=utf-8"},
                                     data=json.dumps({"topic": topic, "message_id": message_id, "session_id": self.session_id}))
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f'Acknowledge request failed: {e}')
            return None
