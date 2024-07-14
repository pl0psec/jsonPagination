"""
Example script to demonstrate the usage of the Paginator class
from the jsonPagination library for fetching and paginating data.
"""

from jsonPagination import Paginator

def hello(data, step):
    """
    A callback function that processes the data received after each fetch.

    Args:
        data (dict or list): The JSON data received from the fetch operation.
        step (str): The operation step or identifier.
    """
    print('plop')
    print(f"Length of the JSON downloaded: {len(data)}")

def main():
    """Main function to demonstrate Paginator usage."""
    try:
        paginator = Paginator(
            log_level='INFO',
            max_threads=10,
            current_index_field='startIndex',  # Used for index-based pagination
            items_field='resultsPerPage',  # This replaces per_page_field
            total_count_field='totalResults',
            data_field='vulnerabilities',
            headers={'apikey': '***************************************'},
            ratelimit=(45, 30)  # Rate limit configuration
        )

        # ratelimit=(4, 30)     ->  31:45
        # ratelimit=(45, 30)    ->  03:56
        # ratelimit=(50, 30)    ->  04:11

        # API with pagination
        # results = paginator.fetch_all_pages(url='https://reqres.in/api/users')

        # {"resultsPerPage":2000,
        # "startIndex":0,
        # "totalResults":242486, "format":"NVD_CVE","version":"2.0","timestamp":"2024-03-23T10:19:20.233","vulnerabilities":[{
        results = paginator.fetch_all_pages(url='https://services.nvd.nist.gov/rest/json/cves/2.0', callback=hello)
        print('Downloaded data:')
        # print(results)

    except Exception as e:  # pylint: disable=W0718
        print(f"An error occurred: {e}")


if __name__ == '__main__':
    main()
