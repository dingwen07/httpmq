import time
import platform
import threading
import curses
import curses.textpad
from httpmqchatroom import HTTPMQChatroom, ChatroomMessage

def input_with_default(prompt, default):
    result = input(f'{prompt} (Default is {default}): ')
    return result if result else default

def receive_func(pad, client, max_y, max_x, stdscr):
    row = 0
    while True:
        try:
            refresh = False
            # chechk if the terminal size has changed
            new_max_y, new_max_x = stdscr.getmaxyx()
            if new_max_x != max_x or new_max_y != max_y:
                pad.resize(1000, new_max_x)
                refresh = True
            max_x, max_y = new_max_x, new_max_y
            messages = client.receive()
            messages.sort(key=lambda x: x['timestamp'])
            for chat_message in messages:
                message_text = ChatroomMessage.message_to_text(chat_message['data'])
                if len(message_text) > 0:
                    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(chat_message["timestamp"]))
                    message = f'[{timestamp}] {message_text}'
                    pad.addstr(row, 0, message)
                    row += 1
                    refresh = True
            if refresh:
                min_row = 0 if row < max_y else row - max_y + 2
                pad.noutrefresh(min_row, 0, 0, 0, max_y-3, max_x-1)
            curses.doupdate()
        except:
            pass
        finally:
            time.sleep(0.5)

def chat(stdscr, client):
    # stdscr.nodelay(True)
    max_y, max_x = stdscr.getmaxyx()
    pad = curses.newpad(1000, max_x)  # create a new pad to store history of messages
    pad.scrollok(True)  # allow the pad to scroll

    threading.Thread(target=receive_func, args=(pad, client, max_y, max_x, stdscr), daemon=True).start()

    input_prompt = 'Input: '
    print(input_prompt, end='', flush=True)
    input_message = ''  # initialize variable to store user's input message
    try:
        while True:
            try:
                ch = stdscr.get_wch()
            except curses.error:
                continue
            if isinstance(ch, str):
                if ch == '\n':
                    if input_message.startswith('/nickname '):
                        new_nickname = input_message[10:]
                        client.update_nickname(new_nickname)
                    elif input_message == '/leave':
                        client.send_leave()
                        break
                    else:
                        client.send_message(input_message)
                    input_message = ''
                elif ch == '\b' or ch == '\x7f':
                    input_message = input_message[:-1]
                else:
                    input_message += ch
            elif ch == curses.KEY_RESIZE:
                max_y, max_x = stdscr.getmaxyx()
                stdscr.clear()  # clear the terminal to avoid display issues
                stdscr.refresh()
                pad.resize(1000, max_x)  # adjust the pad size accordingly

            stdscr.move(max_y - 1, 0)
            stdscr.clrtoeol()
            input_message_display = input_message
            if len(input_message) + len(input_prompt) > max_x - 1:
                input_message_display = '... ' + input_message[-(max_x - len(input_prompt) - 5):]
            stdscr.addstr(max_y - 1, 0, f'Input: {input_message_display}')

            stdscr.refresh()

            # time.sleep(0.01)
    except KeyboardInterrupt:
        client.send_leave()
    finally:
        curses.nocbreak()
        stdscr.keypad(False)
        curses.echo()
        curses.endwin()
        print('Bye')

if __name__ == '__main__':
    try:
        server_url = input_with_default('Server URL: ', 'http://127.0.0.1:5000')
        chatroom_id = input_with_default('Chatroom ID: ', 'test')
        nickname = input_with_default('Nickname: ', platform.node())
        auto_register_key = input_with_default('Auto register key: ', None)
    except KeyboardInterrupt:
        print('\nKeyboardInterrupt')
        exit(0)

    client = HTTPMQChatroom(server_url, chatroom_id, auto_register_key)
    client.nickname = nickname

    client.broadcast_info()
    client.send_join()

    curses.wrapper(chat, client)
