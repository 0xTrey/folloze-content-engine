class ContentEngineError(Exception):
    pass


class CalendarExhaustedError(ContentEngineError):
    pass


class ValidationError(ContentEngineError):
    pass


class EmptyResponseError(ContentEngineError):
    pass


class RefusalError(ContentEngineError):
    pass


class ProviderUnavailableError(ContentEngineError):
    pass


class TemplateError(ContentEngineError):
    pass


class SchemaValidationError(ContentEngineError):
    pass


class RateLimitError(ContentEngineError):
    pass


class ArtifactWriteError(ContentEngineError):
    pass


class ArtifactSchemaError(ContentEngineError):
    pass


class PreviewValidationError(ContentEngineError):
    pass


class VerificationTimeoutError(ContentEngineError):
    pass


class ConfigError(ValueError):
    pass

