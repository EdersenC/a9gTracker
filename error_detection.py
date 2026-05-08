try:
    import time
except ImportError:  # pragma: no cover
    time = None


class ErrorCode:
    SETTINGS_INVALID = "SETTINGS_INVALID"
    NETWORK_STATUS_INVALID = "NETWORK_STATUS_INVALID"
    INSTRUCTION_INVALID = "INSTRUCTION_INVALID"
    CHUNK_INVALID = "CHUNK_INVALID"
    IO_FAILURE = "IO_FAILURE"
    NETWORK_FAILURE = "NETWORK_FAILURE"


class DetectedError(Exception):
    def __init__(self, code, message, context=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.context = context or {}

    def to_dict(self):
        return {
            "code": self.code,
            "message": self.message,
            "context": self.context,
        }


class ErrorDetector:
    def __init__(self):
        self.events = []

    def _timestamp(self):
        if time is None:
            return 0
        return time.time()

    def report(self, severity, code, message, context=None):
        event = {
            "severity": severity,
            "code": code,
            "message": message,
            "context": context or {},
            "timestamp": self._timestamp(),
        }
        self.events.append(event)
        return event

    def info(self, code, message, context=None):
        return self.report("info", code, message, context)

    def warn(self, code, message, context=None):
        return self.report("warn", code, message, context)

    def error(self, code, message, context=None):
        return self.report("error", code, message, context)

    def has_errors(self):
        for event in self.events:
            if event["severity"] == "error":
                return True
        return False


def validate_settings(settings):
    if not isinstance(settings, dict):
        raise DetectedError(ErrorCode.SETTINGS_INVALID, "Settings must be a dict")

    required_top = ("provider", "server", "modes")
    for key in required_top:
        if key not in settings:
            raise DetectedError(
                ErrorCode.SETTINGS_INVALID,
                "Missing required setting key",
                {"missing": key},
            )

    server = settings["server"]
    if not isinstance(server, dict):
        raise DetectedError(
            ErrorCode.SETTINGS_INVALID,
            "server must be a dict",
        )

    for key in ("host", "port", "auth", "routes"):
        if key not in server:
            raise DetectedError(
                ErrorCode.SETTINGS_INVALID,
                "Missing required server key",
                {"missing": key},
            )

    routes = server["routes"]
    if not isinstance(routes, dict):
        raise DetectedError(
            ErrorCode.SETTINGS_INVALID,
            "routes must be a dict",
        )
    for key in ("location", "update"):
        if key not in routes:
            raise DetectedError(
                ErrorCode.SETTINGS_INVALID,
                "Missing required route",
                {"missing": key},
            )
    return True


def validate_network_snapshot(snapshot):
    required = ("scan", "imei", "iccid", "quaility", "registered", "status")
    if not isinstance(snapshot, dict):
        raise DetectedError(
            ErrorCode.NETWORK_STATUS_INVALID, "Network snapshot must be a dict"
        )
    for key in required:
        if key not in snapshot:
            raise DetectedError(
                ErrorCode.NETWORK_STATUS_INVALID,
                "Missing network field",
                {"missing": key},
            )
    return True


def validate_instruction(instruction):
    if not isinstance(instruction, dict):
        raise DetectedError(
            ErrorCode.INSTRUCTION_INVALID, "Instruction must be a dict"
        )
    if "action" not in instruction:
        raise DetectedError(
            ErrorCode.INSTRUCTION_INVALID, "Instruction missing action"
        )
    action = instruction["action"]
    if action not in ("update", "updateState", "Fault", "Idle", "reboot", "print"):
        raise DetectedError(
            ErrorCode.INSTRUCTION_INVALID,
            "Unsupported action",
            {"action": action},
        )
    if action == "update" and "data" not in instruction:
        raise DetectedError(
            ErrorCode.INSTRUCTION_INVALID, "Update instruction missing data"
        )
    return True


def validate_chunk_state(file_size, amount_written, chunk):
    if file_size < 0 or amount_written < 0:
        raise DetectedError(
            ErrorCode.CHUNK_INVALID,
            "File size and amount written must be non-negative",
        )
    if amount_written > file_size and file_size != 0:
        raise DetectedError(
            ErrorCode.CHUNK_INVALID,
            "Amount written cannot exceed file size",
            {"fileSize": file_size, "amountWritten": amount_written},
        )
    if chunk is None:
        raise DetectedError(ErrorCode.CHUNK_INVALID, "Chunk cannot be None")
    return True
