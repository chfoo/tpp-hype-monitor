import argparse
import json
import random
import time

import math

from tpphypemonitor.irc import IRCClient

SHORT_INTERVAL = 60 * 5
LONG_INTERVAL = 60 * 10


class StatsBot(IRCClient):
    def __init__(self, channel, stats_filename):
        super().__init__()
        self._channel = channel
        self._stats_filename = stats_filename

        next_time = math.ceil(time.time() / SHORT_INTERVAL) * SHORT_INTERVAL
        self.reactor.execute_at(next_time, self._sched_send_stats)

    def on_welcome(self, connection, event):
        self.connection.join(self._channel)

    def on_nicknameinuse(self, connection, event):
        connection.nick(connection.get_nickname() + str(random.randint(0, 9)))

    def _sched_send_stats(self):
        self._send_stats()
        next_time = int(math.ceil(time.time() / SHORT_INTERVAL) * SHORT_INTERVAL)
        self.reactor.execute_at(next_time, self._sched_send_stats)

    def _send_stats(self):
        time_now = time.time()
        time_rounded = int(time_now // SHORT_INTERVAL * SHORT_INTERVAL)

        with open(self._stats_filename) as file:
            doc = json.load(file)

        if abs(doc['utc_timestamp'] - time_now) > 120:
            return

        if doc['stats']['averages']:
            averages = doc['stats']['averages'][0]
            change = averages[3]

            if change < 1 and time_rounded % LONG_INTERVAL != 0:
                return
        else:
            return

        text = '[{duration}] Lines/sec {averages_str} · Hints/sec {hint_averages_str}'.format(
            duration=doc['stats']['duration'],
            averages_str=doc['stats']['averages_str'],
            hint_averages_str=doc['stats']['hint_averages_str'],
        )

        self.connection.privmsg(self._channel, text)

        text = 'Chat {chat_graph} · Hint {hint_graph}'.format(
            chat_graph=doc['stats']['chat_graph'],
            hint_graph=doc['stats']['hint_graph'],
        )

        self.connection.privmsg(self._channel, text)

if __name__ == '__main__':
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('server')
    arg_parser.add_argument('nick')
    arg_parser.add_argument('channel')
    arg_parser.add_argument('stats_filename')

    args = arg_parser.parse_args()

    client = StatsBot(args.channel, args.stats_filename)

    client.autoconnect(args.server, 6667, args.nick)

    client.reactor.process_forever()
