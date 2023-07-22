import time
import platform
import threading
import queue
import unicodedata
import logging
import curses
import curses.textpad
import curses.ascii
from httpmqchatroom import HTTPMQChatroom, ChatroomMessage

HELP_MESSAGE = '''\

Commands:
    /nickname <nickname>      Change nickname
    /join <chatroom_id>       Join and switch to a chatroom
    /subscribe <chatroom_id>  Join a chatroom without switching to it
    /leave <chatroom_id>      Leave a chatroom (you will be switched to
                              another chatroom, if you only subscribed to
                              one chatroom, you will join the `default` 
                              chatroom)
    /switch <chatroom_id>     Switch to a chatroom, you must first subscribe
                              to the chatroom
    /discovery <on|off>       Enable or disable chatroom discovery
    /[list|ls]                List joined chatrooms
    /clear                    Clear the screen
    /help                     Show this help message
    /[quit|exit]              Exit the chatroom
Note: you can dismiss this help message by changing the terminal size
'''

def impart(package_name) -> bool:
    try:
        __import__(package_name)
        return True
    except ImportError:
        return False

USE_WCWIDTH = impart('wcwidth')
TAB_WIDTH = 8

def display_length(text):
    total_width = 0
    for char in text:
        if char == "\t":
            width = TAB_WIDTH - (total_width % TAB_WIDTH) + 1
        else:
            if USE_WCWIDTH:
                width = wcwidth.wcswidth(char)
            else:
                width = 1 if unicodedata.combining(char) == 0 else 0
            if width < 0:
                # For non-printable characters, assume display width of 0.
                width = 0
        total_width += width
    return total_width

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
                refresh = True
            messages = client.receive()
            messages.sort(key=lambda x: x['timestamp'])
            for chat_message in messages:
                topic = chat_message['topic']
                chatroom_id = ''
                if topic.startswith(f'{HTTPMQChatroom.CHATROOM_APP}/'):
                    chatroom_id = topic[len(f'{HTTPMQChatroom.CHATROOM_APP}/'):]
                message_text = ChatroomMessage.message_to_text(chat_message['data'], chatroom_id)
                if len(message_text) > 0:
                    timestamp = time.strftime("%y-%m-%d %H:%M:%S", time.localtime(chat_message["timestamp"]))
                    message = f'[{timestamp}] {message_text}'
                    pad.addstr(row, 0, message)
                    screen_content.append(message)
                    row += int((len(message) - 1) / max_x) + 1
                    refresh = True
            if refresh:
                min_row = 0 if row < max_y - 1 else row - max_y + 2
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
    exit_prompt = '/Press Enter now or Hit Ctrl-C again to Exit'
    exit_commands = ['/quit', '/exit', exit_prompt]
    input_message = ''  # initialize variable to store user's input message
    input_pos = 0  # initialize variable to store the cursor position
    input_history = []  # initialize variable to store the input history
    input_history_pos = 0  # initialize variable to store the input history position
    stdscr.addstr(max_y - 1, 0, f'Input: {input_message}')
    curses.setsyx(max_y - 1, len(input_prompt))
    while True:
        try:
            ch = None
            try:
                input_visible_length = display_length(input_message[:input_pos])
                curses.setsyx(max_y - 1, len(input_prompt) + input_visible_length)
                curses.doupdate()
                ch = stdscr.get_wch()
            except curses.error:
                stdscr.nodelay(False)
            if isinstance(ch, str):
                if ch == '\n':
                    input_history_pos = 0
                    if len(input_message) != 0 and (len(input_history) == 0 or input_message != input_history[-1]):
                        input_history.append(input_message)
                    if input_message.startswith('/nickname '):
                        new_nickname = input_message[10:]
                        client.update_nickname(new_nickname)
                    elif input_message.startswith('/join '):
                        new_chatroom_id = input_message[6:]
                        client.add_chatroom(new_chatroom_id)
                        client.switch_chatroom(new_chatroom_id)
                        client.send_join()
                    elif input_message.startswith('/subscribe '):
                        new_chatroom_id = input_message[11:]
                        client.add_chatroom(new_chatroom_id)
                        old_chatroom_id = client.chatroom_id
                        client.switch_chatroom(new_chatroom_id)
                        client.send_join()
                        client.switch_chatroom(old_chatroom_id)
                    elif input_message.startswith('/leave '):
                        leave_chatroom_id = input_message[7:]
                        client.remove_chatroom(leave_chatroom_id)
                    elif input_message.startswith('/switch '):
                        switch_chatroom_id = input_message[8:]
                        client.switch_chatroom(switch_chatroom_id)
                    elif input_message.startswith('/discovery '):
                        if input_message[11:] == 'on':
                            client.discovery(True)
                            client.discovery_dispatch()
                        elif input_message[11:] == 'off':
                            client.discovery(False)
                            client.discovery_dispatch()
                        else:
                            curses.beep()
                            continue
                    elif input_message == '/list' or input_message == '/ls':
                        client.discover_chatrooms()
                        client.chatroom_ids.sort()
                        client.discovered_chatroom_ids.sort()
                        ls_message = '\nJoined Chatrooms: \n'
                        for chatroom_id in client.chatroom_ids:
                            ls_message += f'\t{chatroom_id}\n'
                        ls_message += 'Discovered Chatrooms: \n'
                        for chatroom_id in client.discovered_chatroom_ids:
                            ls_message += f'\t{chatroom_id}\n'
                        if not client.discovery_enabled:
                            ls_message += '\nDiscovery is Not Enabled\n'
                        pad.addstr(ls_message)
                        pad.noutrefresh(0, 0, 0, 0, max_y-3, max_x-1)
                        curses.setsyx(max_y - 1, len(input_prompt))
                        screen_control_queue.put(ls_message.count('\n'))
                    elif input_message in exit_commands:
                        raise KeyboardInterrupt
                    elif input_message == '/clear':
                        screen_control_queue.put(0)
                    elif input_message == '/help' or input_message == '/?':
                        pad.addstr(HELP_MESSAGE)
                        pad.noutrefresh(0, 0, 0, 0, max_y-3, max_x-1)
                        curses.setsyx(max_y - 1, len(input_prompt))
                        screen_control_queue.put(HELP_MESSAGE.count('\n'))
                    elif input_message.startswith('/'):
                        input_history.pop()
                        curses.beep()
                        continue
                    elif input_message != '':
                        client.send_message(input_message)
                        client.discovery_dispatch()
                    else:
                        curses.beep()
                        continue
                    input_message = ''
                    input_pos = 0
                elif ch == '\b' or ch == '\x7f':
                    if len(input_message) > 0:
                        input_message = input_message[:input_pos - 1] + input_message[input_pos:]
                        input_pos -= 1
                    else:
                        curses.beep()
                # ESC
                elif ch == '\x1b':
                    input_message = ''
                    input_pos = 0
                # tab completion
                elif ch == '\t' and input_message.startswith('/'):
                    # match chatroom
                    if input_message.startswith('/switch ') or input_message.startswith('/leave '):
                        chatroom_id_incomplete = input_message.split(' ', maxsplit=1)[1]
                        matched_chatroom_ids = [chatroom_id for chatroom_id in client.chatroom_ids if chatroom_id.startswith(chatroom_id_incomplete)]
                        if len(matched_chatroom_ids) == 1:
                            input_message = input_message.split(' ', maxsplit=1)[0] + ' ' + matched_chatroom_ids[0]
                            input_pos = len(input_message)
                        if len(matched_chatroom_ids) > 1:
                            matched_chatroom_ids.sort(key=len)
                            input_message = input_message.split(' ')[0] + ' ' + matched_chatroom_ids[0]
                            input_pos = len(input_message)
                    # match discovery
                    if input_message.startswith('/join ') or input_message.startswith('/subscribe '):
                        chatroom_id_incomplete = input_message.split(' ', maxsplit=1)[1]
                        chatroom_id_incomplete = chatroom_id_incomplete.lstrip()
                        matched_chatroom_ids = [chatroom_id for chatroom_id in client.discovered_chatroom_ids if chatroom_id.startswith(chatroom_id_incomplete)]
                        if len(matched_chatroom_ids) == 1:
                            input_message = input_message.split(' ', maxsplit=1)[0] + ' ' + matched_chatroom_ids[0]
                            input_pos = len(input_message)
                        elif len(matched_chatroom_ids) > 1:
                            matched_chatroom_ids.sort(key=len)
                            input_message = input_message.split(' ')[0] + ' ' + matched_chatroom_ids[0]
                            input_pos = len(input_message)
                    # match discovery command
                    elif input_message.startswith('/discovery '):
                        commands = ['on', 'off']
                        matched_commands = [command for command in commands if command.startswith(input_message[11:])]
                        if len(matched_commands) == 1:
                            input_message = input_message.split(' ')[0] + ' ' + matched_commands[0]
                            input_pos = len(input_message)
                    # match command
                    elif input_message.startswith('/'):
                        commands = ['/nickname ', '/join ', '/subscribe ', '/leave ', '/switch ', '/discovery ', '/clear', '/list', '/help', '/quit', '/exit']
                        matched_commands = [command for command in commands if command.startswith(input_message)]
                        if len(matched_commands) == 1:
                            input_message = matched_commands[0]
                            input_pos = len(input_message)
                        else:
                            curses.beep()
                else:
                    input_message = input_message[:input_pos] + ch + input_message[input_pos:]
                    input_pos += 1
            elif ch == curses.KEY_RESIZE:
                max_y, max_x = stdscr.getmaxyx()
                stdscr.clear()  # clear the terminal to avoid display issues
                stdscr.refresh()
                pad.resize(1000, max_x)  # adjust the pad size accordingly
            elif ch == curses.KEY_BACKSPACE:
                if len(input_message) > 0:
                    input_message = input_message[:input_pos - 1] + input_message[input_pos:]
                    input_pos -= 1
                else:
                    curses.beep()
            elif ch == curses.KEY_LEFT:
                if len(input_message) <= 0 or input_pos <= 0:
                    curses.beep()
                    continue
                input_pos -= 1
                continue
            elif ch == curses.KEY_RIGHT:
                if len(input_message) <= 0 or input_pos >= len(input_message):
                    curses.beep()
                    continue
                input_pos += 1
                continue
            elif ch == curses.KEY_UP:
                if len(input_history) <= 0 or input_history_pos >= len(input_history):
                    curses.beep()
                    continue
                input_history_pos += 1
                input_message = input_history[-input_history_pos]
                input_pos = len(input_message)
            elif ch == curses.KEY_DOWN:
                if len(input_history) <= 0 or input_history_pos <= 0:
                    curses.beep()
                    continue
                input_history_pos -= 1
                if input_history_pos == 0:
                    input_message = ''
                else:
                    input_message = input_history[-input_history_pos]
                input_pos = len(input_message)

            stdscr.move(max_y - 1, 0)
            stdscr.clrtoeol()
            input_message_display = input_message
            if len(input_message) + len(input_prompt) > max_x - 1:
                input_message_display = '... ' + input_message[-(max_x - len(input_prompt) - 5):]
            stdscr.addstr(max_y - 1, 0, f'Input: {input_message_display}')
            stdscr.refresh()
            # time.sleep(0.01)
        except KeyboardInterrupt:
            if input_message in exit_commands:
                client.send_leave()
                curses.nocbreak()
                stdscr.keypad(False)
                curses.echo()
                curses.endwin()
                print('Bye')
                exit(0)
            else:
                input_message = exit_prompt
                stdscr.nodelay(True)
        except Exception as e:
            raise

if __name__ == '__main__':
    if USE_WCWIDTH:
        import wcwidth
    else:
        logging.warning('wcwidth is not installed, some characters may not be displayed correctly after arrow keys are pressed')

    try:
        server_url = input_with_default('Server URL: ', 'http://127.0.0.1:5002')
        chatroom_id = input_with_default('Chatroom ID: ', 'test')
        nickname = input_with_default('Nickname: ', platform.node())
        enable_discovery = input_with_default('Enable Discovery? (y/n): ', 'y')
        if enable_discovery == 'y':
            enable_discovery = True
        else:
            enable_discovery = False
        auto_register_key = None
    except KeyboardInterrupt:
        print('\nKeyboardInterrupt')
        exit(0)

    client = HTTPMQChatroom(server_url, chatroom_id, auto_register_key)
    client.nickname = nickname
    if enable_discovery:
        client.discovery(True)

    client.broadcast_info()
    client.send_join()

    curses.wrapper(chat, client)
