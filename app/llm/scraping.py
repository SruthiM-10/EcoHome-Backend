import time
from selenium.common.exceptions import TimeoutException, NoSuchElementException, JavascriptException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import io
import PyPDF2
from selenium_stealth import stealth

def extract_text_from_pdf(BASE_HEADERS, pdf_url: str, session: requests.Session) -> str | None:
    """
    Downloads a PDF from a URL and extracts all text from it.
    Returns the text as a single string, or None if it fails.
    """
    try:
        response = session.get(pdf_url, headers=BASE_HEADERS, timeout=20)
        response.raise_for_status()  # Check for 4xx/5xx errors

        pdf_file = io.BytesIO(response.content)

        reader = PyPDF2.PdfReader(pdf_file)

        all_pdf_text = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                all_pdf_text.append(page_text)

        return "\n".join(all_pdf_text)

    except PyPDF2.errors.PdfReadError:
        print(f"Failed to read PDF (corrupt?): {pdf_url}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Failed to download PDF {pdf_url}: {e}")
        return None
    except Exception as e:
        print(f"An unknown error occurred during PDF extraction: {e}")
        return None

def handle_popups(driver: webdriver.Chrome):
    """Tries to find and click common cookie/promo close buttons."""

    common_selectors = [
        (By.XPATH, "//button[contains(translate(., 'ACCEPT', 'accept'), 'accept')]"),  # Matches "Accept", "ACCEPT", "accept all"
        (By.XPATH, "//button[contains(translate(., 'CLOSE', 'close'), 'close')]"),  # Matches "Close", "CLOSE"
        (By.XPATH, "//button[@aria-label='close' or @aria-label='Close']"),  # Common aria-label
        (By.XPATH, "//div[contains(@class, 'modal')]//button[contains(@class, 'close')]"),  # Close button within a modal
        (By.CSS_SELECTOR, "#onetrust-accept-btn-handler"),  # Common cookie banner ID
    ]

    print("Looking for popups/banners...")
    for selector in common_selectors:
        try:
            button = WebDriverWait(driver, 2).until(
                EC.element_to_be_clickable(selector)
            )
            print(f"Found banner/popup button with selector: {selector}. Clicking...")
            driver.execute_script("arguments[0].click();", button)
            time.sleep(1)
            print("Clicked banner/popup button.")
        except TimeoutException:
            pass
        except Exception as e:
            print(f"Error clicking banner button ({selector}): {e}")

def get_all_page_content_stealth(BASE_HEADERS, driver: webdriver.Chrome, session: requests.Session, url: str) -> str:
    """
    Uses stealth, scrolls, waits, expands, gets text from body, iframes, PDFs.
    """
    all_text_sources = []

    try:
        print(f"Navigating to {url} with stealth...")
        driver.get(url)
        wait = WebDriverWait(driver, 15)
    except Exception as e:
        print(f"Driver failed to get URL: {url}. Error: {e}")
        return ""

    handle_popups(driver)

    scroll_page(driver)
    try:
        accordion_xpath = "//div[@role='button' and @aria-expanded='false']"
        time.sleep(1)
        closed_headers = driver.find_elements(By.XPATH, accordion_xpath)
        print(f"Found {len(closed_headers)} closed sections after scrolling. Expanding...")

        for header in closed_headers:
            try:
                driver.execute_script("arguments[0].scrollIntoView(true);", header)
                time.sleep(0.3)
                driver.execute_script("arguments[0].click();", header)
                time.sleep(0.5)
            except Exception as e:
                print(f"Could not click header: {e}")
    except Exception as e:
        print(f"Error finding accordion headers after scrolling: {e}")

    try:
        body_text = driver.find_element(By.TAG_NAME, "body").text
        all_text_sources.append(body_text)
    except NoSuchElementException:
        print("Could not find <body> tag.")

    try:
        print("Looking for Salsify iframe...")
        iframe_id = "salsify-key-features-summary"
        wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, iframe_id)))

        print("Switched into iframe. Waiting for body...")
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        iframe_text = driver.find_element(By.TAG_NAME, "body").text
        all_text_sources.append(iframe_text)

    except TimeoutException:
        print("Iframe (salsify-key-features-summary) did not load in time, even after scrolling.")
    except Exception as e:
        print(f"Error processing iframe: {e}")
    finally:
        driver.switch_to.default_content()


    try:
        pdf_xpath = "//h5[contains(text(), 'From the Manufacturer')]/following-sibling::ul[1]//a[contains(@href, '.pdf')]"
        print("Looking for PDF section...")
        wait.until(EC.presence_of_element_located((By.XPATH, pdf_xpath)))

        pdf_elements = driver.find_elements(By.XPATH, pdf_xpath)
        pdf_urls = set(el.get_attribute('href') for el in pdf_elements if el.get_attribute('href'))
        print(f"Found {len(pdf_urls)} unique PDFs after scrolling. Extracting text...")

        for pdf_url in pdf_urls:
            pdf_text = extract_text_from_pdf(BASE_HEADERS, pdf_url, session)
            if pdf_text:
                all_text_sources.append(pdf_text)

    except TimeoutException:
        print("PDF section 'From the Manufacturer' did not load in time, even after scrolling.")
    except Exception as e:
        print(f"Error extracting PDF text: {e}")

    print("Combining all text sources.")
    return "\n\n--- SEPARATOR ---\n\n".join(all_text_sources)

def scroll_page(driver: webdriver.Chrome):
    """Scrolls down the page gradually to trigger lazy loading."""
    print("Scrolling down to load content...")
    last_height = driver.execute_script("return document.body.scrollHeight")
    scroll_increment = 500

    while True:
        driver.execute_script(f"window.scrollBy(0, {scroll_increment});")

        time.sleep(5)

        try:
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                print("Reached bottom of page.")
                break  # Exit loop if scroll height hasn't changed
            last_height = new_height
        except JavascriptException as e:
            print(f"Error getting scroll height: {e}. Assuming bottom.")
            break

def try_selenium(BASE_HEADERS, url):
    try:
        options = webdriver.ChromeOptions()
        options.add_argument("start-maximized")
        # options.add_argument("--headless")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument("--user-agent=Mozilla/5.0")

        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

        stealth(driver,
                languages=["en-US", "en"],
                vendor="Google Inc.",
                platform="Win32",
                webgl_vendor="Intel Inc.",
                renderer="Intel Iris OpenGL Engine",
                fix_hairline=True,
                )

        session = requests.Session()
        session.headers.update({'User-Agent': driver.execute_script("return navigator.userAgent;")})
        all_page_text = get_all_page_content_stealth(BASE_HEADERS, driver, session, url)
        driver.close()
        return all_page_text
    except Exception as err:
        print(err)
        return ""