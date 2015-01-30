class HandledError(Exception):

    """Indicate that the system state is invalid."""


class OutOfSync(Exception):

    """Indicate the worker is out of sync."""


class SSHConnectTimeout(Exception):

    """Indicate that the SSH session timed out while creating a connection."""
