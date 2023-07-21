from .models import Message, Session
from collections import defaultdict
import time
import threading

class MessageQueue:
    SESSION_TTL = 3600

    def __init__(self):
        self.lock = threading.Lock()
        self.sessions: dict[str, Session] = {} # session_id -> Session
        self.topic_messages: dict[str, dict[str, Message]] = defaultdict(defaultdict) # topic -> message_id -> Message

    def register(self, session_id: str) -> str:
        with self.lock:
            session = Session(session_id)
            self.sessions[session_id] = session
        return session.session_id

    def publish(self, topic: str, data: any, ttl: int = 3600) -> Message:
        with self.lock:
            message = Message(topic, data, ttl)
            self.topic_messages[topic][message.message_id] = message
            return message

    def subscribe(self, session_id: str, topic: str) -> bool:
        with self.lock:
            session = self.sessions.get(session_id)
            if session:
                return session.subscribe(topic)
            return False
        
    def unsubscribe(self, session_id: str, topic: str) -> bool:
        with self.lock:
            session = self.sessions.get(session_id)
            if session:
                return session.unsubscribe(topic)
            return False

    def acknowledge(self, session_id: str, topic_name: str, message_id: str) -> bool:
        with self.lock:
            session = self.sessions.get(session_id)
            if session and topic_name in session.subscribed_topics:
                message = self.topic_messages[topic_name].get(message_id)
                if message:
                    message.clients_acknowledged.add(session_id)
                    return session.acknowledge(topic_name, message_id)
            return False

    def receive(self, session_id: str) -> list[Message]:
        with self.lock:
            session = self.sessions.get(session_id)
            if session:
                messages: list[Message] = []
                for topic in session.subscribed_topics:
                    for message in self.topic_messages[topic].values():
                        if message.message_id not in session.acknowledged_messages:
                            messages.append(message)
                messages.sort(reverse=True)
                return messages
            return []

    def get_messages(self, topic: str) -> list[dict]:
        with self.lock:
            messages: list[Message] = []
            for message in self.topic_messages[topic].values():
                messages.append(message)
            messages.sort(reverse=True)
            mapped_messages: list[dict] = map(lambda message: message.to_dict_admin(), messages)
            return mapped_messages

    def get_topics(self) -> list[str]:
        with self.lock:
            return list(self.topic_messages.keys())
    
    def expire(self):
        timestamp = int(time.time())
        with self.lock:
            # expire sessions
            expired_sessions: list[str] = []
            for session_id, session in self.sessions.items():
                if timestamp - session.last_active > self.SESSION_TTL:
                    expired_sessions.append(session_id)
            for session_id in expired_sessions:
                del self.sessions[session_id]
            # expire messages
            expired_messages: set[str] = set()
            for messages in self.topic_messages.values():
                expired_messages_for_topic: list[Message] = []
                for message in messages.values():
                    if timestamp > message.expire_ts:
                        expired_messages.add(message.topic)
                        expired_messages_for_topic.append(message)
                for message in expired_messages_for_topic:
                    del messages[message.message_id]
            # expire acknowledged messages
            for session in self.sessions.values():
                session.acknowledged_messages.difference_update(expired_messages)
