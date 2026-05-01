class CM:
    def __enter__(self):
        return 1
    def __exit__(self, exc_type, exc, tb):
        pass
with CM() as a, CM() as b:
    print(a)
