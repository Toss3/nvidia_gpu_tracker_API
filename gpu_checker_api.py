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
        self.api_url: str = self.build_api_url()  # Build the full URL using Locale from config
        self.request_headers: Dict[str, str] = self._get_headers("Headers")
        self.product_email_subject: str = self.config.get("Email", "product_email_subject")
        self.down_email_subject: str = self.config.get("Email", "down_email_subject")
        self.check_interval: int = self.config.getint("General", "check_interval")
        self.max_failures: int = self.config.getint("General", "max_failures")
        # Get and process the list of GPUs to monitor
        self.gpus_to_monitor: List[str] = [
            gpu.strip() for gpu in self.config.get("General", "GPU").split(",")
        ]
        self.manufacturer: str = self.config.get("General", "manufacturer")
        self.email_user: str = self.config.get("Email", "email_user")
        self.email_password: str = self.config.get("Email", "email_password")
        self.email_recipient: str = self.config.get("Email", "email_recipient")
        logger.debug(f"Monitoring GPUs: {self.gpus_to_monitor}")

    def _get_headers(self, section: str) -> Dict[str, str]:
        """Retrieves header values.

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
        """Get the request headers.

        Returns:
            Dict[str, str]: The request headers.
        """
        return self.request_headers

    def build_api_url(self) -> str:
        """Builds the full API URL using the base URL and locale.

        Returns:
            str: The complete API URL.
        """

        # Construct the URL, replacing the locale
        url: str = self.base_api_url.replace("{locale}", self.locale)

        logger.debug(f"Constructed API URL: {url}")
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


def process_api_response(api_response: Any) -> Optional[str]:
    """Processes the API response, filtering by manufacturer, GPU, and availability.

    Args:
        api_response (Any): The JSON response from the API.

    Returns:
        Optional[str]: The purchase link if a matching, available product is found; None otherwise.
    """
    try:
        products: Any = api_response.get("searchedProducts", {}).get("productDetails", [])
        if not products:
            logger.warning("No product details found in the API response.")
            return None

        for product in products:
            gpu: str = product.get("gpu", "")
            product_available: bool = product.get("productAvailable", False)
            manufacturer: str = product.get("manufacturer", "")
            logger.debug(
                f"Checking product: {product.get('productTitle')}, GPU: {gpu}, Available: {product_available}, Manufacturer: {manufacturer}"
            )
            # Filter by manufacturer, GPU, and availability as specified in config
            if (
                manufacturer == config.manufacturer
                and gpu in config.gpus_to_monitor
                and product_available
            ):
                # Find the retailer with "isAvailable": true
                for retailer in product.get("retailers", []):
                    if retailer.get("isAvailable"):
                        purchase_link: str = retailer.get("purchaseLink")
                        logger.info(
                            f"Product {product.get('productTitle')} ({gpu}) is available at: {purchase_link}"
                        )
                        return purchase_link

        logger.info("No monitored products are currently available.")
        return None
    except Exception as e:
        logger.error(f"Error processing API response: {e}")
        logger.debug(f"Problematic API response: {api_response}")
        return None


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
            purchase_link: Optional[str] = process_api_response(api_response)
            if purchase_link:
                body: str = (
                    f"<p>Product in stock! Link: "
                    f"<a href='{purchase_link}'>Click here</a></p>"
                )
                send_email(config.product_email_subject, body)

        logger.info(f"Waiting for {config.check_interval} seconds before the next API check.")
        time.sleep(config.check_interval)


if __name__ == "__main__":
    main()