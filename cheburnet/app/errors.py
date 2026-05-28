from __future__ import annotations


class CheburNetError(RuntimeError):
    """Base user-facing application error."""


class AdminRequiredError(CheburNetError):
    pass


class ToolInstallError(CheburNetError):
    pass


class ConfigBuildError(CheburNetError):
    pass


class ProfileImportError(CheburNetError):
    pass
