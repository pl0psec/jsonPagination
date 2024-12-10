"""
A module for fetching and paginating JSON data from APIs with support for multithreading,
customizable authentication, and the option to disable SSL verification for HTTP requests.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock, Semaphore
import time
from urllib.parse import urljoin
from datetime import datetime, timedelta
import math
from typing import Optional, Dict, Any, List, Callable

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

    def __init__(
        self,
        base_url: str,
        login_url: Optional[str] = None,
        auth_data: Optional[Dict[str, Any]] = None,
        current_page_field: Optional[str] = None,
        current_index_field: Optional[str] = None,
        items_field: str = 'per_page',
        total_count_field: str = 'total',
        items_per_page: Optional[int] = None,
        response_items_field: Optional[str] = None,
        max_threads: int = 5,
        download_one_page_only: bool = False,
        verify_ssl: bool = True,
        data_field: str = 'data',
        log_level: str = 'INFO',
        retry_delay: int = 30,
        ratelimit: Optional[tuple] = None,
        headers: Optional[Dict[str, str]] = None,
        proxies: Optional[Dict[str, Optional[str]]] = None,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initializes the Paginator with the given configuration.

        Args:
            base_url (str): The base URL for the API.
            login_url (str, optional): URL for authentication to retrieve a token.
            auth_data (dict, optional): Credentials required for the login endpoint.
            current_page_field (str, optional): Field name for the current page number in the API request.
            response_items_field (str, optional): Field name for the number of items returned per page in the API response.
            current_index_field (str, optional): Field name for the starting index in the API request.
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
            headers (dict, optional): Additional headers to include in the requests.
            logger (logging.Logger, optional): Custom logger instance. If not provided, the default logger is used.
        """

        # Validate pagination fields
        if current_page_field and current_index_field:
            raise ValueError('Only one of `current_page_field` or `current_index_field` should be provided.')

        if not current_page_field and not current_index_field:
            current_page_field = 'page'  # Default to 'page' if neither is provided

        # Setup logger with a console handler
        self.logger = logger or logging.getLogger(__name__)
        self.set_log_level(log_level)

        # URL and Authentication
        self.base_url = base_url
        # print(f"Base URL set to: {self.base_url}")
        self.login_url = login_url
        self.auth_data = auth_data
        self.token = None
        self.token_expiry: Optional[datetime] = None  # To cache token expiry

        # HTTP Configuration
        self.verify_ssl = verify_ssl
        self.request_timeout = 120  # Default timeout; can be customized
        self.headers = headers.copy() if headers else {}
        self.retry_lock = Lock()
        self.is_retrying = False
        self.proxies = proxies  # This will be None by default, allowing system proxies

        # Pagination Configuration
        self.pagination_field = current_page_field if current_page_field else current_index_field
        self.is_page_based = bool(current_page_field)
        self.items_field = items_field
        self.total_count_field = total_count_field
        self.data_field = data_field
        self.items_per_page = items_per_page  # Will be set dynamically if not provided
        self.response_items_field = response_items_field
        self.download_one_page_only = download_one_page_only

        # Threading Configuration
        self.max_threads = max_threads
        self.retry = 5  # Number of retries for failed requests
        self.retry_delay = retry_delay  # Initial retry delay in seconds

        # Rate Limiting Configuration
        self.ratelimit = ratelimit  # Tuple like (5, 60) for 5 calls per 60 seconds
        if self.ratelimit:
            self.calls, self.period = self.ratelimit
            self.rate_semaphore = Semaphore(self.calls)
            self.rate_period = self.period
            self.rate_reset_time = time.time() + self.rate_period
        else:
            self.rate_semaphore = None

        # Disable SSL warnings if SSL verification is disabled
        if not self.verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            self.logger.debug('SSL verification is disabled for all requests.')

    def set_log_level(self, log_level: str) -> None:
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

    def flatten_json(self, y: Any) -> Dict[str, Any]:
        """
        Flattens a nested JSON object into a single level dictionary with keys as paths to nested
        values.

        This method uses a generator to efficiently traverse the nested JSON object.

        Args:
            y (dict or list): The JSON object (or a part of it) to be flattened.

        Returns:
            dict: A single-level dictionary where each key represents a path through the original 
                  nested structure, and each value is the value at that path.

        Example:
            Given a nested JSON object like {"a": {"b": 1, "c": {"d": 2}}},
            the output will be {"a_b": 1, "a_c_d": 2}.
        """
        def flatten(x: Any, name: str = '') -> Dict[str, Any]:
            """Recursively flattens a nested structure of dictionaries and lists into a flat dictionary.
            
            Args:
                x (Any): The input structure to be flattened. Can be a dictionary, list, or any other type.
                name (str, optional): The base name for the current level of recursion. Defaults to ''.
            
            Returns:
                Dict[str, Any]: A flattened dictionary where keys are concatenated paths and values are the leaf nodes.
            
            Yields:
                Tuple[str, Any]: A tuple containing the flattened key and its corresponding value.
            """
            if isinstance(x, dict):
                for a in x:
                    yield from flatten(x[a], f'{name}{a}_')
            elif isinstance(x, list):
                for i, a in enumerate(x):
                    yield from flatten(a, f'{name}{i}_')
            else:
                yield (name[:-1], x)

        return dict(flatten(y))

    def login(self) -> None:
        """
        Authenticates the user and retrieves an authentication token. Implements token caching
        to avoid unnecessary logins.

        Raises:
            ValueError: If login_url or auth_data is not provided.
            LoginFailedException: If the login request fails with a non-200 status code.
        """
        if not self.login_url or not self.auth_data:
            self.logger.error('Login URL and auth data are required for login.')
            raise ValueError('Login URL and auth data must be provided for login.')

        # Check if token is still valid
        if self.token and self.token_expiry and datetime.now() < self.token_expiry:
            self.logger.debug('Using cached authentication token.')
            return  # Token is still valid

        login_url = urljoin(self.base_url, self.login_url)
        self.logger.debug('Logging in to %s', login_url)

        try:
            response = requests.post(
                login_url,
                json=self.auth_data,
                verify=self.verify_ssl,
                timeout=self.request_timeout,
                proxies=self.proxies
            )
            self.logger.debug('Login request to %s returned status code %d', login_url, response.status_code)

            if response.status_code == 200:
                json_response = response.json()
                self.token = json_response.get('token')
                if not self.token:
                    self.logger.error('Token not found in login response.')
                    raise LoginFailedException(response.status_code, 'Token not found in response.')

                self.headers['Authorization'] = f'Bearer {self.token}'

                # Assume the token expires in 'expires_in' seconds if provided
                expires_in = json_response.get('expires_in', 3600)  # Default to 1 hour
                self.token_expiry = datetime.now() + timedelta(seconds=expires_in)
                self.logger.info('Login successful. Token expires at %s.', self.token_expiry)

            else:
                self.logger.error('Login failed with status code %d: %s', response.status_code, response.text)
                raise LoginFailedException(response.status_code, response.text)

        except RequestException as e:
            self.logger.error('Network error during login: %s', e)
            raise LoginFailedException(0, str(e)) from e

    def ensure_authenticated(self) -> None:
        """
        Ensures that the user is authenticated by checking the token's validity and performing
        login if necessary.
        """
        if self.login_url and self.auth_data:
            if not self.token or (self.token_expiry and datetime.now() >= self.token_expiry):
                self.login()

    def enforce_ratelimit(self) -> None:
        """
        Enforces the rate limit by acquiring a semaphore or sleeping if necessary before making the next request.
        """
        if self.ratelimit:
            with self.retry_lock:
                current_time = time.time()
                if current_time >= self.rate_reset_time:
                    # Reset the semaphore and the reset time
                    self.rate_semaphore = Semaphore(self.calls)
                    self.rate_reset_time = current_time + self.rate_period
                    self.logger.debug('Rate limit reset.')

            acquired = self.rate_semaphore.acquire(timeout=self.rate_period)
            if not acquired:
                sleep_time = self.rate_reset_time - time.time()
                if sleep_time > 0:
                    self.logger.debug('Rate limit exceeded, sleeping for %.2f seconds', sleep_time)
                    time.sleep(sleep_time)
                # After sleeping, reset the semaphore
                with self.retry_lock:
                    self.rate_semaphore = Semaphore(self.calls)
                    self.rate_reset_time = time.time() + self.rate_period

    def make_request(
        self,
        session: requests.Session,
        method: str,
        url: str,
        params: Dict[str, Any],
        page: int
    ) -> requests.Response:
        """
        Makes an HTTP request using the provided session.

        Args:
            session (requests.Session): The session to use for making the request.
            method (str): The HTTP method (e.g., 'GET', 'POST').
            url (str): The URL for the request.
            params (dict): Query parameters for the request.
            page (int): The page number being requested (for logging purposes).

        Returns:
            requests.Response: The HTTP response received.

        Raises:
            RequestException: If an error occurs during the request.
        """
        self.enforce_ratelimit()

        full_url = urljoin(self.base_url, url)
        # print(f"Making {method} request to URL: {full_url} with params: {params}")

        try:
            response = session.request(method, full_url, params=params, proxies=self.proxies)
            self.logger.debug('Requesting URL: %s with status code: %d', response.url, response.status_code)
            return response
        except RequestException as e:
            self.logger.error('Network error during request to page %d: %s', page, e)
            raise

    def fetch_page(
        self,
        session: requests.Session,
        url: str,
        params: Dict[str, Any],
        page: int,
        results: List[Any],
        pbar: Optional[tqdm] = None,
        callback: Optional[Callable[[List[Any]], None]] = None
    ) -> None:
        """
        Fetches a single page of data from the API and updates the progress bar.

        Implements exponential backoff for retries.

        Args:
            session (requests.Session): The session to use for making requests.
            url (str): The API endpoint URL.
            params (dict): Additional parameters to pass in the request.
            page (int): The page number to fetch.
            results (list): The list to which fetched data will be appended.
            pbar (tqdm, optional): A tqdm progress bar instance to update with progress.
            callback (function, optional): A callback function to be invoked after each page is fetched.
        """
        retries = self.retry
        backoff_factor = 2  # Exponential backoff factor

        while retries > 0:
            try:
                response = self.make_request(session, 'GET', url, params, page)

                if response.status_code == 200:
                    data = response.json()
                    fetched_data = data.get(self.data_field, []) if self.data_field else data

                    with self.retry_lock:
                        results.extend(fetched_data)

                    if callback:
                        callback(fetched_data)

                    if pbar:
                        pbar.update(len(fetched_data))

                    return  # Success, exit the function

                elif response.status_code == 401:
                    self.logger.error('Authentication failed with status code %d: %s', response.status_code, response.text)
                    raise AuthenticationFailed(f"Authentication failed with status code {response.status_code}")

                elif response.status_code == 403:
                    if not self.login_url:
                        self.logger.warning('Access denied with status code 403, retrying after 10 seconds...')
                        time.sleep(10)
                        continue  # Retry after sleeping
                    else:
                        self.logger.error('Access denied with status code %d: %s', response.status_code, response.text)
                        raise AuthenticationFailed(f"Access denied with status code {response.status_code}")

                else:
                    self.logger.warning('Failed to fetch page %d with status code %d: %s', page, response.status_code, response.text)

            except RequestException as e:
                self.logger.error('Network error fetching page %d: %s', page, e)

            retries -= 1
            if retries > 0:
                backoff = self.retry_delay * (backoff_factor ** (self.retry - retries))
                self.logger.warning('Retrying page %d after %.2f seconds, remaining retries: %d', page, backoff, retries)
                time.sleep(backoff)
            else:
                self.logger.error('Failed to fetch page %d after multiple retries.', page)
                raise DataFetchFailedException(page, f'Failed to fetch page {page} after retries.')

    def _log_error_details(self, response: requests.Response) -> None:
        """
        Logs detailed error information from an HTTP response.

        Args:
            response (requests.Response): The HTTP response containing error details.
        """
        full_url = response.url
        self.logger.error('Failed to fetch data from %s', full_url)
        self.logger.error('HTTP status code: %d', response.status_code)
        self.logger.error('Response reason: %s', response.reason)
        self.logger.error('Response content: %s', response.text)
        self.logger.error('Request headers: %s', response.request.headers)

    def fetch_all_pages(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        flatten_json: bool = False,
        headers: Optional[Dict[str, str]] = None,
        callback: Optional[Callable[[List[Any]], None]] = None
    ) -> List[Any]:
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
            list: A list of JSON objects fetched from the API. If `flatten_json` is True, each item is a flattened dictionary.
        """
        if not params:
            params = {}
        
        # Ensure authentication before copying headers
        self.ensure_authenticated()  # Ensure authentication before making requests

        # Merge instance headers with method-specific headers, if any
        effective_headers = self.headers.copy()
        if headers:
            effective_headers.update(headers)

        # Initialize a session for connection pooling
        with requests.Session() as session:
            session.headers.update(effective_headers)
            session.verify = self.verify_ssl
            session.timeout = self.request_timeout

            # Initial request to get total_count
            try:
                initial_response = session.get(urljoin(self.base_url, url), params=params, proxies=self.proxies)
                self.logger.debug('Initial request to %s returned status code %d', initial_response.url, initial_response.status_code)

                if initial_response.status_code != 200:
                    self._log_error_details(initial_response)
                    raise DataFetchFailedException(initial_response.status_code, initial_response.url, initial_response.text)

                json_data = initial_response.json()
                
                if isinstance(json_data, dict):
                    data = json_data.get('data', [])
                    total_count = json_data.get(self.total_count_field, None)

                    if total_count is None:
                        self.logger.warning('Total count field "%s" missing, cannot paginate properly.', self.total_count_field)
                        return self.flatten_json(json_data) if flatten_json else json_data

                else:
                    # self.logger.error('Expected a dictionary but received a different type.')
                    return self.flatten_json(json_data) if flatten_json else json_data


                # Set items_per_page based on the initial API call if not set
                if not self.items_per_page:
                    if self.response_items_field and self.response_items_field in json_data:
                        self.items_per_page = json_data.get(self.response_items_field)
                    else:
                        self.items_per_page = json_data.get(self.items_field, 50)  # Default to 50

                if self.items_per_page == 0:
                    self.logger.warning('items_per_page is 0, returning an empty result.')
                    return []

                # Calculate total_pages based on total_count and items_per_page
                total_pages = 1 if self.download_one_page_only else math.ceil(total_count / self.items_per_page)
                self.logger.info('Total items to download: %d | Number of pages to fetch: %d', total_count, total_pages)

                results: List[Any] = []

                # Initialize progress bar
                with tqdm(total=total_count, desc='Downloading items') as pbar, ThreadPoolExecutor(max_workers=self.max_threads) as executor:
                    # Create a dictionary to map futures to page numbers
                    future_to_page = {
                        executor.submit(
                            self.fetch_page,
                            session,
                            url,
                            {
                                **params,
                                self.pagination_field: page if self.is_page_based else (page - 1) * self.items_per_page,
                                self.items_field: self.items_per_page
                            },
                            page,
                            results,
                            pbar,
                            callback
                        ): page for page in range(1, total_pages + 1)
                    }

                    for future in as_completed(future_to_page):
                        page = future_to_page[future]
                        try:
                            future.result()
                        except Exception as exc:
                            self.logger.error('Page %d generated an exception: %s', page, exc)
                            # Depending on requirements, you might choose to continue or raise
                            raise

                # Optionally flatten JSON if required
                if flatten_json:
                    results = [self.flatten_json(item) for item in results]

                return results

            except RequestException as e:
                self.logger.error('Network error during initial request: %s', e)
                raise DataFetchFailedException(0, url, str(e)) from e
