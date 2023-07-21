import time
import os
import sys
import platform
import random
from httpmqclient import HTTPMQClient

if __name__ == '__main__':
    client = HTTPMQClient.auto_register('http://127.0.0.1:5000', 'auto_register/test7246', 86400)
    print(f'Session ID: {client.session_id}')
    client.subscribe('test')
    client.publish('test', 300, 'Hello World!')
    for _ in range(1):
        client.publish('test', 60, 'Hello!')
    response = client.receive()
    message_len = len(response['messages'])
    print(f'Received {len(response["messages"])} messages')
    client.ack_all(response['messages'])
    client.unsubscribe('test')