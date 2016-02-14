tpp-hype-monitor
================

TwitchPlaysPokemon chat activity/hype monitor.

The stats produced are informal and are somewhat naive.

Example output:

        Lines/sec Median:  3.95  2.90  2.75 ( +43%) StdDev: 1.44 1.33 1.26 
        Hints/sec   Mean:  0.85  0.24  0.25 (+246%) StdDev: 0.90 0.52 0.54 
        Chat 4h[⣤⣤⣴⣤⣤⣤⣦⣤⣤⣄⣤⣤⣤⣤⣤⣤⣤⣤⣤⣴⣴⣷⣿⣷] 2.9 1h[⣤⣤⣄⣤⣠⣄⣠⣤⣠⣤⣤⣠⣤⣄⣦⣴⣾⣦⣤⣤⣤⣴⣶⣤⣼⣾⣶⣦⣾⣾] 4.0
        Hint 4h[⣀⣀⣀⠀⠀⠀⣀⠀⠀⠀⠀⡀⠀⠀⡀⢀⠀⢀⡀⠀⢀⡀⣸⣠] 0.4 1h[⢀⡀⠀⠀⠀⡀⠀⠀⠀⠀⠀⠀⠀⠀⢀⡀⣀⠀⡀⠀⠀⠀⡀⢀⣸⢰⠀⡀⡀⢸] 0.9

The first line shows messages per second for 1 minute, 5 minutes, and 15 minutes. The percentage shows the difference for 1 minute and 15 minutes. The standard deviation is also printed. The second line shows "hints" which selected keywords such as "PogChamp" and "FailFish". If a Reddit Live Thread is used, selected keywords such as "released" and "nicknamed" are used.

The third and fourth line shows a graph in Unicode braille. A font that supports showing these characters is [DejaVu](http://dejavu-fonts.org/). The first graph shows activity over 4 hours and the second graph shows activity over 1 hour.


Quick start
-----------

Requires:

* Python 3.4+

Python packages:

* irc
* arrow

Example usage:

        python3 tpphypemonitor --run-date "2016-01-01 10:00:00+00:00" --stats-output-file my_data_for_analysis.json irc --pickle program_state.pickle  --live-thread-id liveUpdaterIdAbc123

The above will collect stats for the TwitchPlaysPokemon chat, use a (fictional) Reddit Live Thread for hype hints, and write it out to a JSON for post processing.

Example IRC bot that prints out stats every 10 minutes:

        python3 tpphypemonitor.bot.stats tpp_bot_stats_config.json

Running simulation:

        python3 -m tpphypemonitor--run-date 2015-12-12T21:00:00 simulate 2015-12-*.log --live-thread-log xd_live_updates.txt --start-date 2015-12-12T20:00:00 --time-scale 0.01

The logs should be in [Spaghetti Logger](https://github.com/chfoo/spaghetti-logger) format. The Reddit Live Thread should contain on each line the `data` object for each `LiveUpdate` kind. (You can get past Live Updates using [this script](https://gist.github.com/chfoo/3806f2aef3a8b9dc0657).)


