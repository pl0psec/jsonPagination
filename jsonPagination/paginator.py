"""
A module for fetching and paginating JSON data from APIs with support for multithreading,
customizable authentication, and the option to disable SSL verification for HTTP requests.
"""

import logging
from queue import Queue
from threading import Thread, Lock
import time

import requests
from requests.exceptions import RequestException
import urllib3
from tqdm import tqdm
# from ratelimit import limits, sleep_and_retry


class LoginFailedException(Exception):
    """Exception raised when login fails."""

    def __init__(self, status_code, message="Login failed"):
        super().__init__(f"{message}. Status code: {status_code}")


class DataFetchFailedException(Exception):
    """Exception raised when fetching data fails."""

    def __init__(self, status_code, url, message="Failed to fetch data"):
        super().__init__(f"{message}. Status code: {status_code}, URL: {url}")


class AuthenticationFailed(Exception):
    """Exception raised when authentication fails."""

    def __init__(self, message="Authentication failed"):
        super().__init__(message)


def no_op_decorator(func):
    """A no-operation decorator that just returns the function unmodified."""
    return func


class Paginator:
    """
    A class for fetching and paginating JSON data from APIs with support for multithreading,
    customizable authentication, and the option to disable SSL verification for HTTP requests.
    """

    def __init__(self, login_url=None, auth_data=None, current_page_field='page',
                 start_index_field=None, per_page_field='per_page', total_count_field='total',
                 items_per_page=None, max_threads=5, download_one_page_only=False, verify_ssl=True,
                 data_field='data', log_level='INFO', retry_delay=30, api_rate_limit=None):
        """
        Initializes the Paginator with the given configuration.

        Args:
            login_url (str, optional): URL for authentication to retrieve a token.
            auth_data (dict, optional): Credentials required for the login endpoint.
            current_page_field (str, optional): Field name for the current page number in the API request.
            start_index_field (str, optional): Field name for the starting index in the API request (used for APIs that paginate by index rather than by page number).
            per_page_field (str, optional): Field name for the number of items per page in the API request.
            total_count_field (str, optional): Field name in the API response that holds the total number of items.
            per_page (int, optional): The number of items to request per page.
            max_threads (int, optional): Maximum number of threads to use for parallel requests.
            download_one_page_only (bool, optional): Whether to fetch only the first page of data.
            verify_ssl (bool, optional): Whether to verify SSL certificates for HTTP requests.
            data_field (str, optional): Field name from which to extract the data in the API response.
            log_level (str, optional): Logging level for the paginator.
            retry_delay (int, optional): Time in seconds to wait before retrying a failed request.
            api_rate_limit (tuple, optional): Rate limit settings as a tuple (calls, period) where 'calls' is the number of allowed calls in 'period' seconds.
        """

        # Setup logger with a console handler
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)  # Set logger to debug level

        # Ensure there is at least one handler
        if not self.logger.handlers:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.getLevelName(log_level))  # Set handler level
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)

        # Auth
        self.login_url = login_url
        self.auth_data = auth_data
        self.token = None

        # HTTP
        self.verify_ssl = verify_ssl

        # Pagination
        self.data_field = data_field
        self.current_page_field = current_page_field
        self.per_page_field = per_page_field
        self.total_count_field = total_count_field
        self.items_per_page = items_per_page
        self.download_one_page_only = download_one_page_only

        self.start_index_field = start_index_field

        # Threading
        self.max_threads = max_threads
        self.retry = 5
        self.retry_delay = retry_delay

        # Ratelimit
        self.api_rate_limit = api_rate_limit
        self.timeout = 60

        # Where to classify this ?
        self.headers = {}
        self.data_queue = Queue()
        self.retry_lock = Lock()
        self.is_retrying = False

        if not self.verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            self.logger.debug("SSL verification is disabled for all requests.")

    def flatten_json(self, y):
        """
        Flattens a nested JSON object into a single level dictionary with keys as paths to nested
        values.

        This method recursively traverses the nested JSON object, combining keys from different 
        levels into a single key separated by underscores. It handles both nested dictionaries
        and lists.

        Args:
            y (dict or list): The JSON object (or a part of it) to be flattened.

        Returns:
            dict: A single-level dictionary where each key represents a path through the original 
                 nested structure, and each value is the value at that path.

        Example:
            Given a nested JSON object like {"a": {"b": 1, "c": {"d": 2}}},
            the output will be {"a_b": 1, "a_c_d": 2}.
        """
        out = {}

        def flatten(x, name=''):
            if isinstance(x, dict):
                for a in x:
                    flatten(x[a], name + a + '_')
            elif isinstance(x, list):
                i = 0
                for a in x:
                    flatten(a, name + str(i) + '_')
                    i += 1
            else:
                out[name[:-1]] = x

        flatten(y)
        return out

    def set_log_level(self, log_level):
        """
        Sets the logging level for the Paginator instance.

        Args:
            log_level (str): The logging level to set. Valid options include 'DEBUG', 'INFO', 
                            'WARNING', 'ERROR', and 'CRITICAL'.
        """
        numeric_level = getattr(logging, log_level.upper(), None)
        if not isinstance(numeric_level, int):
            raise ValueError(f'Invalid log level: {log_level}')
        self.logger.setLevel(numeric_level)

    def login(self):
        """
        Authenticates the user and retrieves an authentication token. Does not retry on failure.

        Raises:
            Exception: If login fails due to incorrect credentials or other HTTP errors.
        """
        if not self.login_url or not self.auth_data:
            self.logger.error(
                "Login URL and auth data are required for login.")
            raise ValueError(
                "Login URL and auth data must be provided for login.")

        self.logger.debug("Logging in to %s", self.login_url)
        response = requests.post(self.login_url, json=self.auth_data, verify=self.verify_ssl, timeout=self.timeout)

        self.logger.debug("Login request to %s returned status code %d", self.login_url, response.status_code)

        if response.status_code == 200:
            self.token = response.json().get('token')
            self.headers['Authorization'] = f'Bearer {self.token}'
            self.logger.info("Login successful with status code %d.", response.status_code)

        else:
            self.logger.error("Login failed with status code %d.", response.status_code)
            raise LoginFailedException(response.status_code)

    # @sleep_and_retry
    # @limits(calls=2, period=60)
    def fetch_page(self, url, params, page, results, pbar=None):
        """
        Fetches a single page of data from the API and updates the progress bar.

        Args:
            url (str): The API endpoint URL.
            params (dict): Additional parameters to pass in the request.
            page (int): The page number to fetch.
            results (list): The list to which fetched data will be appended.
            pbar (tqdm, optional): A tqdm progress bar instance to update with progress.
        """
        def make_request():
            # Set the pagination parameters
            if self.start_index_field and self.per_page_field:
                params[self.per_page_field] = self.items_per_page
                params[self.start_index_field] = page * self.items_per_page

            # Construct the full URL for logging
            full_url = f"{url}?{requests.compat.urlencode(params)}"
            self.logger.debug("Requesting URL: %s", full_url)

            response = requests.get(url, headers=self.headers, params=params, timeout=self.timeout, verify=self.verify_ssl)
            if response.status_code == 200:
                data = response.json()
                fetched_data = data.get(self.data_field, []) if self.data_field else data
                with self.retry_lock:
                    results.extend(fetched_data)
                if pbar:
                    pbar.update(len(fetched_data))
                return True  # Successful fetch

            if response.status_code in [401, 403]:
                self.logger.error("Authentication failed with status code %d : %s", response.status_code, response.text)
                raise AuthenticationFailed(f"Authentication failed with status code {response.status_code}")

            return False  # Indicate that fetch was unsuccessful

        retries = self.retry
        while retries > 0:
            try:
                success = make_request()
                if success:
                    return

                retries -= 1
                self.logger.warning(f"Retrying page {page} after {self.retry_delay} seconds, remaining retries: {retries}")
                time.sleep(self.retry_delay)  # Wait before retrying
            except RequestException as e:
                self.logger.error(f"Network error fetching page {page}: {e}")
                retries -= 1
                time.sleep(self.retry_delay)  # Wait before retrying

    def fetch_all_pages(self, url, params=None, flatten_json=False):
        """
        Fetches all pages of data from a paginated API endpoint, optionally flattening the JSON
        structure of the results.

        This method handles authentication (if necessary), iterates over all pages of the endpoint,
        and can flatten the nested JSON structure of the returned data.

        Args:
            url (str): The URL of the API endpoint to fetch data from.
            params (dict, optional): Additional query parameters to include in the request.
            flatten_json (bool, optional): If set to True, the returned JSON structure will be
                                        flattened. Defaults to False.

        Returns:
            list or dict: A list of JSON objects fetched from the API if `flatten_json` is False.
                        If `flatten_json` is True, a single-level dictionary representing the
                        flattened JSON structure is returned.

        Raises:
            DataFetchFailedException: If the initial request to the API fails.
            ValueError: If required pagination fields are missing in the API response.

        Note:
            The method will automatically paginate through all available pages based on the
            response's pagination fields. If pagination fields are missing, it returns the raw
            response from the first request.
        """
        if not params:
            params = {}

        if self.login_url and not self.token and self.auth_data:
            self.login()

        response = requests.get(url, headers=self.headers, params=params, verify=self.verify_ssl, timeout=self.timeout)
        if response.status_code != 200:
            raise DataFetchFailedException(response.status_code, url)

        json_data = response.json()
        total_count = json_data.get(self.total_count_field)
        per_page = json_data.get(self.per_page_field)

        if total_count is None or per_page is None:
            self.logger.warning("Pagination fields missing, returning raw response")
            return self.flatten_json(json_data) if flatten_json else json_data

        self.items_per_page = params.get(self.per_page_field, self.items_per_page or per_page)
        print(f"total_count: {total_count} | self.per_page: {self.items_per_page}")
        total_pages = 1 if self.download_one_page_only else - \
            (-total_count // self.items_per_page)

        results = []
        with tqdm(total=total_count, desc="Downloading items") as pbar:
            threads = []
            for page in range(1, total_pages + 1):
                thread = Thread(target=self.fetch_page, args=(url, params.copy(), page, results, pbar))
                thread.start()
                threads.append(thread)

                if len(threads) >= self.max_threads:
                    for t in threads:
                        t.join()
                    threads = []

            for t in threads:
                t.join()

        while not self.data_queue.empty():
            results.extend(self.data_queue.get())

        return [self.flatten_json(item) if flatten_json else item for item in results]
