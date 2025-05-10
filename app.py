import logging
import time
from typing import Literal
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.remote.webdriver import WebDriver

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class Account:
    def __init__(self, username: str, password: str):
        self._username = username
        self._password = password
        self._following: list[str] = []
        self._followers: list[str] = []
        self._not_followed_by: list[str] = []
        self._not_following_back: list[str] = []

    def get_username(self) -> str:
        """Returns the username of the account."""
        return self._username

    def get_password(self) -> str:
        """Returns the password of the account."""
        return self._password

    def get_collection(self, collection_name: Literal["following", "followers", "not_followed_by", "not_following_back"]) -> list[str]:
        """Retrieves a collection of users (followers, following, etc.) by name."""
        collection = f"_{collection_name}"
        return self[collection]

    def get_total_from_collection(self, collection_name: Literal["following", "followers", "not_followed_by", "not_following_back"]) -> int:
        """Returns the total number of users in a specified collection."""
        collection = f"_{collection_name.strip().lower()}"
        return len(self[collection])

    def add_users_to_collection(self, usernames: list[str], collection_name: Literal["following", "followers"]) -> int:
        """Adds a list of usernames to a specified collection."""
        collection = f"_{collection_name.strip().lower()}"
        self[collection].extend(usernames)
        return len(usernames)

    def eval_not_followed_by(self) -> list[str]:
        """Evaluates and returns the list of users who are not following the account back."""
        self._not_followed_by = list(set(self._following) - set(self._followers))
        return self._not_followed_by

    def eval_not_following_back(self) -> list[str]:
        """Evaluates and returns the list of users the account is not following back."""
        self._not_following_back = list(set(self._followers) - set(self._following))
        return self._not_following_back


class Browser:
    def __init__(self, driver: WebDriver, base_url: str):
        self.driver = driver
        self.base_url = base_url

    def __getattr__(self, name):
        return getattr(self.driver, name)

    def close(self) -> None:
        """Closes the browser and cleans up cookies."""
        logger.info("Closing browser and cleaning up...")
        self.driver.delete_all_cookies()
        self.driver.quit()

    def get_base_url(self) -> str:
        """Returns the base URL"""
        return self.base_url

    def navigate(self, path: str) -> None:
        """Navigates to a specific path on Instagram."""
        if not path.endswith("/"):
            path += "/"
        url = self.get_base_url() + path
        logger.info(f"Navigating to {url}")
        self.driver.get(url)


class Instasight:
    def __init__(self, browser: Browser, account: Account):
        self.browser = browser
        self.account = account

    def login(self) -> bool:
        """Logs into Instagram using the provided credentials."""
        try:
            self.browser.navigate("/accounts/login/")
            time.sleep(5)
            logger.info("Attempting to log in...")
            username_input = self.browser.find_element(By.NAME, "username")
            password_input = self.browser.find_element(By.NAME, "password")
            username_input.send_keys(self.account.get_username())
            password_input.send_keys(self.account.get_password() + Keys.RETURN)
            time.sleep(10)
            try:
                mfa_input = browser.find_element(By.NAME, "verificationCode")
                mfa_code = input("Enter the 2FA code: ")
                mfa_input.send_keys(mfa_code + Keys.RETURN)
                time.sleep(5)
            except NoSuchElementException:
                logger.info("2FA not required.")
            logger.info("Login successful.")
            return True
        except NoSuchElementException as e:
            logger.error(f"Login failed: {e}")
            return False

    def fetch_users(self, from_collection: Literal["following", "followers"]) -> None:
        """Fetches the Instagram users from a given collection (followings or followers)."""
        try:
            self.browser.navigate(f"/{self.account.get_username()}")
            time.sleep(5)
            logger.info(f"Fetching users from {from_collection}...")
            try:
                collection_link = self.browser.find_element(By.PARTIAL_LINK_TEXT, from_collection)
            except NoSuchElementException:
                collection_link = self.browser.find_element(By.XPATH, f'//a[@href="{self.browser.get_base_url()}/{self.account.get_username()}/{from_collection}"]')
            if not collection_link:
                raise Exception(f'"{from_collection}" collection not found. Please try again later.')
            collection_link.click()
            time.sleep(5)
            collection_dialog = self.browser.find_element(By.XPATH, "//div[@role='dialog']//ul")
            if not collection_dialog:
                collection_link.send_keys(Keys.RETURN)
            for _ in range(10):
                self.browser.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", collection_dialog)
                time.sleep(2)
                users_chunk = collection_dialog.find_elements(By.TAG_NAME, "a")
                usernames = [u.text for u in users_chunk if u.text.strip()]
                self.account.add_users_to_collection(usernames, from_collection)
            logger.info(f'Fetched {self.account.get_total_from_collection(from_collection)} user(s) from "{from_collection}".')
        except Exception as e:
            logger.error(f'Error fetching users from "{from_collection}" collection: {e}')

    def save_to_file(self, filename: str, data: list[str]) -> None:
        """Saves a list of strings to a text file."""
        try:
            with open(filename, "w") as file:
                file.write("\n".join(data))
            logger.info(f"Data successfully written to {filename}")
        except Exception as e:
            logger.error(f"Failed to write to {filename}: {e}")


if __name__ == "__main__":
    try:
        account = Account(
            input("Enter your username: ").strip(),
            input("Enter your password: ").strip()
        )
        browser = Browser(webdriver.Chrome(), "https://www.instagram.com")
        app = Instasight(browser, account)
        if not app.login():
            raise Exception("Authentication failed. Please try again later.")
        app.fetch_users(account.get_username(), "followers")
        app.fetch_users(account.get_username(), "following")
        app.save_to_file("not_followed_by.txt", account.eval_not_followed_by())
        app.save_to_file("not_following_back.txt", account.eval_not_following_back())
        logger.info("Analysis successfully completed. Results saved to text files.")
    except Exception as e:
        logger.error(f"An error occurred during runtime: {e}")
    finally:
        browser.close()
