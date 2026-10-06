from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class BrowserStackClient:
    def __init__(self, username, access_key):
        self.username = username
        self.access_key = access_key
        self.driver = None

    def start_session(self, url, browser='chrome'):
        options = webdriver.ChromeOptions()
        options.set_capability('browserName', browser)
        options.set_capability('browserVersion', 'latest')
        options.set_capability('bstack:options', {
            'os': 'Windows',
            'osVersion': '11',
            'local': True,
            'seleniumVersion': '4.18.0',
        })
        self.driver = webdriver.Remote(
            command_executor=f'https://{self.username}:{self.access_key}@hub-cloud.browserstack.com/wd/hub',
            options=options
        )
        self.driver.get(url)
        return self.driver

    def click_ads(self, ad_selectors):
        for selector in ad_selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for element in elements:
                    if element.is_displayed() and element.is_enabled():
                        element.click()
                        WebDriverWait(self.driver, 2).until(
                            lambda d: d.execute_script("return document.readyState") == "complete"
                        )
            except Exception:
                continue

    def fill_form(self, form_data):
        for field_selector, value in form_data.items():
            try:
                field = self.driver.find_element(By.CSS_SELECTOR, field_selector)
                field.clear()
                field.send_keys(value)
            except Exception:
                continue
        try:
            submit = self.driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]')
            submit.click()
        except Exception:
            pass

    def close(self):
        if self.driver:
            self.driver.quit()