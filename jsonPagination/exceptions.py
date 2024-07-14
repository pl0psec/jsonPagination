"""
Defines custom exception classes for handling specific errors in the application.

This module contains definitions of exceptions that are raised when specific errors
occur during the operation of the application, particularly in areas such as login,
data fetching, and authentication.
"""

class LoginFailedException(Exception):
    """
    Exception raised when the login process fails.

    Attributes:
        status_code (int): HTTP status code returned from the login attempt.
        message (str): Explanation of the error. Defaults to 'Login failed'.
    """

    def __init__(self, status_code, message='Login failed'):
        """
        Initialize the exception with a status code and an optional custom message.

        Args:
            status_code (int): HTTP status code indicating the nature of the failure.
            message (str): Custom error message. Defaults to 'Login failed'.
        """
        super().__init__(f"{message}. Status code: {status_code}")


class DataFetchFailedException(Exception):
    """
    Exception raised when fetching data from the API fails.

    Attributes:
        status_code (int): HTTP status code returned from the data fetch attempt.
        url (str): The URL that was attempted to be accessed.
        message (str): Explanation of the error. Defaults to 'Failed to fetch data'.
    """

    def __init__(self, status_code, url, message='Failed to fetch data'):
        """
        Initialize the exception with a status code, URL, and an optional custom message.

        Args:
            status_code (int): HTTP status code indicating the nature of the failure.
            url (str): The URL that was attempted to be accessed.
            message (str): Custom error message. Defaults to 'Failed to fetch data'.
        """
        super().__init__(f"{message}. Status code: {status_code}, URL: {url}")


class AuthenticationFailed(Exception):
    """
    Exception raised when authentication with the API fails.

    Attributes:
        message (str): Explanation of the error. Defaults to 'Authentication failed'.
    """

    def __init__(self, message='Authentication failed'):
        """
        Initialize the exception with an optional custom message.

        Args:
            message (str): Custom error message. Defaults to 'Authentication failed'.
        """
        super().__init__(message)
