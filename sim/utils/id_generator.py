# sim/utils/id_generator.py
class IdGen:
    def __init__(self, prefix: str = "id"):
        self.prefix = prefix
        self.cnt = 0

    def next(self) -> str:
        self.cnt += 1
        return f"{self.prefix}-{self.cnt}"
