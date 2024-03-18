"""
A module for fetching and paginating JSON data from APIs with support for multithreading,
customizable authentication, and the option to disable SSL verification for HTTP requests.
"""

import logging
import time
from queue import Queue
from threading import Thread, Lock
from urllib.parse import urlencode

import requests
from requests.exceptions import RequestException
import urllib3
from tqdm import tqdm


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


class Paginator:
    """
    A class for fetching and paginating JSON data from APIs with support for multithreading,
    customizable authentication, and the option to disable SSL verification for HTTP requests.
    """

    def __init__(self, url, login_url=None, auth_data=None, current_page_field='page',
                 per_page_field='per_page', total_count_field='total', per_page=None,
                 max_threads=5, download_one_page_only=False, verify_ssl=True, data_field='data',
                 log_level='INFO'):
        """
        Initializes the Paginator with the given configuration.

        Args:
            url (str): The API endpoint URL.
            login_url (str, optional): The URL to authenticate and retrieve a bearer token.
            auth_data (dict, optional): Authentication data required by the login endpoint.
            current_page_field (str, optional): JSON field name for the current page number.
            per_page_field (str, optional): JSON field name for the number of items per page.
            total_count_field (str, optional): JSON field name for the total count of items.
            per_page (int, optional): Number of items per page to request from the API.
            max_threads (int, optional): Maximum number of threads for parallel requests.
            download_one_page_only (bool, optional): Whether to download only the first page
            of data.
            verify_ssl (bool, optional): Whether to verify SSL certificates for HTTP requests.
            data_field (str, optional): Specific JSON field name from which to extract the data.
        """

        # Setup logger with a console handler
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)  # Set logger to debug level

        # Ensure there is at least one handler
        # Ensure there is at least one handler
        if not self.logger.handlers:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.getLevelName(
                log_level))  # Set handler level
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)

        self.logger.info("Initializing Paginator with URL: %s", url)

        self.url = url
        self.login_url = login_url
        self.auth_data = auth_data
        self.current_page_field = current_page_field
        self.per_page_field = per_page_field
        self.total_count_field = total_count_field
        self.per_page = per_page
        self.max_threads = max_threads
        self.timeout = 60
        self.download_one_page_only = download_one_page_only
        self.verify_ssl = verify_ssl
        self.data_field = data_field  # New parameter to specify the data field
        self.token = None
        self.headers = {}
        self.data_queue = Queue()
        self.results = []
        self.retry_lock = Lock()
        self.is_retrying = False

        if not self.verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            self.logger.debug("SSL verification is disabled for all requests.")

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
        response = requests.post(
            self.login_url, json=self.auth_data, verify=self.verify_ssl, timeout=self.timeout)

        self.logger.debug(
            "Login request to %s returned status code %d", self.login_url, response.status_code)
        if response.status_code == 200:
            self.token = response.json().get('token')
            self.headers['Authorization'] = f'Bearer {self.token}'
            self.logger.error(
                "Login failed with status code %d.", response.status_code)
        else:
            self.logger.error(
                "Login failed with status code %d.", response.status_code)
            raise LoginFailedException(response.status_code)

    def fetch_page(self, page, pbar=None):
        """
        Fetches a single page of data from the API and updates the progress bar.

        Args:
            page (int): The page number to fetch.
            pbar (tqdm, optional): A tqdm progress bar instance to update with progress.
        """
        retries = 3
        timeout = 30

        while retries > 0:
            params = {self.current_page_field: page,
                      self.per_page_field: self.per_page}
            query_string = urlencode(params)
            full_url = f"{self.url}?{query_string}"

            self.logger.debug(
                "Attempting to fetch page %d with full URL: GET %s", page, full_url)

            try:
                response = requests.get(
                    self.url, headers=self.headers, params=params, timeout=timeout,
                    verify=self.verify_ssl)
                self.logger.debug(
                    "Request made to %s, response status: %d", full_url, response.status_code)

                if response.status_code == 200:
                    data = response.json()
                    fetched_data = data.get(
                        self.data_field, []) if self.data_field else data
                    self.data_queue.put(fetched_data)

                    if pbar:
                        pbar.update(len(fetched_data))

                    self.logger.debug(
                        "Successfully fetched page %d, retrieved %d records.",
                        page, len(fetched_data))
                    return  # Exit the loop on successful fetch

                self.logger.error(
                    "Failed to fetch page %d: HTTP %d", page, response.status_code)
                if response.status_code in [401, 403]:
                    raise AuthenticationFailed(
                        f"Authentication failed with status code {response.status_code}")

            except requests.exceptions.Timeout as e:
                self.logger.warning(
                    "Timeout occurred fetching page %d: %s", page, e)
                retries -= 1

            except RequestException as e:
                self.logger.error("Network error fetching page %d: %s", page, e)
                break

            except Exception as e:
                self.logger.error("Unexpected error fetching page %d: %s", page, e)
                break

            finally:
                with self.retry_lock:
                    self.is_retrying = False

        if retries == 0:
            self.logger.error(
                "Failed to fetch page %d after %d retries.", page, 3)

    def download_all_pages(self):
        """
        Downloads all pages of data from the API using multithreading.

        This method fetches each page of data concurrently and aggregates the results.
        It respects the pagination settings and handles authentication if necessary.
        """
        start_time = time.time()

        if self.login_url and not self.token and self.auth_data:
            self.login()

        response = requests.get(
            self.url, headers=self.headers, verify=self.verify_ssl, timeout=self.timeout)
        if response.status_code != 200:
            self.logger.error("Failed to fetch initial data from %s", self.url)
            raise DataFetchFailedException(response.status_code, self.url)

        json_data = response.json()
        total_count = json_data.get(self.total_count_field)
        per_page = self.per_page or json_data.get(self.per_page_field)

        if total_count is None or per_page is None:
            self.logger.error("Pagination data missing or invalid")
            raise ValueError(
                f"Pagination data missing: total_count={total_count}, per_page={per_page}")

        total_pages = 1 if self.download_one_page_only else - \
            (-total_count // per_page)
        self.logger.info(
            "Total pages to fetch: %d, Total records to download: %d", total_pages, total_count)

        self.logger.info(
            "Downloading %d records across %d pages...",total_count, total_pages)

        with tqdm(total=total_count, desc="Downloading records") as pbar:
            threads = []
            for page in range(1, total_pages + 1):
                while len(threads) >= self.max_threads:
                    for t in threads:
                        t.join()
                    threads = []  # Clear out threads that have finished
                thread = Thread(target=self.fetch_page, args=(page, pbar))
                thread.start()
                threads.append(thread)

            # Wait for any remaining threads to complete
            for t in threads:
                t.join()

        while not self.data_queue.empty():
            data = self.data_queue.get()
            self.results.extend(data)

        end_time = time.time()
        elapsed_time = end_time - start_time
        self.logger.info("Completed downloading all pages in %s",
                         time.strftime('%H:%M:%S', time.gmtime(elapsed_time)))

    def get_results(self):
        """
        Returns the accumulated results from all fetched pages.

        Returns:
            list: A list of JSON objects fetched from the API.
        """
        self.logger.info("Retrieving results from fetched data.")
        return self.results
