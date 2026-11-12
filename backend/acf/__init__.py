"""AI Chatbot Framework: a lean, self-hosted agent with a sandbox per user."""

from importlib.metadata import PackageNotFoundError, version

from packaging.version import Version


def semver(pep440: str) -> str:
    """The release tag's form of a Python version: 2.0.0b1 -> 2.0.0-beta.1."""
    v = Version(pep440)
    base = ".".join(map(str, (v.release + (0, 0))[:3]))
    if not v.pre:
        return base
    kind, n = v.pre
    return f"{base}-{'beta' if kind == 'b' else kind}.{n}"


try:
    __version__ = semver(version("ai-chatbot-framework"))
except PackageNotFoundError:  # running from a source tree that isn't installed
    __version__ = "0.0.0"
