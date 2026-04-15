from app.core.logging import get_logger


class Logger:
    @staticmethod
    def get_logger(name: str = "app"):
        return get_logger(name)


logger = Logger.get_logger()
