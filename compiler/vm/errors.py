from __future__ import annotations


class VMError(RuntimeError):
    pass


class ReturnSignal(Exception):
    def __init__(self, value):
        super().__init__()
        self.value = value


class RaisedSignal(Exception):
    def __init__(self, value, cause=None):
        super().__init__()
        self.value = value
        self.cause = cause
