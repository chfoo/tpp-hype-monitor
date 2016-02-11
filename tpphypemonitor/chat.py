import logging
import random
import sched
import time

import arrow
import irc.client
import irc.strings

from tpphypemonitor.irc import IRCClient
from tpphypemonitor.source import InputSourceThread

_logger = logging.getLogger(__name__)


class TwitchClient(IRCClient):
    def __init__(self, channel, message_callback):
        super().__init__(reconnect_min_interval=2)
        self._channel = irc.strings.lower(channel)
        self._message_callback = message_callback

    def stop(self):
        self.reactor.disconnect_all()

    def on_welcome(self, connection, event):
        super().on_welcome(connection, event)
        self.connection.cap('REQ', 'twitch.tv/membership')
        self.connection.cap('REQ', 'twitch.tv/commands')
        self.connection.cap('REQ', 'twitch.tv/tags')
        self.connection.join(self._channel)

    def on_pubmsg(self, connection, event):
        channel = irc.strings.lower(event.target)

        if channel != self._channel:
            return

        if not hasattr(event.source, 'nick'):
            return

        nick = irc.strings.lower(event.source.nick)

        self._message_callback(nick, event.arguments[0])


class TwitchInputSource(InputSourceThread):
    def __init__(self, server, channel):
        super().__init__()
        self._client = None
        self._server = server
        self._channel = channel
        self._running = False

    def run(self):
        self._running = True

        def feed_calculator(nick, text):
            if random.random() < 0.1:
                _logger.debug('Chat: %s: %s', nick, text)
            self._calculator.add_chat_activity(nick, text)

        self._client = TwitchClient(self._channel, feed_calculator)
        nickname = 'justinfan{}'.format(random.randint(0, 1000000))

        _logger.info('Connecting...')
        self._client.autoconnect(self._server, 6667, nickname)

        while self._running:
            self._client.reactor.process_once(0.2)

    def stop(self):
        self._running = False
        self._client.stop()
