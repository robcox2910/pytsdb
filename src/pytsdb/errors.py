"""Custom exceptions for pytsdb.

Think of these like warning labels on a science kit -- they tell you
exactly what went wrong so you can fix it!
"""


class PyTSDBError(Exception):
    """Base exception for all pytsdb errors.

    Every error in pytsdb extends this class, so you can catch them all
    with a single ``except PyTSDBError``.
    """


class SeriesNotFoundError(PyTSDBError):
    """Raise when a requested time series does not exist.

    Like looking for a notebook in your desk that isn't there --
    you asked for a series name that hasn't been created yet.
    """


class DuplicateSeriesError(PyTSDBError):
    """Raise when trying to create a series that already exists.

    Like trying to label two notebooks with the same name --
    each series must have a unique name.
    """


class EmptySeriesError(PyTSDBError):
    """Raise when an operation requires data but the series is empty.

    Like trying to calculate the average temperature when you
    haven't taken any readings yet!
    """


class InvalidWindowError(PyTSDBError):
    """Raise when an aggregation window is invalid.

    Like trying to divide time into zero-second chunks --
    the window must be a positive duration.
    """


class InvalidRetentionError(PyTSDBError):
    """Raise when a retention period is invalid.

    Like saying "keep newspapers for zero days" --
    the retention period must be positive.
    """
