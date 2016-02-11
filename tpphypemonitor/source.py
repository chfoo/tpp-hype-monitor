import threading


class InputSourceThread(threading.Thread):
    def __init__(self):
        super().__init__()
        self.daemon = True
        self._calculator = None

    def start_source(self, calculator):
        self._calculator = calculator
        self.start()
