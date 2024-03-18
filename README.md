# jsonPagination 

[![python](https://img.shields.io/badge/Python-3.9-3776AB.svg?style=flat&logo=python&logoColor=white)](https://www.python.org)
![pylint](https://img.shields.io/badge/PyLint-9.81-green?logo=python&logoColor=white)
[![License: GPLv3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

`jsonPagination` is a Python library designed to simplify the process of fetching and paginating JSON data from APIs. It supports authentication, multithreading for efficient data retrieval, and handling of pagination logic, making it ideal for working with large datasets or APIs with rate limits.

## Features

- **Easy Pagination**: Automatically handles API pagination to fetch all available data.
- **Multithreading**: Speeds up data retrieval by fetching pages in parallel.
- **Authentication Support**: Includes support for APIs requiring authentication via bearer tokens.
- **Flexible**: Allows customization of pagination parameters and can be used with any JSON-based API.

## Installation

(WIP) soon: To install `jsonPagination`, simply use pip:

    pip install jsonPagination

## Usage

Here's a quick example to get you started:

```python
from jsonPagination.paginator import Paginator

paginator = Paginator(
    url='https://reqres.in/api/users',
    max_threads=5
)

paginator.download_all_pages()
results = paginator.get_results()

print("Downloaded data:")
print(results)
```

## Configuration

When instantiating the `Paginator` class, you can configure the following parameters:

- `url`: The API endpoint URL.
- `login_url` (optional): The URL to authenticate and retrieve a bearer token.
- `auth_data` (optional): A dictionary containing authentication data required by the login endpoint, typically including `username` and `password`.
- `current_page_field`: The JSON field name for the current page number (default: 'page').
- `per_page_field`: The JSON field name for the number of items per page (default: 'per_page').
- `total_count_field`: The JSON field name for the total count of items (default: 'total').
- `per_page` (optional): Number of items per page to request from the API. If not set, the default provided by the API is used.
- `max_threads`: The maximum number of threads for parallel requests (default: 5).
- `download_one_page_only`: Whether to download only the first page of data or paginate through all available data (default: False).
- `verify_ssl`: Whether to verify SSL certificates for HTTP requests (default: True).
- `data_field`: Specific JSON field name from which to extract the data (default: 'data').
- `log_level`: The logging level for the Paginator instance (default: 'INFO').

These parameters allow for customization of the pagination behavior, including how the Paginator interacts with the API, how it handles authentication, and how it processes the retrieved data.

## Contributing

We welcome contributions to `jsonPagination`! Please open an issue or submit a pull request for any features, bug fixes, or documentation improvements.

## License

`jsonPagination` is released under the MIT License. See the LICENSE file for more details.
