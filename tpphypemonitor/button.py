import re

BUTTON_REGEX = r'((a|b|select|start|up|down|left|right)(\d|\+))+'


class ButtonInputParser(object):
    def __init__(self, allow_trailing=False):
        self._allow_trailing = allow_trailing

    def parse_button(self, text):
        parts = text.strip().split(None, 1)

        if len(parts) > 1 and not self._allow_trailing:
            return

        prev_span_start = 0
        buttons = []

        for match in re.finditer(BUTTON_REGEX, text):
            if match.span()[0] != prev_span_start:
                # Ensure continuously joined
                return

            buttons.append(match.groups())
            prev_span_start = match.span()[1]

        if not buttons:
            return

        if buttons[-1][1] == '+':
            # Combination cannot be incomplete
            return

        return buttons
