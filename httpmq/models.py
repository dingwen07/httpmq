from uuid import uuid4
import time
import json

class Message:
    def __init__(self, topic: str, data: str, ttl: int = 3600):
        self.message_id = str(uuid4())
        self.timestamp = int(time.time())
        self.topic = topic
        self.data = data
        self.ttl = ttl
        self.receive_time = time.time()
        self.expire_ts = self.timestamp + ttl
        self.clients_acknowledged: set[str] = set()
    
    def __eq__(self, __value: object) -> bool:
        if isinstance(__value, Message):
            return self.message_id == __value.message_id
        else:
            return False
    
    def __cmp__(self, __value: object) -> int:
        if isinstance(__value, Message):
            return self.receive_time - __value.receive_time
        else:
            return 0
    
    def __lt__(self, __value: object) -> bool:
        if isinstance(__value, Message):
            return self.receive_time < __value.receive_time
        else:
            return False
    
    def __gt__(self, __value: object) -> bool:
        if isinstance(__value, Message):
            return self.receive_time > __value.receive_time
        else:
            return False
    
    def __hash__(self) -> int:
        return hash(self.message_id)
    
    def to_dict(self) -> dict:
        return {
            'message_id': self.message_id,
            'topic': self.topic,
            'data': self.data,
            'timestamp': self.timestamp,
            'ttl': self.ttl,
        }
    
    def to_dict_admin(self) -> dict:
        data = self.data
        try:
            data = json.loads(self.data)
        except:
            pass
        if isinstance(data, str) and len(data) > 80:
            data = self.data[:80] + '...'
        return {
            'message_id': self.message_id,
            'topic': self.topic,
            'data': data,
            'timestamp': self.timestamp,
            'ttl': self.ttl,
            'receive_time': self.receive_time,
            'expire_ts': self.expire_ts,
            'clients_acknowledged': list(self.clients_acknowledged),
        }

class Session:
    def __init__(self, session_id: str = None):
        if not session_id:
            session_id = str(uuid4())
        self.session_id = session_id
        self.subscribed_topics: set[str] = set()
        self.acknowledged_messages: set[str] = set()
        self.last_active = int(time.time())
    
    def refresh(self):
        self.last_active = int(time.time())
    
    def subscribe(self, topic: str) -> bool:
        if topic in self.subscribed_topics:
            return False
        self.subscribed_topics.add(topic)
        return True

    def unsubscribe(self, topic: str) -> bool:
        if topic in self.subscribed_topics:
            self.subscribed_topics.remove(topic)
            return True
        return False
    
    def acknowledge(self, topic_name: str, message_id: str) -> bool:
        if topic_name in self.subscribed_topics:
            self.acknowledged_messages.add(message_id)
            return True
        return False
