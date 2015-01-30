"""Contains a list of Exceptions used in this project."""


class SubmitException(Exception):

    """Superclass for all Submit exceptions."""


class GroupWithException(SubmitException):

    """Indicates there are too many users to join a group."""


class InvalidId(SubmitException):

    """Indicates that the id to fetch doesn't exist."""
