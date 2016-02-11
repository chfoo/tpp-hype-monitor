import datetime

import tpphypemonitor.util
from tpphypemonitor.util import grouper


def text_graph(data_list, max_value=None):
    if not data_list:
        return ''

    chars = []

    max_value = max_value or max(data_list)

    for value_1, value_2 in grouper(data_list, 2, fillvalue=0):
        braille_1 = round(value_1 / max_value * 4) if max_value else 0
        braille_2 = round(value_2 / max_value * 4) if max_value else 0

        chars.append(tpphypemonitor.util.graph_barille_char(braille_1, braille_2))

    return ''.join(chars)


def format_duration(seconds):
    negative = seconds < 0
    seconds = int(abs(seconds))
    days, remain = divmod(seconds, 86400)
    hours, remain = divmod(remain, 3600)
    minutes, seconds = divmod(remain, 60)

    return '{negative}{days}d {hours:02d}h {minutes:02d}m'.format(
        negative='-' if negative else '',
        days=days, hours=hours, minutes=minutes)


def stats_doc(calculator):
    datetime_current = datetime.datetime.utcfromtimestamp(calculator.last_timestamp or 0)
    duration = format_duration(calculator.duration)

    return dict(
        date=datetime_current.isoformat(),
        duration=duration,
        averages=calculator.compute_averages(median=True),
        averages_str=calculator.averages_string(median=True),
        hint_averages_str=calculator.averages_string('hint'),
        chat_graph=calculator.graph_string(),
        hint_graph=calculator.graph_string('hint')
    )


def format_summary(calculator):
    return '{date} ({duration})\n' \
           'Lines/sec {averages_str}\n' \
           'Hints/sec {hint_averages_str}\n' \
           'Chat {chat_graph}\n' \
           'Hint {hint_graph}'\
        .format(**stats_doc(calculator))
