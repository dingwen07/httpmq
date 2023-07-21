import curses
import time
import threading
import platform
import locale
import string
import unicodedata

from httpmqchatroom import HTTPMQChatroom, ChatroomMessage

locale.setlocale(locale.LC_ALL, '')

def input_with_default(prompt, default):
    result = input(f'{prompt} (Default is {default}): ')
    return result if result else default

def filter_non_printable(str):
    return ''.join(c for c in str if not unicodedata.category(c).startswith('C'))

def char_replace(char):
    print(char)

class ChatWindow:
    def __init__(self):
        self.resized = False

    def get_term_size(self, stdscr):
        return stdscr.getmaxyx()

    def monitor_resize(self, stdscr):
        current_size = self.get_term_size(stdscr)
        while True:
            new_size = self.get_term_size(stdscr)
            if new_size != current_size:
                current_size = new_size
                self.resized = True
            time.sleep(0.5)

    def receive_func(self, stdscr, pad, client):
        row = 0
        while True:
            if self.resized:
                self.resized = False
                max_y, max_x = stdscr.getmaxyx()
                stdscr.clear()
                stdscr.refresh()
                pad.redrawwin()
                pad.refresh(0,0, 0,0, max_y-2, max_x-1)

            messages = client.receive()
            messages.sort(key=lambda x: x['timestamp'])
            for chat_message in messages:
                message_text = ChatroomMessage.message_to_text(chat_message['data'])
                if len(message_text) > 0:
                    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(chat_message["timestamp"]))
                    message = f'[{timestamp}] {message_text}'
                    pad.addstr(row, 0, message)
                    row += 1
                max_y, max_x = stdscr.getmaxyx()
                pad.refresh(0,0, 0,0, max_y-2, max_x-1)
            time.sleep(1)

    def chat(self, stdscr, client):
        stdscr.nodelay(True)
        max_y, max_x = stdscr.getmaxyx()
        pad = curses.newpad(1000, max_x)  # create a new pad to store history of messages
        pad.scrollok(True)  # allow the pad to scroll

        threading.Thread(target=self.receive_func, args=(stdscr, pad, client), daemon=True).start()
        threading.Thread(target=self.monitor_resize, args=(stdscr,), daemon=True).start()

        input_message = ''  # initialize variable to store user's input message
        try:
            while True:
                c = stdscr.getch()
                if c != -1:
                    char_replace(c)
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

                max_y, max_x = stdscr.getmaxyx()
                stdscr.move(max_y - 1, 0)
                stdscr.clrtoeol()
                stdscr.addstr(max_y - 1, 0, f'Input: {filter_non_printable(input_message)}')
                stdscr.refresh()

                time.sleep(0.1)
        except KeyboardInterrupt:
            client.send_leave()
        finally:
            curses.nocbreak()
            stdscr.keypad(0)
            curses.echo()
            curses.endwin()


if __name__ == '__main__':
    server_url = input_with_default('Server URL: ', 'http://127.0.0.1:5000')
    chatroom_id = input_with_default('Chatroom ID: ', 'test')
    nickname = input_with_default('Nickname: ', platform.node())
    auto_register_key = input_with_default('Auto register key: ', None)

    client = HTTPMQChatroom(server_url, chatroom_id, auto_register_key)
    client.nickname = nickname

    client.broadcast_info()
    client.send_join()

    chat_window = ChatWindow()
    curses.wrapper(chat_window.chat, client)
