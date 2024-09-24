"""
Example script to demonstrate the usage of the Paginator class
from the jsonPagination library for fetching and paginating data.
"""

import sys
import os
import logging
from typing import Any, Callable, Dict, List, Optional

# Add the project root to the Python path before importing jsonPagination
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from jsonPagination import Paginator  # Now import should work

def main():
    """Main function to demonstrate Paginator usage."""
    try:
        # Initialize the Paginator for a paginated API endpoint
        paginator = Paginator(
            base_url='https://reqres.in',               # Base URL for the API
            log_level='DEBUG',                           # Set logging level to DEBUG for detailed logs
            items_per_page=6,                            # Number of items per page as per Reqres.in documentation
            max_threads=2,                               # Number of threads to use for fetching pages
            download_one_page_only=False,                # Set to False to download all pages
            current_page_field='page',                   # Field name for the current page in request parameters
            items_field='per_page',                      # Field name for items per page in request parameters
            total_count_field='total',                   # Field name for total item count in response
            data_field='data',                           # Field name that contains the list of items in response
            verify_ssl=True,                             # Enable SSL verification
            retry_delay=5,                               # Delay in seconds before retrying a failed request
            ratelimit=None,                              # No rate limiting for Reqres.in
            headers={
                'Accept': 'application/json'              # Specify that we expect JSON responses
            }
            # No authentication required for Reqres.in, so login_url and auth_data are omitted
        )

        # Define a callback function to process each fetched page (optional)
        def process_page(fetched_data: List[Any]) -> None:
            """
            Callback function to process each fetched page.
            For demonstration, we'll print the number of items fetched in the page.
            """
            print(f'Processed {len(fetched_data)} items from the current page.')

        # -----------------------------
        # Example 1: API with Pagination
        # -----------------------------
        print("Fetching paginated user data from Reqres.in...\n")
        results_paginated = paginator.fetch_all_pages(
            url='/api/users',                             # Relative URL for the paginated endpoint
            params={'delay': 1},                          # Optional: Add delay to simulate network latency
            flatten_json=False,                           # Reqres.in returns flat JSON objects
            callback=process_page                         # Pass the callback function to process each page
        )
        print('\nDownloaded paginated data:')
        for user in results_paginated:
            print(f"ID: {user['id']}, Name: {user['first_name']} {user['last_name']}, "
                  f"Email: {user['email']}, Avatar: {user['avatar']}")

        # -------------------------------
        # Example 2: API without Pagination
        # -------------------------------
        # Initialize another Paginator instance for single resource fetching
        paginator_single = Paginator(
            base_url='https://reqres.in',                  # Base URL for the API
            log_level='DEBUG',                             # Set logging level to DEBUG for detailed logs
            items_per_page=1,                              # Set items_per_page to 1 for single resource
            max_threads=1,                                 # Single thread as only one request is needed
            download_one_page_only=True,                   # Set to True since it's a single resource
            current_page_field=None,                       # Not needed for single resource
            items_field=None,                              # Not needed for single resource
            total_count_field=None,                        # Not needed for single resource
            data_field='data',                             # Field name that contains the item in response
            verify_ssl=True,                               # Enable SSL verification
            retry_delay=5,                                 # Delay in seconds before retrying a failed request
            ratelimit=None,                                # No rate limiting for Reqres.in
            headers={
                'Accept': 'application/json'               # Specify that we expect JSON responses
            }
            # No authentication required for Reqres.in, so login_url and auth_data are omitted
        )

        print("\nFetching single user data from Reqres.in...\n")
        results_single = paginator_single.fetch_all_pages(
            url='/api/users/2',                            # Relative URL for the single user endpoint
            params={},                                     # No additional params needed
            flatten_json=False,                            # Reqres.in returns flat JSON objects
            callback=lambda data: print(f'Fetched single user: {data}')  # Inline callback function
        )
        print('\nDownloaded single user data:')
        for user in results_single:
            print(f"ID: {user['id']}, Name: {user['first_name']} {user['last_name']}, "
                  f"Email: {user['email']}, Avatar: {user['avatar']}")

    except Exception as e:  # pylint: disable=W0718
        print(f"An error occurred: {e}")

if __name__ == '__main__':
    main()
