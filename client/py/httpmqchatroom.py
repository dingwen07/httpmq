import time
import json
import platform
import logging
from enum import Enum
from httpmqclient import HTTPMQClient

CHATROOM_APP = 'HTTPMQChatroom'

class HTTPMQChatroom:
    CHATROOM_APP = CHATROOM_APP
    
    def __init__(self, server_url: str, chatroom_id: str, auto_register_key: str = None):
        self.server_url = server_url
        self.chatroom_id = chatroom_id
        self.topic = f'{CHATROOM_APP}/{chatroom_id}'
        self.chatroom_ids = [chatroom_id]
        if not auto_register_key:
            self.client = HTTPMQClient(server_url)
        else:
            self.client = HTTPMQClient.auto_register(server_url, auto_register_key, 7200)
        if not self.client.session_id:
            raise ValueError('Unable to connect to server')
        self.client.subscribe(self.topic)
        try:
            self.client.ack_all(self.client.receive()['messages'], output=False)
        except:
            pass
        self.nickname = platform.node()
    
    def receive(self) -> list[dict]:
        resp = self.client.receive()
        if resp:
            messages = resp['messages']
            if messages:
                self.client.ack_all(messages, output=False)
                # update data field to ChatroomMessage
                for message in messages:
                    try:
                        data_dict = json.loads(message['data'])
                        message['data'] = ChatroomMessage.from_dict(data_dict)
                    except:
                        logging.info(f'Failed to parse message: {message}')
                        message['data'] = None
                ret = []
                for message in messages:
                    if message['data']:
                        ret.append(message)
                return ret
        return []
    
    def add_chatroom(self, chatroom_id: str):
        if chatroom_id in self.chatroom_ids:
            return
        topic = f'{CHATROOM_APP}/{chatroom_id}'
        self.chatroom_ids.append(chatroom_id)
        self.client.subscribe(topic)
    
    def remove_chatroom(self, chatroom_id: str):
        if chatroom_id not in self.chatroom_ids:
            return
        topic = f'{CHATROOM_APP}/{chatroom_id}'
        self.chatroom_ids.remove(chatroom_id)
        self.client.unsubscribe(topic)
        if self.chatroom_id == chatroom_id:
            self.chatroom_id = self.chatroom_ids[0]
            self.topic = f'{CHATROOM_APP}/{self.chatroom_id}'
    
    def switch_chatroom(self, chatroom_id: str):
        if not chatroom_id in self.chatroom_ids:
            return
        topic = f'{CHATROOM_APP}/{chatroom_id}'
        self.topic = topic
        self.chatroom_id = chatroom_id
    
    def broadcast_info(self):
        chatroom_message = ChatroomMessage(ChatroomMessageTypes.CTRL_INFO, '')
        self._publish(chatroom_message)
    
    def send_join(self):
        chatroom_message = ChatroomMessage(ChatroomMessageTypes.CTRL_JOIN, '')
        self._publish(chatroom_message)
    
    def send_leave(self):
        chatroom_message = ChatroomMessage(ChatroomMessageTypes.BCST_LEAVE, '')
        self._publish(chatroom_message)
    
    def update_nickname(self, nickname: str):
        old_nickname = self.nickname
        self.nickname = nickname
        chatroom_message = ChatroomMessage(ChatroomMessageTypes.BCST_NICKNAME, old_nickname)
        self._publish(chatroom_message)

    def send_message(self, message: str):
        chatroom_message = ChatroomMessage(ChatroomMessageTypes.CHAT_CHAT, message)
        self._publish(chatroom_message)
    
    def run(self, interval = 1):
        self.broadcast_info()
        self.send_join()
        while True:
            messages = self.receive()
            # sort messages by timestamp
            messages.sort(key=lambda x: x['timestamp'])
            for message in messages:
                # print message time
                message_text = ChatroomMessage.message_to_text(message['data'])
                if len(message_text) > 0:
                    print(f'[{time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(message["timestamp"]))}]', end=' ')
                    print(message_text)
            time.sleep(interval)
    
    def _publish(self, message: 'ChatroomMessage'):
        message.meta['nickname'] = self.nickname
        self.client.publish(self.topic, ChatroomMessageTypes.types.value[message.type.value]['ttl'], data=message.to_dict())


class ChatroomMessage:
    def __init__(self, message_type: 'ChatroomMessageTypes', message_body: str, message_meta: dict = {}):
        self.type = message_type
        self.body = message_body
        self.meta = message_meta
    
    def to_dict(self) -> dict:
        return {
            'type': self.type.value,
            'body': self.body,
            'meta': self.meta,
        }
    
    @staticmethod
    def from_dict(message_dict: dict) -> 'ChatroomMessage':
        return ChatroomMessage(ChatroomMessageTypes(message_dict['type']), message_dict['body'], message_dict['meta'])

    @staticmethod
    def message_to_text(message: 'ChatroomMessage', chatroom_id = '') -> str:
        msg_str = ''
        nickname = ''
        meta = message.meta
        if meta:
            nickname = meta.get('nickname')
            if not nickname:
                nickname = 'Anonymous'
        if len(nickname) > 9:
            nickname = nickname[:9] + '~'
        if chatroom_id != '':
            nickname += f'@{chatroom_id}'
        if message.type == ChatroomMessageTypes.CHAT_CHAT:
            msg_str += f'{nickname}: '
            msg_str += message.body
        elif message.type == ChatroomMessageTypes.CTRL_JOIN:
            msg_str += f'{nickname} joined the chat'
        elif message.type == ChatroomMessageTypes.BCST_LEAVE:
            msg_str += f'{nickname} left the chat'
        elif message.type == ChatroomMessageTypes.BCST_NICKNAME:
            msg_str += f'{message.body} changed nickname to {nickname}'
        return msg_str


class ChatroomMessageTypes(Enum):
    CHAT_CHAT = 'chat-chat'
    CTRL_JOIN = 'ctrl-join'
    CTRL_INFO = 'ctrl-info'
    BCST_LEAVE = 'bcst-leave'
    BCST_NICKNAME = 'bcst-nickname'

    types = {
        'chat-chat': {
            'ttl': 300,
        },
        'ctrl-join': {
            'ttl': 300,
        },
        'ctrl-info': {
            'ttl': 60,
        },
        'bcst-leave': {
            'ttl': 300,
        },
        'bcst-nickname': {
            'ttl': 300,
        },
    }

def input_with_default(prompt: str, default: str) -> str:
    value = input(prompt)
    if value == '':
        return default
    return value


if __name__ == '__main__':
    server_url = input_with_default('Server URL: ', 'http://127.0.0.1:5000')
    chatroom_id = input_with_default('Chatroom ID: ', 'test')
    nickname = input_with_default('Nickname: ', platform.node())
    auto_register_key = input_with_default('Auto register key: ', f'auto-register/{platform.node()}')
    client = HTTPMQChatroom(server_url, chatroom_id, auto_register_key)
    client.nickname = nickname
    client.run()

