class AnneError(Exception):
    pass


class DuplicateSourceError(AnneError):
    pass


class BookNotFoundError(AnneError):
    pass


class ConfigError(AnneError):
    pass
