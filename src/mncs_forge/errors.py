"""Domain errors with stable machine-readable codes."""


class ForgeError(RuntimeError):
    """A bounded error safe to expose through the CLI or MCP."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def as_dict(self) -> dict[str, object]:
        return {"ok": False, "error": {"code": self.code, "message": self.message}}
