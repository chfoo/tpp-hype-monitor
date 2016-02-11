import json
import logging
import sched
import time
import tornado.ioloop
import tornado.gen
import tornado.httpclient
import tornado.websocket

from tpphypemonitor.source import InputSourceThread

_logger = logging.getLogger(__name__)

RECONNECT_MIN_INTERVAL = 2
RECONNECT_MAX_INTERVAL = 300


class LiveThreadInputSource(InputSourceThread):
    def __init__(self, thread_id):
        super().__init__()
        self._thread_id = thread_id
        self._reconnect_time = RECONNECT_MIN_INTERVAL

    def run(self):
        tornado.ioloop.IOLoop.current().run_sync(self._run)

    @tornado.gen.coroutine
    def _run(self):
        client = tornado.httpclient.AsyncHTTPClient()
        about_url = 'https://www.reddit.com/live/{}/about.json'.format(self._thread_id)

        while True:
            _logger.info('Get Live Thread info')
            response = yield client.fetch(about_url)

            if response.code != 200:
                _logger.error('Live thread info failed. %s %s', response.code,
                              response.reason)
                yield self._sleep_failure()
                continue

            try:
                doc = json.loads(response.body.decode('utf8', 'replace'))
            except ValueError:
                _logger.exception('Json parse error')
                yield self._sleep_failure()
                continue

            websocket_url = doc['data']['websocket_url'].replace('&amp;', '&')

            try:
                conn = yield tornado.websocket.websocket_connect(websocket_url)
            except tornado.websocket.WebSocketError:
                _logger.exception('Connect websocket error')
                yield self._sleep_failure()
                continue

            self._reconnect_time = RECONNECT_MIN_INTERVAL

            while True:
                msg = yield conn.read_message()

                if msg is None:
                    break

                doc = json.loads(msg)

                if doc['type'] == 'update':
                    post_doc = doc['payload']['data']
                    _logger.debug('Post: %s: %s', post_doc['author'], post_doc['body'])

                    self._calculator.add_live_thread_activity(post_doc)

            _logger.info('Websocket disconnected.')
            yield tornado.gen.sleep(self._reconnect_time)

    @tornado.gen.coroutine
    def _sleep_failure(self):
        self._reconnect_time *= 2
        self._reconnect_time = min(RECONNECT_MAX_INTERVAL, self._reconnect_time)

        yield tornado.gen.sleep(self._reconnect_time)
