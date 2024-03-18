"""
Example script to demonstrate the usage of the Paginator class
from the jsonPagination library for fetching and paginating data.
"""

from jsonPagination import Paginator

def main():
    """Main function to demonstrate Paginator usage."""
    try:
        paginator = Paginator(
            url='https://reqres.in/api/users',
            max_threads=5
        )

        paginator.download_all_pages()
        results = paginator.get_results()
        print("Downloaded data:")
        print(results)
    except Exception as e:  # pylint: disable=W0718
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
