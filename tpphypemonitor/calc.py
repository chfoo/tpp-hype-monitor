import datetime
import queue
import threading
import collections
import logging
import os
import statistics
import time
import pickle

import math

from tpphypemonitor.text import text_graph, format_duration

_logger = logging.getLogger(__name__)


class DataPoint(object):
    __slots__ = (
        'line_count',
        'button_count',
        'hint_score',
        'timestamp',
    )

    def __init__(self, timestamp):
        self.timestamp = timestamp
        self.line_count = 0
        self.button_count = 0
        self.hint_score = 0


class DataSet(dict):
    def __init__(self, data=(), bin_size=60, max_len=100):
        super().__init__(data)
        self._bin_size = bin_size
        self._max_len = max_len

    @property
    def bin_size(self):
        return self._bin_size

    def _bump_data_point(self, timestamp=None):
        if not timestamp:
            timestamp = time.time()

        timestamp = timestamp // self._bin_size * self._bin_size

        if timestamp not in self:
            self[timestamp] = DataPoint(timestamp)

            while len(self) > self._max_len:
                key = tuple(self.iter_timestamp())[0]
                del self[key]
                break

        return timestamp

    def add_chat_data_point(self, is_button=False, timestamp=None):
        timestamp = self._bump_data_point(timestamp=timestamp)

        data_point = self[timestamp]
        data_point.line_count += 1

        if is_button:
            data_point.button_count += 1

    def add_hint_data_point(self, score=1.0, timestamp=None):
        timestamp = self._bump_data_point(timestamp=timestamp)

        data_point = self[timestamp]
        data_point.hint_score += score

    def iter_timestamp(self):
        yield from sorted(self)

    def iter_data_point(self, start_timestamp=float('-inf'),
                        end_timestamp=float('inf')):
        for timestamp in sorted(self):
            if start_timestamp <= timestamp <= end_timestamp:
                yield self[timestamp]

    def iter_rate(self, start_timestamp=float('-inf'),
                  end_timestamp=float('inf')):
        for data_point in self.iter_data_point(start_timestamp, end_timestamp):
            yield data_point.line_count / self._bin_size

    def iter_hint(self, start_timestamp=float('-inf'),
                  end_timestamp=float('inf')):
        for data_point in self.iter_data_point(start_timestamp, end_timestamp):
            yield data_point.hint_score / self._bin_size


class DataSets(object):
    def __init__(self, bin_sizes=(), max_time=14400):
        self._data_sets = {}

        for bin_size in bin_sizes:
            self._data_sets[bin_size] = DataSet((), bin_size, max_time // bin_size)

    @property
    def data_sets(self):
        return self._data_sets

    def add_chat_data_point(self, is_button=False, timestamp=None):
        for data_set in self._data_sets.values():
            data_set.add_chat_data_point(is_button, timestamp)

    def add_hint_data_point(self, score=1.0, timestamp=None):
        for data_set in self._data_sets.values():
            data_set.add_hint_data_point(score, timestamp)

    def has_data(self):
        return all(len(data_set) for data_set in self._data_sets.values())


class HypeEvent(object):
    def __init__(self):
        self.begin_time = None
        self.end_time = None
        self.begin_threshold = None
        self.end_threshold = None


AverageInfo = collections.namedtuple(
    'AverageInfo', ['short', 'medium', 'long', 'change'])
StdDevInfo = collections.namedtuple('StdDevInfo', ['short', 'medium', 'long'])

LIVE_INTERVAL = 10
SHORT_INTERVAL = 60
MEDIUM_INTERVAL = 300
LONG_INTERVAL = 900
BIN_SIZES = (LIVE_INTERVAL, SHORT_INTERVAL, MEDIUM_INTERVAL, LONG_INTERVAL)


class HypeCalculator(object):
    def __init__(self, button_input_parser, text_analyzer, pickle_path=None):
        self._button_input_parser = button_input_parser
        self._text_analyzer = text_analyzer
        self._pickle_path = pickle_path

        if pickle_path and os.path.exists(pickle_path):
            with open(pickle_path, 'rb') as file:
                doc = pickle.load(file)
                self._activity = doc['all_activity']
                self._hype_events = doc.get('hype_events', {})
                self._recent_hype_events = doc.get('recent_hype_events', [])
        else:
            self._activity = DataSets(BIN_SIZES)
            self._hype_events = {}
            self._recent_hype_events = []

        self._thread_lock = threading.Lock()
        self._input_queue = queue.Queue()
        self._last_timestamp = 0
        self._last_compute_timestamp = 0

    @property
    def last_timestamp(self):
        return self._last_timestamp

    @property
    def duration(self):
        if not self._last_timestamp:
            return 0

        return self._last_timestamp - self._text_analyzer.run_start_timestamp

    @property
    def recent_hype_events(self):
        with self._thread_lock:
            return tuple(self._recent_hype_events)

    def save_pickle(self):
        with self._thread_lock, open(self._pickle_path, 'wb') as file:
            pickle.dump(
                {
                    'all_activity': self._activity,
                    'hype_events': self._hype_events,
                },
                file)

    def add_chat_activity(self, nick, text, timestamp=None):
        self._input_queue.put(('chat', nick, text, timestamp))

    def add_live_thread_activity(self, doc, timestamp=None):
        self._input_queue.put(('live_thread', doc, timestamp))

    def process_forever(self):
        while True:
            item = self._input_queue.get()

            if item[0] == 'chat':
                self._process_chat_activity(item[1], item[2], item[3])
            else:
                self._process_thread_activity(item[1], item[2])

            if self._last_timestamp - self._last_compute_timestamp > SHORT_INTERVAL:
                self._compute_events()
                self._last_compute_timestamp = self._last_timestamp

    def _process_chat_activity(self, nick, text, timestamp=None):
        if not timestamp:
            timestamp = time.time()

        self._last_timestamp = timestamp

        with self._thread_lock:
            is_button = self._button_input_parser.parse_button(text)
            self._activity.add_chat_data_point(is_button=is_button, timestamp=timestamp)

            chat_hint = self._text_analyzer.analyze_chat(text)
            if chat_hint:
                if timestamp and timestamp >= self._text_analyzer.run_start_timestamp:
                    _logger.debug('Chat hint: %s [%s]', chat_hint.string, chat_hint.group(0))

                self._activity.add_hint_data_point(timestamp=timestamp)

    def _process_thread_activity(self, doc, timestamp=None):
        if not timestamp:
            timestamp = time.time()

        self._last_timestamp = timestamp

        with self._thread_lock:
            hint = self._text_analyzer.analyze_live_thread(doc)

            if hint:
                _logger.debug('Live hint: %s [%s]', hint.string, hint.group(0))
                _logger.info('Live hint: %s', hint.group(0))
                self._activity.add_hint_data_point(score=10.0, timestamp=timestamp)

    def compute_averages(self, series='rate', median=False, timestamp=None):
        data_set = self._activity.data_sets[LIVE_INTERVAL]

        if not timestamp:
            timestamp = self._last_timestamp

        with self._thread_lock:
            if series == 'rate':
                iter_func = data_set.iter_rate
            elif series == 'hint':
                iter_func = data_set.iter_hint
            else:
                raise ValueError('unknown series')

            values_short = tuple(
                iter_func(start_timestamp=timestamp - SHORT_INTERVAL,
                          end_timestamp=timestamp)
            ) or (0,)
            values_medium = tuple(
                iter_func(start_timestamp=timestamp - MEDIUM_INTERVAL,
                          end_timestamp=timestamp)
            ) or (0,)
            values_long = tuple(
                iter_func(start_timestamp=timestamp - LONG_INTERVAL,
                          end_timestamp=timestamp)
            ) or (0,)

        if median:
            stats_func = statistics.median
        else:
            stats_func = statistics.mean

        avg_short = stats_func(values_short)
        avg_medium = stats_func(values_medium)
        avg_long = stats_func(values_long)

        if avg_long != 0:
            avg_change = (avg_short - avg_long) / avg_long
        elif avg_short - avg_long > 0:
            avg_change = float('inf')
        elif avg_short - avg_long < 0:
            avg_change = float('-inf')
        else:
            avg_change = 0

        std_dev_short = statistics.pstdev(values_short)
        std_dev_medium = statistics.pstdev(values_medium)
        std_dev_long = statistics.pstdev(values_long)

        return (
            AverageInfo(avg_short, avg_medium, avg_long, avg_change),
            StdDevInfo(std_dev_short, std_dev_medium, std_dev_long)
        )

    def averages_string(self, series='rate', median=False):
        if not self._activity.has_data():
            return

        (avg_short, avg_medium, avg_long, change), \
        (std_dev_short, std_dev_medium, std_dev_long) = self.compute_averages(series, median=median)

        if math.isinf(change):
            if change > 0:
                change = 9.99
            else:
                change = -9.99

        avg_str = 'Median' if median else '  Mean'

        return (
            '{avg_str}: {avg_short:>#5.02f} {avg_medium:>#5.02f} {avg_long:>#5.02f} ({change:>+#4d}%) '
            'StdDev: {std_dev_short:.02f} {std_dev_medium:.02f} {std_dev_long:.02f} '
        ).format(
            avg_str=avg_str,
            avg_short=avg_short,
            avg_medium=avg_medium,
            avg_long=avg_long,
            std_dev_short=std_dev_short,
            std_dev_medium=std_dev_medium,
            std_dev_long=std_dev_long,
            change=int(change * 100),
        )

    def graph_string(self, series='rate'):
        if not self._activity.has_data():
            return

        data_sets = self._activity.data_sets

        with self._thread_lock:
            if series == 'rate':
                short_iterable = data_sets[SHORT_INTERVAL].iter_rate()
                medium_iterable = data_sets[MEDIUM_INTERVAL].iter_rate()
            elif series == 'hint':
                short_iterable = data_sets[SHORT_INTERVAL].iter_hint()
                medium_iterable = data_sets[MEDIUM_INTERVAL].iter_hint()
            else:
                raise ValueError('unknown series')

            data_list_short = tuple(short_iterable)[-60:]
            data_list_medium = tuple(medium_iterable)

        graph_short = text_graph(data_list_short)
        graph_medium = text_graph(data_list_medium)

        max_short = max(data_list_short)
        max_medium = max(data_list_medium)

        return '4h[{graph_medium}]{max_medium:>#4.01f} 1h[{graph_short}]{max_short:>#4.01f}'.format(
            graph_short=graph_short,
            graph_medium=graph_medium,
            max_short=max_short,
            max_medium=max_medium,
        )

    def _compute_events(self):
        for event_type in ('chat', 'hint'):
            if event_type == 'chat':
                average_info, std_dev_info = self.compute_averages(series='rate', median=True)
            else:
                average_info, std_dev_info = self.compute_averages(series='hint')

            hype_event = self._hype_events.get(event_type)

            if not hype_event and average_info.change >= 1.0:
                hype_event = HypeEvent()
                hype_event.begin_time = self._last_timestamp
                hype_event.begin_threshold = average_info.short
                hype_event.end_threshold = average_info.long

                if not self._hype_events:
                    self._event_begun(self._last_timestamp, event_type)

                self._hype_events[event_type] = hype_event

            elif hype_event and not hype_event.end_time and \
                    average_info.short < hype_event.end_threshold:
                hype_event.end_time = self._last_timestamp

                del self._hype_events[event_type]

                if not self._hype_events:
                    self._event_ended(self._last_timestamp, event_type)

    def _event_begun(self, begin_time, event_type):
        _logger.info(
            'Hype event (%s) begin: %s (%s)',
            event_type,
            datetime.datetime.utcfromtimestamp(begin_time),
            format_duration(begin_time - self._text_analyzer.run_start_timestamp)
        )

        with self._thread_lock:
            self._recent_hype_events.append(('begin', 'event_type', begin_time))

            while len(self._recent_hype_events) > 100:
                del self._recent_hype_events[0]

    def _event_ended(self, end_time, event_type):
        _logger.info(
            'Hype event (%s) end: %s (%s)',
            event_type,
            datetime.datetime.utcfromtimestamp(end_time),
            format_duration(end_time - self._text_analyzer.run_start_timestamp)
        )

        with self._thread_lock:
            self._recent_hype_events.append(('end', 'event_type', end_time))
