# jsonPagination 

[![python](https://img.shields.io/badge/Python-3.9-3776AB.svg?style=flat&logo=python&logoColor=white)](https://www.python.org)
[![License: GPLv3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
![pylint](https://img.shields.io/badge/PyLint-9.77-green?logo=python&logoColor=white)
[![GitHub version](https://badge.fury.io/gh/pl0psec%2FjsonPagination.svg)](https://badge.fury.io/gh/pl0psec%2FjsonPagination)
[![PyPI version](https://badge.fury.io/py/jsonPagination.svg)](https://badge.fury.io/py/jsonPagination)

`jsonPagination` is a Python library designed to simplify the process of fetching and paginating JSON data from APIs. It supports authentication, multithreading for efficient data retrieval, and handling of pagination logic, making it ideal for working with large datasets or APIs with rate limits.

## Features

- **Easy Pagination**: Automatically handles API pagination to fetch all available data.
- **Authentication Support**: Includes support for APIs requiring authentication via bearer tokens.
- **Multithreading**: Speeds up data retrieval by fetching pages in parallel.
- **Flexible**: Allows customization of pagination parameters and can be used with any JSON-based API.

## Todo

- **Rate limit**

## Installation

To install `jsonPagination`, simply use pip:

    pip install jsonPagination

## Usage

### Basic Pagination
Here's a quick example to get you started without authentication:

```python
from jsonPagination.paginator import Paginator

paginator = Paginator(
    max_threads=5
)

paginator.fetch_all_pages()
results = paginator.get_results()

print("Downloaded data:")
print(results)
```

### Pagination with Authentication
If the API requires authentication, provide the login URL and authentication data. The `Paginator` will convert the username and password into a token internally.

```python
from jsonPagination.paginator import Paginator

# Assuming the API uses a login endpoint to exchange username/password for a token
paginator = Paginator(
    login_url='https://api.example.com/api/login',
    auth_data={'username': 'your_username', 'password': 'your_password'},
    max_threads=5
)

paginator.fetch_all_pages(url='https://api.example.com/api/users')
results = paginator.get_results()

print("Downloaded data with authentication:")
print(results)
```

In this example:
- `auth_data` contains the credentials (`username` and `password`) needed to authenticate.
- When `Paginator` is instantiated, it uses `auth_data` to request an authentication token from the `login_url`.
- Once obtained, the token is stored internally within the `Paginator` instance.
- For all subsequent API requests to fetch data, the `Paginator` automatically includes this token in the HTTP header to authenticate the request. Typically, the token is added as a `Bearer` token in the `Authorization` header.
- This process abstracts the authentication management from the user, simplifying the data fetching and pagination process.


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
