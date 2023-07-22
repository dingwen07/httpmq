import time
import platform
import threading
import queue
import curses
import curses.textpad
from httpmqchatroom import HTTPMQChatroom, ChatroomMessage

HELP_MESSAGE = '''\

Commands:
    /nickname <nickname>    Change nickname
    /leave                  Leave the chatroom
    /clear                  Clear the screen
    /help                   Show this help message
'''

def input_with_default(prompt, default):
    result = input(f'{prompt} (Default is {default}): ')
    return result if result else default

def receive_func(pad, client, max_y, max_x, stdscr, screen_control_queue):
    time.sleep(0.3)
    row = 0
    screen_content: list[str] = []
    next_delay = 0
    while True:
        try:
            y, x = curses.getsyx()
            refresh = False
            # chechk if the terminal size has changed
            new_max_y, new_max_x = stdscr.getmaxyx()
            if new_max_x != max_x or new_max_y != max_y:
                pad.clear()
                row = 0
                for line in screen_content:
                    pad.addstr(row, 0, line)
                    row += int((len(line) - 1) / max_x) + 1
                refresh = True
                max_x, max_y = new_max_x, new_max_y
                next_delay = -1
            if not screen_control_queue.empty():
                control = screen_control_queue.get()
                if control == 0:
                    pad.clear()
                    pad.noutrefresh(0, 0, 0, 0, max_y-3, max_x-1)
                    row = 0
                else:
                    row += control
                curses.setsyx(y, x)
                refresh = True
            messages = client.receive()
            messages.sort(key=lambda x: x['timestamp'])
            for chat_message in messages:
                message_text = ChatroomMessage.message_to_text(chat_message['data'])
                if len(message_text) > 0:
                    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(chat_message["timestamp"]))
                    message = f'[{timestamp}] {message_text}'
                    pad.addstr(row, 0, message)
                    screen_content.append(message)
                    row += int((len(message) - 1) / max_x) + 1
                    refresh = True
            if refresh:
                min_row = 0 if row < max_y else row - max_y + 2
                pad.noutrefresh(min_row, 0, 0, 0, max_y-3, max_x-1)
                curses.setsyx(y, x)
            curses.doupdate()
        except:
            pass
        finally:
            if next_delay < 0:
                pass
            if next_delay > 0:
                time.sleep(next_delay)
            else:
                time.sleep(0.3)
            next_delay = 0

def chat(stdscr, client):
    # stdscr.nodelay(True)
    max_y, max_x = stdscr.getmaxyx()
    pad = curses.newpad(1000, max_x)  # create a new pad to store history of messages
    pad.scrollok(True)  # allow the pad to scroll
    screen_control_queue = queue.Queue()

    threading.Thread(target=receive_func, args=(pad, client, max_y, max_x, stdscr, screen_control_queue), daemon=True).start()

    input_prompt = 'Input: '
    leave_prompt = '/Press Enter now or Hit Ctrl-C again to Leave'
    leave_commands = ['/leave', '/quit', '/exit', leave_prompt]
    input_message = ''  # initialize variable to store user's input message
    stdscr.addstr(max_y - 1, 0, f'Input: {input_message}')
    curses.setsyx(max_y - 1, len(input_prompt))
    while True:
        try:
            ch = None
            try:
                ch = stdscr.get_wch()
            except curses.error:
                stdscr.nodelay(False)
            if isinstance(ch, str):
                if ch == '\n':
                    if input_message.startswith('/nickname '):
                        new_nickname = input_message[10:]
                        client.update_nickname(new_nickname)
                    elif input_message in leave_commands:
                        raise KeyboardInterrupt
                    elif input_message == '/clear':
                        screen_control_queue.put(0)
                    elif input_message == '/help':
                        pad.addstr(HELP_MESSAGE)
                        pad.noutrefresh(0, 0, 0, 0, max_y-3, max_x-1)
                        curses.setsyx(max_y - 1, len(input_prompt))
                        screen_control_queue.put(HELP_MESSAGE.count('\n'))
                    elif input_message.startswith('/'):
                        continue
                    elif input_message != '':
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
            if input_message in leave_commands:
                client.send_leave()
                curses.nocbreak()
                stdscr.keypad(False)
                curses.echo()
                curses.endwin()
                print('Bye')
                exit(0)
            else:
                input_message = leave_prompt
                stdscr.nodelay(True)
        except Exception as e:
            print(e)

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
