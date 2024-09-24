# jsonPagination 

[![Python](https://img.shields.io/badge/Python-3.9-3776AB.svg?style=flat&logo=python&logoColor=white)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
![PyLint](https://img.shields.io/badge/PyLint-9.73-green?logo=python&logoColor=white)[![GitHub release (latest by date)](https://img.shields.io/github/v/release/pl0psec/jsonPagination)](https://github.com/pl0psec/jsonPagination/releases)
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

To install `jsonPagination`, you have two options:

1. Install directly using pip:

    ```sh
    pip install jsonPagination
    ```

2. If you have a `requirements.txt` file that includes `jsonPagination`, install all the required packages using:

    ```sh
    pip install -r requirements.txt
    ```

Make sure `jsonPagination` is listed in your `requirements.txt` file with the desired version, like so:

```sh
jsonPagination==x.y.z
```

Replace `x.y.z` with the specific version number you want to install.

## Usage

### Basic Pagination

Here's how to use `jsonPagination` for basic pagination, demonstrating both page-based and index-based pagination:

```python
from jsonPagination.paginator import Paginator

# Instantiate the Paginator with a base URL
paginator = Paginator(
    base_url='https://api.example.com',
    current_page_field='page',  # Field name used by the API for page number
    items_field='items_per_page',  # Field name used by the API for the number of items per page
    max_threads=2
)

# Fetch data using a relative path
results = paginator.fetch_all_pages('/data')

print("Downloaded data:")
print(results)
```

**Note:**
If your API request needs to specify a different number of items per page (`items_per_page`) than what is expected in the API response (`response_items_field`), you can configure these separately in the Paginator constructor. For example, if the API uses 'items_per_page' in the request but returns 'count' in the response to specify how many items are in each page, configure your Paginator like this:

```python
paginator = Paginator(
    base_url='https://api.example.com',
    current_page_field='page',
    items_field='items_per_page',  # Field name for request pagination
    response_items_field='count',  # Field name in the response for the number of items
    max_threads=2
)
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
    base_url='https://api.example.com',
    headers=headers,
    max_threads=2
)

results = paginator.fetch_all_pages('/api/data')

print("Downloaded data with basic authentication:")
print(results)
```

#### Token-based Authentication

For APIs requiring a token, configure the `login_url` with the base URL during instantiation:

```python
from jsonPagination.paginator import Paginator

paginator = Paginator(
    base_url='https://api.example.com',
    login_url='/api/login',  # Relative path for login
    auth_data={'username': 'your_username', 'password': 'your_password'},
    max_threads=2
)

results = paginator.fetch_all_pages('/api/data')

print("Downloaded data with token-based authentication:")
print(results)
```

**Note:** Ensure that the `login_url` is a relative path if it should be joined with the `base_url`. The Paginator will handle the full URL construction internally.

### Rate Limit Example

Demonstrating how to handle rate limits:

```python
from jsonPagination.paginator import Paginator

paginator = Paginator(
    base_url='https://api.example.com',
    max_threads=2,
    ratelimit=(5, 60)  # 5 requests per 60 seconds
)

results = paginator.fetch_all_pages('/api/data')

print("Downloaded data with rate limiting:")
print(results)
```

### Advanced Configuration

You can further customize the paginator by adjusting additional parameters such as `verify_ssl`, `retry_delay`, `download_one_page_only`, and more. Here's an example with additional configurations:

```python
from jsonPagination.paginator import Paginator

paginator = Paginator(
    base_url='https://api.example.com',
    login_url='/api/login',
    auth_data={'username': 'your_username', 'password': 'your_password'},
    current_page_field='page',
    items_field='per_page',
    response_items_field='count',
    max_threads=4,
    verify_ssl=False,  # Disable SSL verification if needed
    retry_delay=10,    # Retry delay in seconds
    ratelimit=(10, 60), # 10 requests per 60 seconds
    log_level='DEBUG'  # Set log level to DEBUG for more verbose output
)

results = paginator.fetch_all_pages('/api/data', flatten_json=True)

print("Downloaded and flattened data:")
print(results)
```

### Paginator Parameters

Below is a comprehensive list of all available parameters for the `Paginator` class, along with their explanations:

| Parameter               | Type                      | Default                | Description                                                                                                                                                     |
|-------------------------|---------------------------|------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `base_url`              | `str`                     | **Required**           | The base URL for the API.                                                                                                                                       |
| `login_url`             | `str`, optional           | `None`                 | URL for authentication to retrieve a token. Must be a relative path if `base_url` is provided.                                                                 |
| `auth_data`             | `dict`, optional          | `None`                 | Credentials required for the login endpoint. Typically includes fields like username and password.                                                              |
| `current_page_field`    | `str`, optional           | `None`                 | Field name for the current page number in the API request. Use either `current_page_field` or `current_index_field`, not both.                                   |
| `current_index_field`   | `str`, optional           | `None`                 | Field name for the starting index in the API request. Use either `current_page_field` or `current_index_field`, not both.                                         |
| `items_field`           | `str`                     | `'per_page'`           | Field name for the number of items per page in the API request.                                                                                                 |
| `total_count_field`     | `str`                     | `'total'`              | Field name in the API response that holds the total number of items.                                                                                             |
| `items_per_page`        | `int`, optional           | `None`                 | The number of items to request per page. If not set, it will be determined dynamically based on the API response or default to 50.                                   |
| `response_items_field`  | `str`, optional           | `None`                 | Field name in the response for the number of items returned per page. Useful if the API uses a different field name for item count in responses.                    |
| `max_threads`           | `int`                     | `5`                    | Maximum number of threads to use for parallel requests. Adjust based on system resources and API rate limits.                                                   |
| `download_one_page_only`| `bool`                    | `False`                | Whether to fetch only the first page of data. Useful for scenarios where only a subset of data is needed.                                                        |
| `verify_ssl`            | `bool`                    | `True`                 | Whether to verify SSL certificates for HTTP requests. Set to `False` to disable SSL verification (not recommended for production environments).                   |
| `data_field`            | `str`                     | `'data'`               | Field name from which to extract the data in the API response. If the API nests data within a specific field, specify it here.                                     |
| `log_level`             | `str`                     | `'INFO'`               | Logging level for the paginator. Valid options include `'DEBUG'`, `'INFO'`, `'WARNING'`, `'ERROR'`, and `'CRITICAL'`.                                           |
| `retry_delay`           | `int`                     | `30`                   | Time in seconds to wait before retrying a failed request. Implements exponential backoff for subsequent retries.                                                  |
| `ratelimit`             | `tuple`, optional         | `None`                 | Rate limit settings as a tuple `(calls, period)` where `calls` is the number of allowed calls in `period` seconds. For example, `(5, 60)` allows 5 calls per minute. |
| `headers`               | `dict`, optional          | `None`                 | Additional headers to include in the requests. Useful for including API keys, session tokens, or other custom headers required by the API.                          |
| `logger`                | `logging.Logger`, optional| `None`                 | Custom logger instance. If not provided, the default logger is used. Allows integration with existing logging configurations in your application.                    |

## Contributing

We welcome contributions to `jsonPagination`! Please open an issue or submit a pull request for any features, bug fixes, or documentation improvements.

## License

`jsonPagination` is released under the MIT License. See the [LICENSE](https://opensource.org/licenses/MIT) file for more details.