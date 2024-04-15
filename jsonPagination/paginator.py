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

from .exceptions import LoginFailedException, DataFetchFailedException, AuthenticationFailed


class Paginator:
    """
    A class for fetching and paginating JSON data from APIs with support for multithreading,
    customizable authentication, and the option to disable SSL verification for HTTP requests.
    """

    def __init__(self, login_url=None, auth_data=None, current_page_field=None,
                 current_index_field=None, items_field='per_page', total_count_field='total',
                 items_per_page=None, response_items_field=None, max_threads=5, download_one_page_only=False, verify_ssl=True,
                 data_field='data', log_level='INFO', retry_delay=30, ratelimit=None, headers=None):
        """
        Initializes the Paginator with the given configuration.

        Args:
            login_url (str, optional): URL for authentication to retrieve a token.
            auth_data (dict, optional): Credentials required for the login endpoint.
            current_page_field (str, optional): Field name for the current page number in the API request.
            response_items_field (str, optional): Field name for the current page number in the API response.
            current_index_field (str, optional): Field name for the starting index in the API request (used for APIs that paginate by index rather than by page number).
            items_field (str, optional): Field name for the number of items per page in the API request.
            total_count_field (str, optional): Field name in the API response that holds the total number of items.
            items_per_page (int, optional): The number of items to request per page.
            max_threads (int, optional): Maximum number of threads to use for parallel requests.
            download_one_page_only (bool, optional): Whether to fetch only the first page of data.
            verify_ssl (bool, optional): Whether to verify SSL certificates for HTTP requests.
            data_field (str, optional): Field name from which to extract the data in the API response.
            log_level (str, optional): Logging level for the paginator.
            retry_delay (int, optional): Time in seconds to wait before retrying a failed request.
            ratelimit (tuple, optional): Rate limit settings as a tuple (calls, period) where 'calls' is the number of allowed calls in 'period' seconds.
        """

        if current_page_field and current_index_field:
            raise ValueError("Only one of `current_page_field` or `current_index_field` should be provided.")

        if not current_page_field and not current_index_field:
            current_page_field = 'page'  # Default to 'page' if neither is provided

        # self.items_per_page = items_per_page if items_per_page is not None else 10  # Ensure there's a default value for items_per_page

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
        self.request_timeout = 120

        self.headers = headers if headers is not None else {}

        # Pagination

        # Use `current_page_field` if provided, otherwise default to `current_index_field`        
        self.pagination_field = current_page_field if current_page_field else current_index_field
        self.is_page_based = bool(current_page_field)

        self.items_field = items_field
        self.total_count_field = total_count_field
        self.items_per_page = items_per_page or 10

        self.data_field = data_field

        self.items_per_page = items_per_page
        self.response_items_field = response_items_field or items_per_page
        self.download_one_page_only = download_one_page_only

        # Threading
        self.max_threads = max_threads
        self.retry = 5
        self.retry_delay = retry_delay

        # Ratelimit
        self.ratelimit = ratelimit  # should be a tuple like (5, 60) for 5 calls per 60 seconds
        self.last_request_time = None
        self.request_interval = 0 if not ratelimit else ratelimit[1] / ratelimit[0]

        # Where to classify this ?
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
        response = requests.post(self.login_url, json=self.auth_data, verify=self.verify_ssl, timeout=self.request_timeout)

        self.logger.debug("Login request to %s returned status code %d", self.login_url, response.status_code)

        if response.status_code == 200:
            self.token = response.json().get('token')
            self.headers['Authorization'] = f'Bearer {self.token}'
            self.logger.info("Login successful with status code %d.", response.status_code)

        else:
            self.logger.error("Login failed with status code %d.", response.status_code)
            raise LoginFailedException(response.status_code)

    def enforce_ratelimit(self):
        """
        Enforces the rate limit by sleeping if necessary before making the next request.
        """
        if self.ratelimit:
            current_time = time.time()
            if self.last_request_time and (current_time - self.last_request_time) < self.request_interval:
                sleep_time = self.request_interval - (current_time - self.last_request_time)
                self.logger.debug("Rate limiting in effect, sleeping for %.2f seconds", sleep_time)
                time.sleep(sleep_time)

            self.last_request_time = time.time()

    def fetch_page(self, url, params, page, results, pbar=None, callback=None):
        """
        Fetches a single page of data from the API and updates the progress bar.

        If a callback is provided, it is invoked after successfully fetching the page data.

        Args:
            url (str): The API endpoint URL.
            params (dict): Additional parameters to pass in the request.
            page (int): The page number to fetch.
            results (list): The list to which fetched data will be appended.
            pbar (tqdm, optional): A tqdm progress bar instance to update with progress.
            callback (function, optional): A callback function to be invoked after each page is fetched.
        """
        def make_request():
            # Rate limiting enforcement
            self.enforce_ratelimit()

            # Update the params with the appropriate pagination parameters
            if self.is_page_based:
                params[self.pagination_field] = page
            else:
                params[self.pagination_field] = (page - 1) * self.items_per_page

            params[self.items_field] = self.items_per_page

            self.logger.debug("Parameters for request: %s", params)

            # Construct the full URL for logging and request
            response = requests.get(url, headers=self.headers, params=params, timeout=self.request_timeout, verify=self.verify_ssl)
            self.logger.debug("Requesting URL: %s with status code: %d", response.request.url, response.status_code)

            if response.status_code == 200:
                data = response.json()
                fetched_data = data.get(self.data_field, []) if self.data_field else data

                with self.retry_lock:
                    results.extend(fetched_data)

                if callback:  # Invoke the callback function with the fetched data
                    callback(fetched_data, 'page_fetch')  # Or any other step identifier

                if pbar:
                    pbar.update(len(fetched_data))

                return True

            if response.status_code == 401:
                self.logger.error("Authentication failed with status code %d : %s", response.status_code, response.text)
                raise AuthenticationFailed(f"Authentication failed with status code {response.status_code}")

            if response.status_code == 403:
                if not self.login_url:  # No login URL defined, retry after sleeping
                    self.logger.warning("Access denied with status code 403, retrying after 10 seconds...")
                    time.sleep(10)  # Sleep and then retry the current request
                    self.last_request_time = time.time()  # Update the rate limit enforcement time
                    return False

                self.logger.error("Access denied with status code %d : %s", response.status_code, response.text)
                raise AuthenticationFailed(f"Access denied with status code {response.status_code}")

            return False  # Indicate that fetch was unsuccessful

        retries = self.retry
        while retries > 0:
            try:
                success = make_request()
                if success:
                    return

                retries -= 1
                self.logger.warning("Retrying page %d after %d seconds, remaining retries: %d", page, self.retry_delay, retries)
                time.sleep(self.retry_delay)  # Wait before retrying
            except RequestException as e:
                self.logger.error("Network error fetching page %d: %s", page, e)
                retries -= 1
                time.sleep(self.retry_delay)  # Wait before retrying

    def fetch_all_pages(self, url, params=None, flatten_json=False, headers=None, callback=None):
        """
        Fetches all pages of data from a paginated API endpoint, optionally flattening the JSON
        structure of the results. Invokes a callback function after each page if provided.

        Args:
            url (str): The URL of the API endpoint to fetch data from.
            params (dict, optional): Additional query parameters to include in the request.
            flatten_json (bool, optional): If set to True, the returned JSON structure will be
                                           flattened. Defaults to False.
            callback (function, optional): A callback function that is called after each page is fetched.

        Returns:
            list or dict: A list of JSON objects fetched from the API if `flatten_json` is False.
                          If `flatten_json` is True, a single-level dictionary representing the
                          flattened JSON structure is returned.
        """
        if not params:
            params = {}

        # Merge instance headers with method-specific headers, if any

        if self.login_url and not self.token and self.auth_data:
            self.login()

        effective_headers = self.headers.copy()
        if headers:
            effective_headers.update(headers)

        response = requests.get(url, headers=effective_headers, params=params, verify=self.verify_ssl, timeout=self.request_timeout)

        if response.status_code != 200:
            full_url = response.url  # This gives the full URL after the query parameters are applied

            # Log detailed error information
            self.logger.error("Failed to fetch data from %s", full_url)
            self.logger.error("HTTP status code: %d", response.status_code)
            self.logger.error("Response reason: %s", response.reason)
            self.logger.error("Response content: %s", response.text)
            self.logger.error("Request headers: %s", effective_headers)

            # Raise exception with detailed info
            raise DataFetchFailedException(response.status_code, full_url, response.text)

        json_data = response.json()
        total_count = json_data.get(self.total_count_field)
        if total_count is None:
            self.logger.warning("Total count field missing, cannot paginate properly.")
            return self.flatten_json(json_data) if flatten_json else json_data

        # Set items_per_page based on the initial API call if not set
        # if not self.items_per_page:
            # self.items_per_page = json_data.get(self.items_field, 200)  # Default to 200 if not specified

        # Set items_per_page based on the response, dynamically choosing the field or defaulting as necessary         
        if self.response_items_field and self.response_items_field in json_data:
            self.items_per_page = json_data.get(self.response_items_field)
        else:
            self.items_per_page = json_data.get(self.items_field, 200)

        # Determine pagination strategy
        if self.is_page_based:
            total_pages = 1 if self.download_one_page_only else max(-(-total_count // self.items_per_page), 1)
        else:  # Index-based pagination
            # Calculate how many sets of data (each of size 'items_per_page') are needed to cover 'total_count'
            total_pages = 1 if self.download_one_page_only else max(-(-total_count // self.items_per_page), 1)

        self.logger.info("Total items to download: %d | Number of pages to fetch: %d", total_count, total_pages)

        results = []
        with tqdm(total=total_count, desc="Downloading items") as pbar:
            threads = []
            for page in range(1, total_pages + 1):
                page_params = params.copy()

                # Existing pagination logic...

                thread = Thread(target=self.fetch_page, args=(url, page_params, page, results, pbar, callback))
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
