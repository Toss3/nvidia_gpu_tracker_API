import os
import time
import requests
import logging
from logging.handlers import TimedRotatingFileHandler
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
import configparser
from typing import Any, Dict, List, Optional


class Config:
    """
    A class to parse and manage configurations from a config.ini file.
    """

    def __init__(self, config_file: str = "config.ini"):
        """
        Initializes the Config object by reading the config.ini file.

        Args:
            config_file (str): The path to the configuration file. Defaults to "config.ini".
        """
        self.config: configparser.ConfigParser = configparser.ConfigParser(
            interpolation=None
        )  # Disable interpolation to prevent configparser from treating the % character as a special character for variable substitution
        self.config.read(config_file)
        self.base_api_url: str = self.config.get("API", "base_api_url")
        self.locale: str = self.config.get("API", "locale")
        self.inventory_api_url: str = self.config.get("API", "inventory_api_url")
        self.api_url: str = self.build_api_url()  # Build the full URL
        self.request_headers: Dict[str, str] = self._get_headers("Headers")
        self.inventory_request_headers: Dict[str, str] = self._get_inventory_headers() # Fix 2: Add inventory headers
        self.test_email_subject: str = self.config.get("Email", "test_email_subject")
        self.product_email_subject: str = self.config.get("Email", "product_email_subject")
        self.down_email_subject: str = self.config.get("Email", "down_email_subject")
        self.email_user: str = self.config.get("Email", "email_user")
        self.email_password: str = self.config.get("Email", "email_password")
        self.email_recipient: str = self.config.get("Email", "email_recipient")
        self.manufacturer: str = self.config.get("General", "manufacturer")
        # Get and process the list of GPUs to monitor
        self.gpus_to_monitor: List[str] = [
            gpu.strip() for gpu in self.config.get("General", "GPU").split(",")
        ]
        logger.debug(f"Monitoring GPUs: {self.gpus_to_monitor}")
        self.check_interval: int = self.config.getint("General", "check_interval")
        self.max_failures: int = self.config.getint("General", "max_failures")
        self.last_known_skus: Dict[str, str] = {}  # Initialize last_known_skus, {gpu: sku}
        self.sku_changed: Dict[str, bool] = {} # {gpu: bool}

        for gpu in self.gpus_to_monitor:
            self.last_known_skus[gpu] = ""  # Initialize last_known_skus for each GPU
            self.sku_changed[gpu] = False

    def _get_headers(self, section: str) -> Dict[str, str]:
        """Retrieves header values from specified section.

        Args:
            section (str): The section in the config file (e.g., "Headers").

        Returns:
            Dict[str, str]: A dictionary of headers.
        """
        headers: Dict[str, str] = {}
        for key, value in self.config.items(section):
            headers[key] = value
        logger.debug(f"Request Headers: {headers}")
        return headers

    def get_headers(self) -> Dict[str, str]:
        """Get the request headers for main API.

        Returns:
            Dict[str, str]: The request headers.
        """
        return self.request_headers

    def _get_inventory_headers(self) -> Dict[str, str]:
        """Returns specific headers for Inventory API requests."""
        return {
            "authority": "api.store.nvidia.com",
            "method": "GET",
            "path": "/partner/v1/feinventory?status=1&skus={sku}&locale={locale}", # Path will be updated in check_inventory_api
            "scheme": "https",
            "accept": "application/json, text/javascript, */*; q=0.01",
            "accept-encoding": "gzip, deflate, br, zstd",
            "accept-language": "en-US,en;q=0.9,sv;q=0.8",
            "content-type": "application/json",
            "origin": "https://marketplace.nvidia.com",
            "priority": "u=1, i",
            "referer": "https://marketplace.nvidia.com/",
            "sec-ch-ua": '"Not A(Brand";v="8", "Chromium";v="132", "Microsoft Edge";v="132"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"macOS"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 Edg/132.0.0.0",
        }


    def get_inventory_headers(self) -> Dict[str, str]:
        """Get the request headers for inventory API.

        Returns:
            Dict[str, str]: The inventory request headers.
        """
        return self.inventory_request_headers


    def build_api_url(self) -> str:
        """Builds the full API URL using the base URL and locale.

        Returns:
            str: The complete API URL.
        """

        # Construct the URL, replacing the locale
        url: str = self.base_api_url.replace("{locale}", self.locale)

        logger.debug(f"Constructed API URL: {url}")
        return url

    def build_inventory_api_url(self, sku: str) -> str:
        """Builds the inventory API URL with the given SKU and locale.

        Args:
            sku (str): The product SKU.

        Returns:
            str: The constructed inventory API URL.
        """
        url: str = self.inventory_api_url.replace("{locale}", self.locale).replace("{sku}", sku)
        logger.debug(f"Constructed Inventory API URL: {url}")
        return url

# Logger setup
def setup_logger() -> logging.Logger:
    """Sets up a logger that logs to both console and a daily rotating file.

    Returns:
        logging.Logger: Configured logger instance.
    """
    logger: logging.Logger = logging.getLogger("APIMonitor")
    logger.setLevel(logging.DEBUG)
    formatter: logging.Formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    # Console handler for important logs
    ch: logging.StreamHandler = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # File handler that rotates daily and keeps logs for the last 24 hours
    fh: TimedRotatingFileHandler = TimedRotatingFileHandler("apimonitor.log", when="D", interval=1, backupCount=1)
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    return logger


logger: logging.Logger = setup_logger()

# Load configuration
config: Config = Config()


def send_email(subject: str, body: str, html: bool = True) -> None:
    """Sends an email using Gmail's SMTP server.

    Args:
        subject (str): The email subject.
        body (str): The email body.
        html (bool, optional): Whether the email body is HTML. Defaults to True.
    """

    if not all([config.email_user, config.email_password, config.email_recipient]):
        logger.error("email_user, email_password, and email_recipient must be set in config.ini.")
        return

    logger.info(f"Preparing to send email to {config.email_recipient} with subject '{subject}'.")
    try:
        message: MIMEMultipart = MIMEMultipart()
        message["From"] = config.email_user
        message["To"] = config.email_recipient
        message["Subject"] = subject

        mime_type: str = "html" if html else "plain"
        message.attach(MIMEText(body, mime_type))

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.ehlo()
            server.starttls()
            server.login(config.email_user, config.email_password)
            server.send_message(message)
            logger.info("Email sent successfully.")
    except Exception as e:
        logger.error(f"Error sending email: {e}")


def check_api() -> Any:
    """Calls the API and returns the JSON response.

    Returns:
        Any: The JSON response if successful; otherwise, None.
    """
    try:
        response: requests.Response = requests.get(config.api_url, headers=config.get_headers(), timeout=10)
        response.raise_for_status()
        json_data: Any = response.json()
        logger.debug(f"API call successful. Status Code: {response.status_code},  JSON data received: {json_data}")
        return json_data
    except requests.exceptions.RequestException as e:
        logger.error(f"Error during API call: {e}")
        return None

def check_inventory_api(sku: str) -> bool:
    """Checks the inventory API for the given SKU.

    Args:
        sku (str): The product SKU.

    Returns:
        bool: True if the product is active, False otherwise.
    """
    url: str = config.build_inventory_api_url(sku)
    inventory_headers: Dict[str, str] = config.get_inventory_headers()
    inventory_headers['path'] = inventory_headers['path'].replace("{sku}", sku).replace("{locale}", config.locale) # Fix 3: Updated to use 'path' instead of ':path' # Fix 2: Update path with sku and locale
    inventory_headers['method'] = "GET"
    inventory_headers['scheme'] = "https"
    inventory_headers['authority'] = "api.store.nvidia.com"


    logger.debug(f"Inventory API Headers: {inventory_headers}")

    try:
        response: requests.Response = requests.get(url, headers=inventory_headers, timeout=10)
        response.raise_for_status()
        json_data: Any = response.json()
        logger.debug(f"Inventory API call successful. Status Code: {response.status_code}, JSON data: {json_data}")

        is_active: str = json_data.get("listMap", [{}])[0].get("is_active", "false")
        return is_active == "true"

    except requests.exceptions.RequestException as e:
        logger.error(f"Error during Inventory API call: {e}")
        return False

def process_api_response(api_response: Any) -> None:
    """Processes the initial API response to extract and check product SKUs.

    Args:
        api_response (Any): The JSON response from the initial API call.
    """
    try:
        products: Any = api_response.get("searchedProducts", {}).get("productDetails", [])
        if not products:
            logger.warning("No product details found in the API response.")
            return

        for product in products:
            gpu: str = product.get("gpu", "")
            manufacturer: str = product.get("manufacturer", "")
            product_sku: str = product.get("productSKU", "")

            logger.debug(
                f"Checking product: {product.get('productTitle')}, GPU: {gpu}, Manufacturer: {manufacturer}, SKU: {product_sku}"
            )

            # Filter by manufacturer and GPU
            if manufacturer == config.manufacturer and gpu in config.gpus_to_monitor:
                if product_sku != config.last_known_skus.get(gpu, ""):
                    if config.last_known_skus.get(gpu, "") == "":
                        logger.info(f"Sending test email {gpu}: {product_sku}")
                        body: str = f"<p>SKU set for {gpu} to: {product_sku}</p>"
                        send_email(config.test_email_subject, body)
                    elif config.last_known_skus.get(gpu, "") != "":
                        logger.info(f"New SKU detected for {gpu}: {product_sku}")
                        # Email for SKU Change
                        body: str = f"<p>SKU changed for {gpu} to: {product_sku}</p>"
                        send_email(config.product_email_subject, body)
                    else:
                        logger.info(f"Initial SKU detected for {gpu}: {product_sku}. No SKU change email sent on first run.") # Debugging first run

                    config.last_known_skus[gpu] = product_sku  # Update last_known_skus
                    config.sku_changed[gpu] = True # Set sku_changed to True

                if config.sku_changed[gpu]:
                    if check_inventory_api(product_sku):
                         # Find the first retailer and send email
                        retailers = product.get("retailers", [])
                        if retailers: # Check if retailers list is not empty
                            purchase_link: Optional[str] = retailers[0].get("purchaseLink") # Get the first retailer's purchase link
                            if purchase_link: # Check if purchase_link is not None
                                logger.info(f"Product with SKU {product_sku} is active and purchase link found. Sending email.") # Debugging
                                body: str = (
                                    f"<p>Product in stock! Link: "
                                    f"<a href='{purchase_link}'>Click here</a></p>"
                                )
                                send_email(config.product_email_subject, body)
                                config.sku_changed[gpu] = False  # Reset sku_changed after successful notification
                                return # We only send one email per new SKU and is_active
                            else:
                                logger.warning(f"No purchase link found for SKU {product_sku} even though inventory API returned active.") # Debugging
                        else:
                            logger.warning(f"No retailers found for SKU {product_sku} even though inventory API returned active.") # Debugging

                    else:
                        logger.debug(f"Product with SKU {product_sku} is not active.")

        logger.info("No new products in stock.")

    except Exception as e:
        logger.error(f"Error processing API response: {e}")
        logger.debug(f"Problematic API response: {api_response}")


def main() -> None:
    """Main loop that checks the API and sends email alerts."""
    failure_count: int = 0

    logger.info("Starting API monitoring...")
    while True:
        api_response: Any = check_api()

        if api_response is None:
            failure_count += 1
            logger.warning(f"API call failed. Current consecutive failures: {failure_count}")

            if failure_count >= config.max_failures:
                body: str = "<p>Alert: The API is down. Please check the API status and connectivity.</p>"
                send_email(config.down_email_subject, body)
                failure_count = 0
        else:
            failure_count = 0
            process_api_response(api_response)  # Process the API response

        logger.info(f"Waiting for {config.check_interval} seconds before the next API check.")
        time.sleep(config.check_interval)


if __name__ == "__main__":
    main()
