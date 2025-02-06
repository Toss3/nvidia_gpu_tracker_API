# RTX 5090 FE Stock Tracker (API Version)

This project is a Python script that monitors the availability of NVIDIA GeForce RTX 50 series graphics cards (and others, if configured) on the NVIDIA marketplace. It uses the NVIDIA Partners API to periodically check for product availability and sends email notifications when a matching product is in stock.  It also sends an email if the API is down for a configurable number of consecutive checks.

## Features

-   **Automated Stock Checking:** Monitors the NVIDIA Partners API for RTX 50 series (and other configured GPUs) availability.
-   **Email Notifications:** Sends email alerts when a matching product is in stock or if the API is down.
-   **Configurable:** Allows customization of email settings, API URL, monitored GPUs, manufacturer, check interval, and maximum API failure count via a `config.ini` file.
-   **Robust URL Handling:** The base API URL and headers are configured in `config.ini`, with automatic handling of the locale.
-   **Logging:** Logs events and errors to `apimonitor.log` for debugging and monitoring, including detailed API responses and status codes.
- **Multiple GPU Support**: Monitors multiple GPUs

## Prerequisites

-   Python 3.7 or higher
-   A Gmail account for sending email notifications (or another SMTP server if you modify the `send_email` function)

## Installation

1.  **Clone the repository:**

    ```bash
    git clone <repository_url>
    cd <repository_name>
    ```

2.  **Create a virtual environment (recommended):**

    ```bash
    python3 -m venv .venv
    ```

3.  **Activate the virtual environment:**

    -   On Windows:

        ```bash
        .venv\Scripts\activate
        ```

    -   On macOS/Linux:

        ```bash
        source .venv/bin/activate
        ```

4.  **Install the required packages:**

    ```bash
    pip install -r requirements.txt
    ```
    (The `requirements.txt` file should contain: `requests`, `python-dotenv`, and `configparser`)

## Configuration

1.  **Create a Gmail App Password:**

    -   Go to your Google Account settings.
    -   Navigate to "Security" and then "2-Step Verification."  Make sure 2-Step Verification is enabled.
    -   At the bottom of the page, select "App passwords."
    -   Choose "Mail" as the app and "Other (Custom name)" as the device.
    -   Give it a name (e.g., "RTX 5090 Tracker") and click "Generate."
    -   Copy the generated 16-character app password.  **You won't see this password again, so store it securely.**

2.  **Configure `config.ini`:**

    -   Edit the `config.ini` file in the project's root directory.
    -   Modify the following sections and fields, replacing the placeholder values with your actual information:

    ```ini
    [API]
    base_api_url = https://api.nvidia.partners/edge/product/search?page=1&limit=12&locale={locale}&gpu=RTX%205090,RTX%205080&gpu_filter=RTX%205090~2,RTX%205080
    locale = sv-se

    [Headers]
    Host = api.nvidia.partners
    accept = application/json, text/javascript, */*; q=0.01
    accept-encoding = gzip, deflate, br, zstd
    accept-language = en-GB,en;q=0.9,en-US;q=0.8,sv;q=0.7,fi;q=0.6
    cache-control = no-cache
    content-type = application/json
    dnt = 1
    origin = https://marketplace.nvidia.com
    pragma = no-cache
    referer = https://marketplace.nvidia.com/
    sec-ch-ua = "Not A(Brand";v="8", "Chromium";v="132", "Microsoft Edge";v="132"
    sec-ch-ua-mobile = ?0
    sec-ch-ua-platform = "Windows"
    sec-fetch-dest = empty
    sec-fetch-mode = cors
    sec-fetch-site = same-site
    user-agent = Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 Edg/132.0.0.0

    [Email]
    product_email_subject = Product in Stock Alert
    down_email_subject = API Down Alert
    email_user = your_email@gmail.com
    email_password = your_app_password
    email_recipient = recipient_email@example.com

    [General]
    GPU = RTX 5090, RTX 5080
    manufacturer = NVIDIA
    check_interval = 25
    max_failures = 3
    ```

    -   **`[API]`**:
        -   `base_api_url`:  The base URL for the NVIDIA Partners API.  **Do not modify the placeholder `{locale}`**.  These are automatically filled in by the script.
        -   `locale`: The locale code for the NVIDIA marketplace you want to monitor (e.g., `fr-fr`, `sv-se`, `en-us`, `en-gb`, etc.).  See the NVIDIA marketplace website for available locales.

    -   **`[Headers]`**:
        -   These are the HTTP headers sent with the API request.  You generally shouldn't need to modify these unless the API's requirements change.  They are important for mimicking a legitimate browser request.

    -   **`[Email]`**:
        -   `product_email_subject`: The subject line for emails when a product is found in stock.
        -   `down_email_subject`: The subject line for emails when the API is down.
        -   `email_user`: Your Gmail address.
        -   `email_password`: The 16-character app password you generated.
        -   `email_recipient`: The email address where you want to receive notifications.

    -   **`[General]`**:
        -   `GPU`: A comma-separated list of GPU names to monitor (e.g., `RTX 5090, RTX 5080`).  The script will check for *any* of the listed GPUs - NOTE: These must match the response from the search API.
        -   `manufacturer`:  The manufacturer to filter by (e.g., `NVIDIA`). This is case-sensitive and must match the value returned by the API.
        -   `check_interval`: How often (in seconds) the script should check the API.  Don't set this too low, or you might get rate-limited by the API.  25 seconds is a reasonable starting point.
        -   `max_failures`:  The number of consecutive API call failures before an "API Down" email is sent.

## Usage

1.  **Run the script:**

    ```bash
    python gpu_checker_api.py
    ```

    The script will start monitoring the API and send email notifications based on the configured settings.  It will continue running until you manually stop it (e.g., with Ctrl+C).

## Troubleshooting

-   **Email Issues:** Ensure that your Gmail address and app password are correct in `config.ini`. Also, check your spam folder if you are not receiving notifications.  Make sure you have enabled "Less secure app access" in your Google Account settings *if* you are not using an app password (but using an app password is strongly recommended).
-   **API Errors:**  The script logs detailed error messages to `apimonitor.log`.  Check this file for any issues related to API calls (e.g., timeouts, invalid responses).
-   **Incorrect Filtering:**  If you're not getting notifications for products you expect, double-check the `GPU` and `manufacturer` values in `config.ini`.  Make sure they match the values returned by the API *exactly* (including case).  The debug logs will show you the exact values being checked.
- **Requirements:** Ensure all required libraries are installed.

## Testing the Email Functionality

To test the email functionality without waiting for a product to come into stock, you can temporarily modify the `config.ini` file to trigger an email:

1.  **API Down Simulation:**  To test the "API Down" email, change the `base_api_url` in the `[API]` section to an invalid URL (e.g., add an extra character).  Run the script; it should send an "API Down" email after the number of failures specified by `max_failures`.  **Remember to change the URL back to the correct value after testing.**

2.  **Product in Stock Simulation:** This is trickier, as we can't directly control the API response.  You could:
    *   **Temporarily modify the script:**  In the `process_api_response` function, *temporarily* comment out the `if` condition that checks for `manufacturer`, `gpu`, and `product_available`.  This will cause the script to treat *any* product returned by the API as a match, and it will send an email.  **Remember to uncomment the condition after testing.**  This is the most reliable way to test the "Product in Stock" email.
    *   **Monitor a product that is likely to be in stock:** If you know of a product that is frequently in stock, you could temporarily add its GPU name to the `GPU` list in `config.ini`.

## Disclaimer

This project is for educational and informational purposes only. The author is not responsible for any misuse or consequences resulting from the use of this script. The NVIDIA Partners API is subject to change, and this script may need to be updated accordingly. Use at your own risk.