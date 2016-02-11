import json
import logging
import sched

import arrow
import time

from tpphypemonitor.source import InputSourceThread


_logger = logging.getLogger(__name__)


class ChatLogReader(object):
    def __init__(self, filenames, timestamp_start=None):
        super().__init__()
        self._filenames = list(sorted(filenames))
        self._current_file = None
        self._timestamp_start = timestamp_start

    def items(self):
        timestamp_start = self._timestamp_start

        while True:
            self._open_next_file()
            for line in self._current_file:
                line = line.strip()

                if not line or line.startswith('#'):
                    self._current_file = None
                    break

                datetime_str, command, rest = line.split(' ', 2)

                if command != 'privmsg':
                    continue

                arrow_date = arrow.get(datetime_str)
                timestamp = arrow_date.timestamp
                tags, nick, text = rest.split(' :', 2)

                if not timestamp_start:
                    timestamp_start = timestamp

                if timestamp < timestamp_start:
                    continue

                yield timestamp, nick, text

    def _open_next_file(self):
        if not self._filenames:
            raise ValueError('End of simulation')

        filename = self._filenames.pop(0)
        _logger.info('Open file %s', filename)
        self._current_file = open(filename, 'r')

    def stop(self):
        self._current_file.close()


class LiveThreadReader(object):
    def __init__(self, filename, timestamp_start=None):
        super().__init__()
        self._filename = filename
        self._timestamp_start = timestamp_start

    def items(self):
        timestamp_start = self._timestamp_start

        with open(self._filename) as file:
            for line in file:
                doc = json.loads(line)

                timestamp = doc['created_utc']

                if not timestamp_start:
                    timestamp_start = timestamp

                if timestamp < timestamp_start:
                    continue

                yield timestamp, doc


class SimulationInputSource(InputSourceThread):
    def __init__(self, chat_log_reader, live_thread_reader=None, time_scale=1.0):
        super().__init__()
        self._chat_log_reader = chat_log_reader
        self._live_thread_reader = live_thread_reader
        self._time_scale = time_scale

    def _iter_readers(self):
        if not self._live_thread_reader:
            for timestamp, nick, text in self._chat_log_reader.items():
                yield 'chat', timestamp, nick, text
        else:
            chat_iter = self._chat_log_reader.items()
            live_thread_iter = self._live_thread_reader.items()
            chat_timestamp = None
            live_thread_timestamp = None
            while True:
                if not chat_timestamp:
                    chat_timestamp, chat_nick, chat_text = next(chat_iter)
                if not live_thread_timestamp:
                    live_thread_timestamp, doc = next(live_thread_iter)

                if chat_timestamp < live_thread_timestamp:
                    yield 'chat', chat_timestamp, chat_nick, chat_text
                    chat_timestamp = None
                else:
                    yield 'live_thread', live_thread_timestamp, doc
                    live_thread_timestamp = None

    def run(self):
        scheduler = sched.scheduler()
        scheduler_timestamp_start = time.monotonic()
        timestamp_start = None

        for item in self._iter_readers():
            timestamp = item[1]

            if not timestamp_start:
                timestamp_start = timestamp

            next_timestamp = (timestamp - timestamp_start) * self._time_scale + scheduler_timestamp_start

            def func():
                item_type = item[0]

                if item_type == 'chat':
                    nick = item[2]
                    text = item[3]
                    self._calculator.add_chat_activity(nick, text, timestamp)
                else:
                    doc = item[2]
                    self._calculator.add_live_thread_activity(doc, timestamp)

            scheduler.enterabs(next_timestamp, 0, func)
            scheduler.run()
