import argparse
import json
import logging
import os
import sched
import threading
import time
import atexit

import arrow

from tpphypemonitor.button import ButtonInputParser
from tpphypemonitor.calc import HypeCalculator
from tpphypemonitor.chat import TwitchInputSource
from tpphypemonitor.heuristics import TextAnalyzer
from tpphypemonitor.reddit import LiveThreadInputSource
from tpphypemonitor.simulation import ChatLogReader, LiveThreadReader, \
    SimulationInputSource
from tpphypemonitor.text import format_summary, stats_doc

_logger = logging.getLogger(__name__)


def main():
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('--server', default='irc.twitch.tv')

    subparsers = arg_parser.add_subparsers(dest='command')
    subparsers.required = True

    irc_parser = subparsers.add_parser('irc')
    irc_parser.add_argument('--channel', default='#twitchplayspokemon')
    irc_parser.add_argument('--pickle')
    irc_parser.add_argument('--live-thread-id')

    simulate_parser = subparsers.add_parser('simulate')
    simulate_parser.add_argument('chat_log', nargs='+')
    simulate_parser.add_argument('--live-thread-log')
    simulate_parser.add_argument('--start-date')
    simulate_parser.add_argument('--time-scale', type=float, default=1.0)

    arg_parser.add_argument('--run-date')
    arg_parser.add_argument('--print-summary-interval', default=60, type=int)
    arg_parser.add_argument('--stats-output-filename')
    arg_parser.add_argument('--debug', action='store_const',
                            dest='log_level',
                            default=logging.INFO, const=logging.DEBUG)

    args = arg_parser.parse_args()
    logging.basicConfig(level=args.log_level)

    pickle_path = args.pickle if args.command == 'irc' else None

    scheduler = sched.scheduler()
    button_input_parser = ButtonInputParser()
    text_analyzer = TextAnalyzer(arrow.get(args.run_date or time.time()).timestamp)
    calculator = HypeCalculator(button_input_parser, text_analyzer,
                                pickle_path=pickle_path)

    if args.command == 'irc':
        input_source = TwitchInputSource(args.server, args.channel)

        if args.live_thread_id:
            reddit_input_source = LiveThreadInputSource(args.live_thread_id)
        else:
            reddit_input_source = None
    else:
        timestamp_start = None
        reddit_input_source = None

        if args.start_date:
            timestamp_start = arrow.get(args.start_date).timestamp

        chat_log_reader = ChatLogReader(
            args.chat_log, timestamp_start=timestamp_start)

        if args.live_thread_log:
            live_thread_reader = LiveThreadReader(
                args.live_thread_log, timestamp_start=timestamp_start)
        else:
            live_thread_reader = None

        input_source = SimulationInputSource(
            chat_log_reader, live_thread_reader, time_scale=args.time_scale)

    if pickle_path:
        def save_pickle():
            calculator.save_pickle()
            scheduler.enter(60, 0, save_pickle)

        save_pickle()

    @atexit.register
    def cleanup():
        if pickle_path:
            calculator.save_pickle()

    def print_stats():
        _logger.info('Summary - ' + format_summary(calculator))
        delay = args.print_summary_interval

        if args.command == 'simulate':
            delay *= args.time_scale
            delay = max(1, delay)

        scheduler.enter(delay, 0, print_stats)

    def write_output():
        doc = {
            'utc_timestamp': time.time(),
            'stats': stats_doc(calculator),
            'recent_hype_events': calculator.recent_hype_events,
        }

        new_filename = args.stats_output_filename + '-new'
        with open(new_filename, 'w') as file:
            json.dump(doc, file)

        os.rename(new_filename, args.stats_output_filename)
        scheduler.enter(60, 0, write_output)

    if args.stats_output_filename:
        write_output()

    if args.print_summary_interval:
        print_stats()

    input_source.start_source(calculator)

    if reddit_input_source:
        reddit_input_source.start_source(calculator)

    process_thread = threading.Thread(target=calculator.process_forever)
    process_thread.daemon = True
    process_thread.start()

    def check_threads():
        if not process_thread.is_alive():
            raise Exception('Process thread died')
        if not input_source.is_alive():
            raise Exception('Input thread died')
        if reddit_input_source and not reddit_input_source.is_alive():
            raise Exception('Reddit input thread died')
        scheduler.enter(5, 0, check_threads)

    check_threads()

    while True:
        scheduler.run()

    _logger.info('Done')

if __name__ == '__main__':
    main()
