"""
Example script to demonstrate the usage of the Paginator class
from the jsonPagination library for fetching and paginating data.
"""

from jsonPagination import Paginator

def main():
    """Main function to demonstrate Paginator usage."""
    try:
        paginator = Paginator()

        # API with pagination
        results = paginator.fetch_all_pages(url='https://reqres.in/api/users')
        print("Downloaded data:")
        print(results)

        # API with no pagination
        results = paginator.fetch_all_pages(url='https://reqres.in/api/users/2')
        print("Downloaded data:")
        print(results)

    except Exception as e:  # pylint: disable=W0718
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    main()
