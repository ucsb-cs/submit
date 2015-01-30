"""Contains a list of Exceptions used in this project."""


class NudibranchException(Exception):

    """Superclass for all Nudibranch exceptions."""


class GroupWithException(NudibranchException):

    """Indicates there are too many users to join a group."""


class InvalidId(NudibranchException):

    """Indicates that the id to fetch doesn't exist."""
