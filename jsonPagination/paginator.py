"""
A module for fetching and paginating JSON data from APIs with support for multithreading,
customizable authentication, and the option to disable SSL verification for HTTP requests.
"""

import logging
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import time
from urllib.parse import urljoin
from datetime import datetime, timedelta
import math
from typing import Any, Callable

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
        login_url: str | None = None,
        auth_data: dict[str, Any] | None = None,
        current_page_field: str | None = None,
        current_index_field: str | None = None,
        items_field: str = 'per_page',
        total_count_field: str = 'total',
        items_per_page: int | None = None,
        response_items_field: str | None = None,
        max_threads: int = 5,
        download_one_page_only: bool = False,
        verify_ssl: bool = True,
        data_field: str = 'data',
        log_level: str = 'INFO',
        retry_delay: int = 30,
        max_backoff: int = 300,
        ratelimit: tuple | None = None,
        headers: dict[str, str] | None = None,
        proxies: dict[str, str | None] | None = None,
        logger: logging.Logger | None = None,
        token_field: str = 'token',
        paginate_until_empty: bool = False,
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
            max_backoff (int, optional): Maximum backoff time in seconds for retries. Defaults to 300.
            ratelimit (tuple, optional): Rate limit settings as a tuple (calls, period) where 'calls' is the number of allowed calls in 'period' seconds.
            headers (dict, optional): Additional headers to include in the requests.
            proxies (dict, optional): Proxy configuration for requests.
            logger (logging.Logger, optional): Custom logger instance. If not provided, the default logger is used.
            token_field (str, optional): Field name for the token in the login response. Defaults to 'token'.
            paginate_until_empty (bool, optional): If True, fetches pages sequentially until the data
                field returns an empty list, instead of relying on total_count. Defaults to False.
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
        self.login_url = login_url
        self.auth_data = auth_data
        self.token = None
        self.token_expiry: datetime | None = None  # To cache token expiry
        self.token_field = token_field

        # HTTP Configuration
        self.verify_ssl = verify_ssl
        self.request_timeout = 120  # Default timeout; can be customized
        self.headers = headers.copy() if headers else {}
        self.proxies = proxies  # This will be None by default, allowing system proxies

        # Locks
        self.retry_lock = Lock()
        self._results_lock = Lock()
        self._rate_lock = Lock()
        self.is_retrying = False

        # Pagination Configuration
        self.pagination_field = current_page_field if current_page_field else current_index_field
        self.is_page_based = bool(current_page_field)
        self.items_field = items_field
        self.total_count_field = total_count_field
        self.data_field = data_field
        self.items_per_page = items_per_page  # Will be set dynamically if not provided
        self.response_items_field = response_items_field
        self.download_one_page_only = download_one_page_only
        self.paginate_until_empty = paginate_until_empty

        # Threading Configuration
        self.max_threads = max_threads
        self.retry = 5  # Number of retries for failed requests
        self.retry_delay = retry_delay  # Initial retry delay in seconds
        self.max_backoff = max_backoff

        # Rate Limiting Configuration (sliding window)
        self.ratelimit = ratelimit  # Tuple like (5, 60) for 5 calls per 60 seconds
        if self.ratelimit:
            self.calls, self.period = self.ratelimit
            self._rate_timestamps: list[float] = []

        # Warn about disabled SSL verification without global side effects
        if not self.verify_ssl:
            warnings.filterwarnings('ignore', category=urllib3.exceptions.InsecureRequestWarning)
            self.logger.warning(
                'SSL verification is disabled. InsecureRequestWarning suppressed process-wide.'
            )

    def _build_url(self, path: str) -> str:
        """Joins base_url and path without dropping the base path component."""
        base = self.base_url.rstrip('/') + '/'
        return urljoin(base, path.lstrip('/'))

    def _sanitize_headers(self, headers: dict) -> dict:
        """Returns a copy of headers with sensitive values redacted."""
        sanitized = dict(headers)
        for key in sanitized:
            if key.lower() in ('authorization', 'cookie', 'x-api-key'):
                sanitized[key] = '***REDACTED***'
        return sanitized

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

    def flatten_json(self, y: Any) -> dict[str, Any]:
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
        def flatten(x: Any, name: str = '') -> dict[str, Any]:
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

        login_url = self._build_url(self.login_url)
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
                self.token = json_response.get(self.token_field)
                if not self.token:
                    self.logger.error('Token field "%s" not found in login response.', self.token_field)
                    raise LoginFailedException(response.status_code, f'Token field "{self.token_field}" not found in response.')

                self.headers['Authorization'] = f'Bearer {self.token}'

                # Assume the token expires in 'expires_in' seconds if provided
                expires_in = json_response.get('expires_in', 3600)  # Default to 1 hour
                self.token_expiry = datetime.now() + timedelta(seconds=expires_in)
                self.logger.info('Login successful. Token expires at %s.', self.token_expiry)

            else:
                self.logger.error('Login failed with status code %d.', response.status_code)
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
        Enforces the rate limit using a sliding window algorithm.

        Tracks request timestamps and sleeps when the window is full, releasing the lock
        while sleeping so other threads are not blocked unnecessarily.
        """
        if not self.ratelimit:
            return

        while True:
            sleep_time = 0.0
            with self._rate_lock:
                now = time.time()
                # Prune timestamps outside the current window
                self._rate_timestamps = [t for t in self._rate_timestamps if now - t < self.period]
                if len(self._rate_timestamps) < self.calls:
                    # Slot available - record this request and proceed
                    self._rate_timestamps.append(now)
                    return
                # Window is full - calculate how long to wait
                oldest = self._rate_timestamps[0]
                sleep_time = self.period - (now - oldest) + 0.01

            # Sleep outside the lock so other threads aren't blocked
            self.logger.debug('Rate limit reached, sleeping for %.2f seconds', sleep_time)
            time.sleep(sleep_time)

    def make_request(
        self,
        session: requests.Session,
        method: str,
        url: str,
        params: dict[str, Any],
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

        full_url = self._build_url(url)

        try:
            response = session.request(
                method, full_url, params=params,
                proxies=self.proxies, timeout=self.request_timeout
            )
            self.logger.debug('Requesting URL: %s with status code: %d', response.url, response.status_code)
            return response
        except RequestException as e:
            self.logger.error('Network error during request to page %d: %s', page, e)
            raise

    def fetch_page(
        self,
        session: requests.Session,
        url: str,
        params: dict[str, Any],
        page: int,
        results: list[Any],
        pbar: tqdm | None = None,
        callback: Callable[[list[Any]], None] | None = None
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
                    fetched_data = (data.get(self.data_field) or []) if self.data_field else data

                    with self._results_lock:
                        results.extend(fetched_data)

                    if callback:
                        callback(fetched_data)

                    if pbar is not None:
                        pbar.update(len(fetched_data))

                    return  # Success, exit the function

                elif response.status_code == 401:
                    self.logger.error('Authentication failed with status code %d.', response.status_code)
                    raise AuthenticationFailed(f"Authentication failed with status code {response.status_code}")

                elif response.status_code == 403:
                    if not self.login_url:
                        self.logger.warning('Access denied with status code 403, retrying after 10 seconds...')
                        time.sleep(10)
                        continue  # Retry after sleeping
                    else:
                        self.logger.error('Access denied with status code %d.', response.status_code)
                        raise AuthenticationFailed(f"Access denied with status code {response.status_code}")

                else:
                    self.logger.warning('Failed to fetch page %d with status code %d.', page, response.status_code)

            except RequestException as e:
                self.logger.error('Network error fetching page %d: %s', page, e)

            retries -= 1
            if retries > 0:
                backoff = min(
                    self.retry_delay * (backoff_factor ** (self.retry - retries)),
                    self.max_backoff
                )
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
        self.logger.error('Response content (truncated): %.500s', response.text)
        self.logger.error('Request headers: %s', self._sanitize_headers(dict(response.request.headers)))

    def _resolve_items_per_page(self, json_data: dict) -> None:
        """Sets items_per_page from the API response if not already configured."""
        if not self.items_per_page:
            if self.response_items_field and self.response_items_field in json_data:
                self.items_per_page = json_data.get(self.response_items_field)
            else:
                self.items_per_page = json_data.get(self.items_field, 50)  # Default to 50

    def _extract_page_data(self, json_data: Any) -> list[Any]:
        """Extracts the data list from a JSON response using data_field."""
        if self.data_field:
            data = json_data.get(self.data_field) if isinstance(json_data, dict) else json_data
            return data if isinstance(data, list) else ([] if data is None else [data])
        if isinstance(json_data, list):
            return json_data
        return [json_data]

    def _paginate_until_empty(
        self,
        session: requests.Session,
        url: str,
        params: dict[str, Any],
        initial_data: list[Any],
        flatten_json: bool,
        callback: Callable[[list[Any]], None] | None
    ) -> list[Any]:
        """
        Fetches pages in parallel batches until a page returns an empty data field.

        Pages are fetched in batches of ``max_threads``.  After each batch
        completes, results are inspected **in page order** and appended to the
        output.  The first page whose data field is empty marks the end of
        pagination -- all data from earlier pages in that batch is kept, and
        no further batches are issued.

        At most ``max_threads - 1`` extra requests are made beyond the last
        page that contains data (the remaining pages in the final batch).

        Args:
            session: The requests session to use.
            url: The API endpoint URL.
            params: Base query parameters (without pagination params).
            initial_data: Data already extracted from the first page.
            flatten_json: Whether to flatten the result items.
            callback: Optional callback invoked per page.

        Returns:
            list: All fetched items across all pages.
        """
        results: list[Any] = list(initial_data)

        if callback and initial_data:
            callback(initial_data)

        if not initial_data or self.download_one_page_only:
            if flatten_json:
                results = [self.flatten_json(item) for item in results]
            return results

        page = 2
        with tqdm(desc='Downloading items', initial=len(results)) as pbar, \
             ThreadPoolExecutor(max_workers=self.max_threads) as executor:
            while True:
                batch_start = page
                batch_end = page + self.max_threads

                # Each page gets its own result list so we can inspect per-page
                page_results_map: dict[int, list[Any]] = {}
                future_to_page = {}

                for p in range(batch_start, batch_end):
                    page_data: list[Any] = []
                    page_results_map[p] = page_data

                    page_params = {
                        **params,
                        self.pagination_field: (
                            p if self.is_page_based
                            else (p - 1) * self.items_per_page
                        ),
                    }
                    if self.items_per_page:
                        page_params[self.items_field] = self.items_per_page

                    future = executor.submit(
                        self.fetch_page, session, url, page_params,
                        p, page_data, pbar, callback
                    )
                    future_to_page[future] = p

                # Wait for every page in this batch to finish
                for future in as_completed(future_to_page):
                    p = future_to_page[future]
                    try:
                        future.result()
                    except Exception as exc:
                        self.logger.error('Page %d generated an exception: %s', p, exc)
                        raise

                # Collect results in page order; stop at the first empty page
                found_empty = False
                for p in range(batch_start, batch_end):
                    if not page_results_map[p]:
                        found_empty = True
                        break
                    results.extend(page_results_map[p])

                if found_empty:
                    break

                page = batch_end

        if flatten_json:
            results = [self.flatten_json(item) for item in results]

        return results

    def fetch_all_pages(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        flatten_json: bool = False,
        headers: dict[str, str] | None = None,
        callback: Callable[[list[Any]], None] | None = None
    ) -> list[Any]:
        """
        Fetches all pages of data from a paginated API endpoint, optionally flattening the JSON
        structure of the results. Invokes a callback function after each page if provided.

        Args:
            url (str): The URL of the API endpoint to fetch data from.
            params (dict, optional): Additional query parameters to include in the request.
            flatten_json (bool, optional): If set to True, the returned JSON structure will be
                                        flattened. Defaults to False.
            headers (dict, optional): Additional headers for this request only.
            callback (function, optional): A callback function that is called after each page is fetched.

        Returns:
            list: A list of JSON objects fetched from the API. If `flatten_json` is True, each item is a flattened dictionary.
        """
        if not params:
            params = {}

        # Ensure authentication before copying headers
        self.ensure_authenticated()

        # Merge instance headers with method-specific headers, if any
        effective_headers = self.headers.copy()
        if headers:
            effective_headers.update(headers)

        # Initialize a session for connection pooling
        with requests.Session() as session:
            session.headers.update(effective_headers)
            session.verify = self.verify_ssl

            # Build initial request params including pagination for page 1
            initial_params = {
                **params,
                self.pagination_field: 1 if self.is_page_based else 0,
            }
            if self.items_per_page:
                initial_params[self.items_field] = self.items_per_page

            # Initial request to get first page data and total_count
            try:
                initial_response = session.get(
                    self._build_url(url), params=initial_params,
                    proxies=self.proxies, timeout=self.request_timeout
                )
                self.logger.debug('Initial request to %s returned status code %d', initial_response.url, initial_response.status_code)

                if initial_response.status_code != 200:
                    self._log_error_details(initial_response)
                    raise DataFetchFailedException(initial_response.status_code, initial_response.url, initial_response.text)

                json_data = initial_response.json()

                if not isinstance(json_data, dict):
                    return self.flatten_json(json_data) if flatten_json else json_data

                # Set items_per_page from response if not configured
                self._resolve_items_per_page(json_data)

                if self.items_per_page == 0:
                    self.logger.warning('items_per_page is 0, returning an empty result.')
                    return []

                # Extract page 1 data from the initial response
                initial_data = self._extract_page_data(json_data)

                # Branch: paginate until empty (sequential)
                if self.paginate_until_empty:
                    return self._paginate_until_empty(
                        session, url, params, initial_data, flatten_json, callback
                    )

                # Standard path: use total_count to calculate pages
                total_count = json_data.get(self.total_count_field, None)

                if total_count is None:
                    self.logger.warning('Total count field "%s" missing, cannot paginate properly.', self.total_count_field)
                    if flatten_json:
                        return [self.flatten_json(item) for item in initial_data] if initial_data else []
                    return initial_data if initial_data else []

                total_pages = 1 if self.download_one_page_only else math.ceil(total_count / self.items_per_page)
                self.logger.info('Total items to download: %d | Number of pages to fetch: %d', total_count, total_pages)

                # Start with page 1 data already fetched
                results: list[Any] = list(initial_data)

                if callback and initial_data:
                    callback(initial_data)

                # Fetch remaining pages (2..total_pages) in parallel
                if total_pages > 1:
                    with tqdm(total=total_count, initial=len(results), desc='Downloading items') as pbar, \
                         ThreadPoolExecutor(max_workers=self.max_threads) as executor:

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
                            ): page for page in range(2, total_pages + 1)
                        }

                        for future in as_completed(future_to_page):
                            page = future_to_page[future]
                            try:
                                future.result()
                            except Exception as exc:
                                self.logger.error('Page %d generated an exception: %s', page, exc)
                                raise

                # Optionally flatten JSON if required
                if flatten_json:
                    results = [self.flatten_json(item) for item in results]

                return results

            except RequestException as e:
                self.logger.error('Network error during initial request: %s', e)
                raise DataFetchFailedException(0, url, str(e)) from e
