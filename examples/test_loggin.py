import logging
import coloredlogs     # https://coloredlogs.readthedocs.io/en/latest/readme.html#usage

class MyHandler():

    def __init__(self, level='DEBUG', use_color = True):
        self.log = logging.getLogger('root')

        fmt = '[%(asctime)s] %(filename)-17s [%(levelname)-6s] %(message)s'
        date_fmt = '%Y-%m-%d %H:%M:%S'
        coloredlogs.install(fmt=fmt, datefmt=date_fmt, level=level, logger=self.log)

        self.log.debug('__init__ MyHandler')


"""
Example script to demonstrate the usage of the Paginator class
from the jsonPagination library for fetching and paginating data.
"""

from jsonPagination import Paginator

# My login
import logging
log = logging.getLogger('root')

MyHandler(level='INFO')

def main():
    """Main function to demonstrate Paginator usage."""
    try:
        paginator = Paginator()

        # API with pagination
        results = paginator.fetch_all_pages(url='https://reqres.in/api/users')
        print('Downloaded data:')
        print(results)

        # API with no pagination
        results = paginator.fetch_all_pages(url='https://reqres.in/api/users/2')
        print('Downloaded data:')
        print(results)

    except Exception as e:  # pylint: disable=W0718
        print(f"An error occurred: {e}")


if __name__ == '__main__':
    main()
