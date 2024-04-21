# jsonPagination 

[![python](https://img.shields.io/badge/Python-3.9-3776AB.svg?style=flat&logo=python&logoColor=white)](https://www.python.org)
[![License: GPLv3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
![pylint](https://img.shields.io/badge/PyLint-9.73-green?logo=python&logoColor=white)
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

To install `jsonPagination`, you have two options:

1. Install directly using pip:

    ```
    pip install jsonPagination
    ```

2. If you have a `requirements.txt` file that includes `jsonPagination`, install all the required packages using:

    ```
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

results = paginator.fetch_all_pages('/data')

print("Downloaded data with basic authentication:")
print(results)
```

#### Token-based Authentication
For APIs requiring a token, configure the `login_url` with the base URL during instantiation:

```python
from jsonPagination.paginator import Paginator
from urllib.parse import urljoin

paginator = Paginator(
    base_url='https://api.example.com',
    login_url=urljoin(base_url, '/api/login'),
    auth_data={'username': 'your_username', 'password': 'your_password'},
    max_threads=2
)

results = paginator.fetch_all_pages('/api/data')

print("Downloaded data with token-based authentication:")
print(results)
```

### Rate Limit Example
Demonstrating how to handle rate limits:

```python
from jsonPagination.paginator import Paginator

paginator = Paginator(
    base_url='https://api.example.com',
    max_threads=2,
    ratelimit=(5, 60)  # 5 requests per 60 seconds
)

results = paginator.fetch_all_pages('/data')

print("Downloaded data with rate limiting:")
print(results)
```

## Contributing

We welcome contributions to `jsonPagination`! Please open an issue or submit a pull request for any features, bug fixes, or documentation improvements.

## License

`jsonPagination` is released under the MIT License. See the LICENSE file for more details.
