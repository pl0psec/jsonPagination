# jsonPagination 

[![python](https://img.shields.io/badge/Python-3.9-3776AB.svg?style=flat&logo=python&logoColor=white)](https://www.python.org)
[![License: GPLv3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
![pylint](https://img.shields.io/badge/PyLint-9.71-green?logo=python&logoColor=white)
[![GitHub version](https://badge.fury.io/gh/pl0psec%2FjsonPagination.svg)](https://badge.fury.io/gh/pl0psec%2FjsonPagination)
[![PyPI version](https://badge.fury.io/py/jsonPagination.svg)](https://badge.fury.io/py/jsonPagination)

`jsonPagination` is a Python library designed to simplify the process of fetching and paginating JSON data from APIs. It supports authentication, multithreading for efficient data retrieval, and handling of pagination logic, making it ideal for working with large datasets or APIs with rate limits.

## Features

- **Easy Pagination**: Simplifies the process of fetching large datasets by automatically handling the pagination logic. It can manage both page-number-based and index-offset-based pagination methods, seamlessly iterating through pages or data chunks.

- **Authentication Support**: Facilitates secure access to protected APIs with built-in support for various authentication mechanisms, including basic auth, bearer tokens, and custom header-based authentication. This feature abstracts away the complexity of managing authentication tokens, automatically obtaining and renewing them as needed.

- **Multithreading**: Utilizes concurrent threads to fetch data in parallel, significantly reducing the overall time required to retrieve large datasets. The number of threads can be adjusted to optimize the balance between speed and system resource utilization.

- **Flexible Configuration**: Offers customizable settings for pagination parameters, such as the field names for page numbers, item counts, and total records. This flexibility ensures compatibility with a wide range of APIs, accommodating different pagination schemes.

- **Automatic Rate Limit Handling**: Intelligent rate limit management prevents overloading the API server by automatically throttling request rates based on the API's specified limits. This feature helps to maintain compliance with API usage policies and avoids unintentional denial of service.

- **Custom Headers Support**: Enables the injection of custom HTTP headers into each request, providing a way to include additional metadata like API keys, session tokens, or other authentication information required by the API.

- **Error Handling and Retry Logic**: Implements robust error detection and retry mechanisms to handle transient network issues or API errors. This ensures that temporary setbacks do not interrupt the data retrieval process, improving the reliability of data fetching operations.


## Installation

To install `jsonPagination`, simply use pip:

    pip install jsonPagination

## Usage

### Basic Pagination
Here's how to use `jsonPagination` for basic pagination, demonstrating both page-based and index-based pagination:

```python
from jsonPagination.paginator import Paginator

# Page-based pagination example
paginator = Paginator(
    current_page_field='page',  # Field name used by the API for page number
    items_field='items_per_page',  # Field name used by the API for the number of items per page
    max_threads=2
)

results = paginator.fetch_all_pages('https://api.example.com/data')

print("Downloaded data:")
print(results)
```

### Pagination with Authentication
#### Basic Authentication
For APIs that use basic authentication, you can directly include credentials in the header:

```python
from jsonPagination.paginator import Paginator

headers = {
    'Authorization': 'Basic <base64_encoded_credentials>'
}

paginator = Paginator(
    headers=headers,
    max_threads=2
)

results = paginator.fetch_all_pages('https://api.example.com/data')

print("Downloaded data with basic authentication:")
print(results)
```

#### Token-based Authentication
For APIs requiring a token, provide the login URL and authentication data:

```python
from jsonPagination.paginator import Paginator

paginator = Paginator(
    login_url='https://api.example.com/api/login',
    auth_data={'username': 'your_username', 'password': 'your_password'},
    max_threads=2
)

results = paginator.fetch_all_pages('https://api.example.com/api/data')

print("Downloaded data with token-based authentication:")
print(results)
```

### Rate Limit Example
Demonstrating how to handle rate limits:

```python
from jsonPagination.paginator import Paginator

paginator = Paginator(
    max_threads=2,
    ratelimit=(5, 60)  # 5 requests per 60 seconds
)

results = paginator.fetch_all_pages('https://api.example.com/data')

print("Downloaded data with rate limiting:")
print(results)
```

## Configuration

When instantiating the `Paginator` class, you can configure the following parameters to tailor its behavior:

- `url`: The API endpoint URL from which data will be fetched.
- `login_url` (optional): The URL to authenticate and retrieve a bearer token, used if the API requires token-based authentication.
- `auth_data` (optional): A dictionary containing authentication data (such as `username` and `password`) required by the login endpoint for obtaining a token.
- `current_page_field` (optional): The JSON field name used by the API to denote the current page number, applicable for page-number-based pagination.
- `current_index_field` (optional): The JSON field name used by the API to denote the starting index for data fetching, applicable for index-based pagination.
- `items_field` (optional): The JSON field name for the number of items to fetch per request, which corresponds to `per_page` in many APIs. This is used to control pagination size.
- `total_count_field`: The JSON field name that contains the total number of items available, used to calculate the total number of pages or batches.
- `items_per_page` (optional): Specifies the number of items to request per page or batch. If not set, the Paginator will try to use a sensible default based on the first API response or a predefined value.
- `max_threads`: The maximum number of threads to use for parallel data fetching, enhancing speed for large datasets.
- `download_one_page_only` (optional): A boolean indicating whether to fetch only the first page/batch of data, useful for testing or when only a sample of data is needed.
- `verify_ssl` (optional): Determines whether SSL certificates should be verified in HTTP requests, enhancing security.
- `data_field`: The specific JSON field name from which to extract the main data in the API response, necessary for parsing the fetched JSON data correctly.
- `log_level` (optional): Sets the verbosity of logging, with possible values like `DEBUG`, `INFO`, `WARNING`, `ERROR`, and `CRITICAL`, to assist in debugging and monitoring.
- `headers` (optional): A dictionary of custom HTTP headers to include in every request made by the Paginator, enabling additional customization like API keys or session tokens.
- `ratelimit` (optional): A tuple specifying the rate limit as `(calls, period)` to prevent exceeding the API's rate limiting policies, ensuring compliant and responsible usage.

These configuration options provide extensive control over how the `Paginator` interacts with the API, including authentication mechanisms, request formatting, error handling, and data retrieval efficiency. By adjusting these parameters, you can optimize the behavior of the Paginator to match the specific requirements and constraints of the API you are working with.

## Contributing

We welcome contributions to `jsonPagination`! Please open an issue or submit a pull request for any features, bug fixes, or documentation improvements.

## License

`jsonPagination` is released under the MIT License. See the LICENSE file for more details.
