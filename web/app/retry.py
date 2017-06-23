from collections import Callable
import functools
import logging
import sys
from time import sleep


class Retry(object):
    """
        A retrying decorator/context-manager that traps any of the configured exceptions thrown by
        the decorated function or method.

        The number of retries (default: 3) and the sequence of exceptions (default: (Exception,))
        can be specialized.  The sequence of sleep delays can also be specialized.

        The decorator/context-manager takes initializing arguments, and therefore must be used with
        'function call' syntax - @Retry(), not @Retry.

        Usage example (decorator):
        C{
            class AClass(object):

                @Retry()
                def method_1(self):
                    ...
                    ...

                @Retry(retries=5, exceptions=(SysCallError, IOError,), sleep_seconds=(1,5,15,30,))
                def method_2(self):
                    ...
                    ...
        }

        Usage example (context-manager):
        C{
            class AClass(object):

                def method_1(self, string_param):
                    ...
                    ...

            with Retry(retries=10, exceptions=(IOError,), sleep_seconds=(1,)) as retry:
                retry.execute(AClass().method_1, "hi, there")
        }
    """

    DEFAULT_SLEEP_SECONDS = (0.5, 1, 1.5, 2.5, 4, 6.5, 10.5, 17, 27.5, 34.5)
    """
        Default sequence of sleep durations (in seconds).
    """

    def __init__(self,
                 retries=3,
                 exceptions=(Exception,),
                 sleep_seconds=DEFAULT_SLEEP_SECONDS,
                 debug=False):
        """
            Parameterize with retries, exceptions, sleep_seconds, or all.  Enable debug logging of
            the called function and its arguments with debug.

            @param retries: how many times to retry the method, if the method raises
            one of the given exceptions.
            @type retries: int
            @param exceptions: a tuple of exceptions that should be caught if raised by the method,
            and retried.
            @type exceptions: tuple
            @param sleep_seconds: a sequence of values indicating how much time (in seconds) to
            delay between retries.
            @type sleep_seconds: tuple
            @param debug: enable (True)/disable (False) debug logging of method call and its args
            @type debug: bool

            @precondition: retries > 0
            @precondition: len(exceptions) > 0
            @precondition: (
                all(issubclass(x, Exception) for x in exceptions)
            )
            @precondition: len(sleep_seconds) > 0
            @precondition: (
                all(isinstance(x, (int, float)) for x in sleep_seconds)
            )
            @precondition: (
                all(x > 0. for x in sleep_seconds)
            )
        """
        assert isinstance(retries, int), type(retries)
        assert isinstance(exceptions, tuple), type(exceptions)
        assert isinstance(sleep_seconds, tuple), type(sleep_seconds)
        assert isinstance(debug, bool), type(debug)
        assert exceptions
        assert all(issubclass(x, Exception) for x in exceptions), exceptions
        assert sleep_seconds
        assert all(isinstance(x, (int, float)) for x in sleep_seconds), sleep_seconds
        assert all(x > 0. for x in sleep_seconds), sleep_seconds

        self.__retries = retries
        self.__exceptions = exceptions
        self.__sleep_seconds = sleep_seconds
        self.__debug = debug

    def __call__(self, func):
        @functools.wraps(func)
        def retry_func(*args, **kwargs):
            return self.execute(func, *args, **kwargs)
        return retry_func

    # add __enter__/__exit__ methods for context manager utility
    def __enter__(self):
        return self

    def __exit__(self, *exception_args):
        return False

    def execute(self, func, *args, **kwargs):
        """
            Execute the given function with the given arguments (if any) and/or keyword arguments
            (if any).  The function is retried according to the parameters given to the class
            initializer.

            @param func: a function or method
            @type func: collections.Callable
            @param args: tuple of arguments passed directly to method
            @param kwargs: keyword arguments passed directly to method
        """
        assert isinstance(func, Callable), type(func)

        for i in range(self.__retries):
            try:
                if self.__debug:
                    Retry.__LOGGER.debug(
                        '{}({},{})'.format(func.__name__, args, kwargs)
                    )
                return func(*args, **kwargs)
            except self.__exceptions:
                exc_info = sys.exc_info()
                if i < self.__retries - 1:
                    seconds = self.__sleep_seconds[min(i, len(self.__sleep_seconds) - 1)]
                    Retry.__LOGGER.warning(
                        "Retrying in %ss, after exception %s",
                        seconds,
                        exc_info[:2]
                    )
                    sleep(seconds)
                else:
                    raise exc_info[0](exc_info[1]).with_traceback(exc_info[2])

    __LOGGER = logging.getLogger(__name__)

    __slots__ = (
        '__exceptions',
        '__retries',
        '__sleep_seconds',
        '__debug',
    )
