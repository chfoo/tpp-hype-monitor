import logging

import irc.client
import time

RECONNECT_SUCCESS_THRESHOLD = 60
RECONNECT_MIN_INTERVAL = 60
RECONNECT_MAX_INTERVAL = 300
KEEP_ALIVE = 60
IRC_RATE_LIMIT = (20 - 0.5) / 30


_logger = logging.getLogger(__name__)


class IRCClient(irc.client.SimpleIRCClient):
    def __init__(self, reconnect_min_interval=RECONNECT_MIN_INTERVAL):
        super().__init__()
        self._reconnect_min_interval = reconnect_min_interval
        self._reconnect_time = reconnect_min_interval
        self._last_connect = 0

        irc.client.ServerConnection.buffer_class.errors = 'replace'
        self.connection.set_rate_limit(IRC_RATE_LIMIT)

        self.reactor.execute_every(KEEP_ALIVE, self._keep_alive)

    def autoconnect(self, *args, **kwargs):
        try:
            if args:
                self.connect(*args, **kwargs)
            else:
                self.connection.reconnect()
        except irc.client.ServerConnectionError:
            _logger.exception('Connect failed.')
            self._schedule_reconnect()

    def _schedule_reconnect(self):
        time_now = time.time()

        if time_now - self._last_connect > RECONNECT_SUCCESS_THRESHOLD:
            self._reconnect_time *= 2
            self._reconnect_time = min(RECONNECT_MAX_INTERVAL,
                                       self._reconnect_time)
        else:
            self._reconnect_time = self._reconnect_min_interval

        _logger.info('Reconnecting in %s seconds.', self._reconnect_time)
        self.reactor.execute_delayed(self._reconnect_time,
                                     self.autoconnect)

    def _keep_alive(self):
        if self.connection.is_connected():
            self.connection.ping('keep-alive')

    def on_welcome(self, connection, event):
        _logger.info('Logged in to server.')
        self._last_connect = time.time()
