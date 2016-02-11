import enum
from itertools import zip_longest


class Dots(enum.IntEnum):
    dot_1 = 1
    dot_2 = 1 << 1
    dot_3 = 1 << 2
    dot_4 = 1 << 3
    dot_5 = 1 << 4
    dot_6 = 1 << 5
    dot_7 = 1 << 6
    dot_8 = 1 << 7


LEFT_DOTS = (Dots.dot_7, Dots.dot_3, Dots.dot_2, Dots.dot_1)
RIGHT_DOTS = (Dots.dot_8, Dots.dot_6, Dots.dot_5, Dots.dot_4)


def graph_barille_char(left=0, right=0):
    assert 0 <= left <= 4, left
    assert 0 <= right <= 4, right
    value = 0

    for left_index in range(left):
        value |= LEFT_DOTS[left_index].value

    for right_index in range(right):
        value |= RIGHT_DOTS[right_index].value

    # https://en.wikipedia.org/wiki/Braille_Patterns
    return chr(value | 0x2800)


def grouper(iterable, n, fillvalue=None):
    "Collect data into fixed-length chunks or blocks"
    # grouper('ABCDEFG', 3, 'x') --> ABC DEF Gxx"
    # Copied from itertools Recipes
    args = [iter(iterable)] * n
    return zip_longest(*args, fillvalue=fillvalue)
