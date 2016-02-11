import re

elapsed_time_pattern = re.compile(r'\[?\s*(\d+)\s?d\s*(\d+)\s?h\s*(\d+)\s*m',
                                  re.IGNORECASE)

IMPORTANT_MARKER = '**'
IMPORTANT_LIVE_THREAD_PATTERNS = (
    r'\bcaught\b',
    r'\bnicknamed?\b',
    r'\bobtained\b',
    r'\b(released|we release)\b',
    r'\bdefeated\b',
    r'\blearn(s|ed)\b',
    r'\bdeposit(ed)?\b',
    r'\bpc\b.+(intens|shuff)',
    r'\b(tossed|we toss)\b',
    r'\bevolve[ds]\b',
    r'\b(taught|we teach)\b',
)
IMPORTANT_CHAT_PATTERNS = (
    r'\bPogChamp\b',
    r'\bwe did it\b',
    r'\bvictory riot\b',
    r'\bFailFish\b',
)


class TextAnalyzer(object):
    def __init__(self, run_start_timestamp):
        self._run_start_timestamp = run_start_timestamp

    @property
    def run_start_timestamp(self):
        return self._run_start_timestamp

    def analyze_live_thread(self, doc):
        timestamp = doc['created_utc']
        text = doc['body']

        elapsed_time_match = elapsed_time_pattern.match(text)

        if not elapsed_time_match:
            return

        elapsed_time = int(elapsed_time_match.group(1)) * 86400 + \
            int(elapsed_time_match.group(2)) * 3600 + \
            int(elapsed_time_match.group(3)) * 60

        abs_elapsed_time = elapsed_time + self._run_start_timestamp

        if abs(timestamp - abs_elapsed_time) > 60 * 5:
            # Discard updates that are not reflected at time of post
            return

        if IMPORTANT_MARKER not in text:
            return

        for pattern in IMPORTANT_LIVE_THREAD_PATTERNS:
            match = re.search(pattern, text)
            if match:
                return match

    def analyze_chat(self, text):
        for pattern in IMPORTANT_CHAT_PATTERNS:
            match = re.search(pattern, text)
            if match:
                return match
