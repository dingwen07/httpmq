import time
import platform
from httpmqclient import HTTPMQClient

if __name__ == '__main__':
    client = HTTPMQClient.auto_register('http://127.0.0.1:5000', f'auto-register/{platform.node()}', 86400)
    print(f'Session ID: {client.session_id}')
    client.subscribe('test')
    client.publish('test', 300, 'Hello World!')
    for _ in range(1):
        client.publish('test', 60, 'Hello!')
    try:
        while True:
            response = client.receive()
            message_len = len(response['messages'])
            if message_len == 0:
                time.sleep(1)
                continue
            print(f'Received {len(response["messages"])} messages')
            for message in response['messages']:
                print(f'  {message["message_id"]}: {message["data"]} (ts: {message["timestamp"]})')
            client.ack_all(response['messages'])
    except KeyboardInterrupt:
        print('Unsubscribe and exit')
    client.unsubscribe('test')
