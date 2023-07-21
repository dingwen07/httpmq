import curses
import time
import threading
import platform
from httpmqchatroom import HTTPMQChatroom, ChatroomMessage

def input_with_default(prompt, default):
    result = input(f'{prompt} (Default is {default}): ')
    return result if result else default

def receive_func(window, client):
    row = 0
    while True:
        messages = client.receive()
        messages.sort(key=lambda x: x['timestamp'])
        for chat_message in messages:
            message_text = ChatroomMessage.message_to_text(chat_message['data'])
            if len(message_text) > 0:
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(chat_message["timestamp"]))
                message = f'[{timestamp}] {message_text}'
                window.addstr(row, 0, message)
                window.refresh()
                row += 1
        time.sleep(1)

def chat(stdscr, client):
    stdscr.nodelay(True)
    max_y, max_x = stdscr.getmaxyx()
    window = curses.newwin(max_y, max_x, 0, 0)  # create a new window to display messages

    threading.Thread(target=receive_func, args=(window, client), daemon=True).start()

    input_message = ''  # initialize variable to store user's input message
    while True:
        c = stdscr.getch()
        if c != -1:
            if c == ord('\n'):
                if input_message.startswith("/nickname "):
                    new_nickname = input_message[10:]
                    client.update_nickname(new_nickname)
                elif input_message == "/leave":
                    client.send_leave()
                    break
                else:
                    client.send_message(input_message)
                input_message = ''
            elif c == ord('\b'):
                input_message = input_message[:-1]
            else:
                input_message += chr(c)

        stdscr.move(max_y - 1, 0)
        stdscr.clrtoeol()
        stdscr.addstr(max_y - 1, 0, f'Input: {input_message}')

        stdscr.refresh()

        time.sleep(0.1)

if __name__ == '__main__':
    server_url = input_with_default('Server URL: ', 'http://127.0.0.1:5000')
    chatroom_id = input_with_default('Chatroom ID: ', 'test')
    nickname = input_with_default('Nickname: ', platform.node())
    auto_register_key = input_with_default('Auto register key: ', None)

    client = HTTPMQChatroom(server_url, chatroom_id, auto_register_key)
    client.nickname = nickname

    client.broadcast_info()
    client.send_join()

    curses.wrapper(chat, client)
