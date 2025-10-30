import time
from selenium.common.exceptions import TimeoutException, NoSuchElementException, JavascriptException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
import io
import PyPDF2
from app.llm.data_processing import data_cleaning
import undetected_chromedriver as uc

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

    time.sleep(1)

    handle_popups(driver)

    scroll_page(driver)


    try:
        accordion_xpath = "//button[.//h3] | /div[@role='button' and @aria-expanded='false']"
        time.sleep(1)

        header_count = len(driver.find_elements(By.XPATH, accordion_xpath))
        print(f"Found {header_count} expandable button sections. Expanding one by one...")

        unique_pdf_urls = set()
        for i in range(header_count):
            try:
                all_headers = driver.find_elements(By.XPATH, accordion_xpath)

                if i >= len(all_headers):
                    print("Header list changed unexpectedly, stopping expand loop.")
                    break

                header_to_click = all_headers[i]
                header_text = header_to_click.text.splitlines()[0]

                print(f"Clicking header {i + 1}/{header_count}: {header_text}")

                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", header_to_click)
                time.sleep(0.3)
                driver.execute_script("arguments[0].click();", header_to_click)
                time.sleep(0.5)

                try:
                    time.sleep(2)
                    body_text = driver.find_element(By.TAG_NAME, "body").text
                    all_text_sources.append(body_text)
                except NoSuchElementException:
                    print("Could not find <body> tag.")

                close_button_xpath = "//button[@aria-label='Close Sheet']"
                try:
                    close_button = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.XPATH, close_button_xpath))
                    )

                    overlay_xpath = "//div[@role='dialog'][@aria-label]"
                    try:
                        overlay = WebDriverWait(driver, 5).until(
                            EC.visibility_of_element_located((By.XPATH, overlay_xpath))
                        )
                        print(f"Overlay '{header_text}' is open. Scraping its text...")
                        overlay_text = overlay.text
                        all_text_sources.append(overlay_text)  # Append ONLY the overlay text

                        overlay_pdfs = overlay.find_elements(By.XPATH, ".//a[contains(@href, '.pdf')]")
                        for pdf in overlay_pdfs:
                            if href := pdf.get_attribute('href'):
                                unique_pdf_urls.add(href)
                        print(f"Found {len(overlay_pdfs)} PDFs in overlay. Total unique PDFs: {len(unique_pdf_urls)}")
                    except Exception as e:
                        print(f"Could not find or scrape overlay content: {e}")

                    driver.execute_script("arguments[0].click();", close_button)
                    print(f"Clicked 'Close Sheet' button for '{header_text}'.")

                    WebDriverWait(driver, 10).until(
                        EC.invisibility_of_element_located((By.XPATH, close_button_xpath))
                    )
                    print("Overlay is closed.")
                    time.sleep(0.5)

                except TimeoutException:
                    print(f"No 'Close Sheet' overlay found for '{header_text}'. Assuming it was an in-page expand.")
                    pass

            except Exception as e:
                print(f"Could not click header {i} or its close button: {e}")

    except Exception as e:
        print(f"Error in main accordion header loop: {e}")

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
        time.sleep(2)
        body_text = driver.find_element(By.TAG_NAME, "body").text
        all_text_sources.append(body_text)
    except NoSuchElementException:
        print("Could not find <body> tag.")

    try:
        pdf_xpath = "//a[contains(@href, '.pdf')]"
        print("Looking for PDF section...")
        wait.until(EC.presence_of_element_located((By.XPATH, pdf_xpath)))

        pdf_elements = driver.find_elements(By.XPATH, pdf_xpath)
        pdf_urls = set(el.get_attribute('href') for el in pdf_elements if el.get_attribute('href'))
        print(f"Found {len(pdf_urls) + len(unique_pdf_urls)} unique PDFs after scrolling. Extracting text...")
        pdf_urls = pdf_urls.union(unique_pdf_urls)
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
    scroll_increment = last_height/5

    while True:
        driver.execute_script(f"window.scrollBy(0, {scroll_increment});")

        time.sleep(2.5)

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
       #  options = webdriver.ChromeOptions()
       #  options.add_argument("start-maximized")
       # #  options.add_argument("--headless")
       #  options.add_experimental_option("excludeSwitches", ["enable-automation"])
       #  options.add_experimental_option('useAutomationExtension', False)
       #  options.add_argument("--user-agent=Mozilla/5.0")
       #
       #  driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

        options = uc.ChromeOptions()
        options.add_argument("--no-first-run --no-service-autorun --password-store=basic")
        options.add_argument("--start-maximized")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) ...")

        driver = uc.Chrome(options=options)

    # stealth(driver,
    #         languages=["en-US", "en"],
    #         vendor="Google Inc.",
    #         platform="Win32",
    #         webgl_vendor="Intel Inc.",
    #         renderer="Intel Iris OpenGL Engine",
    #         fix_hairline=True,
    #         )
        session = requests.Session()
        session.headers.update({'User-Agent': driver.execute_script("return navigator.userAgent;")})
        all_page_text = get_all_page_content_stealth(BASE_HEADERS, driver, session, url)
        driver.close()
        return all_page_text
    except Exception as err:
        print(err)
        return ""

if __name__ == "__main__":
    BASE_HEADERS = {
        # 1. User-Agent: Keep it modern and specific
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',

        # 2. Accept Headers: Crucial for looking like a browser
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',  # Must be included
        'Upgrade-Insecure-Requests': '1',

        # 3. Sec-Fetch Headers: Modern fingerprinting signals
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',

        # 4. Standard Caching
        'Cache-Control': 'max-age=0'
    }
    text = try_selenium(BASE_HEADERS, "https://www.homedepot.com/p/GE-4-5-cu-ft-Top-Load-Washer-in-White-with-Dual-Action-Agitator-and-Cold-Plus-Sanitize-with-Oxi-GTW485ASWWB/328425526")
    clean_text = "\n".join(line.strip() for line in text.split() if line.strip())
    print(data_cleaning(clean_text))


# import time
# import random
# from selenium.common.exceptions import TimeoutException, NoSuchElementException, JavascriptException
# from selenium.webdriver.support.ui import WebDriverWait
# from selenium.webdriver.support import expected_conditions as EC
# import requests
# from selenium import webdriver
# from selenium.webdriver.common.by import By
# # from selenium.webdriver.chrome.service import Service # Not needed for Safari
# # from webdriver_manager.chrome import ChromeDriverManager # Not needed for Safari
# import io
# import PyPDF2
#
#
# # from selenium_stealth import stealth # This library is for Chrome-only
# # from app.llm.data_processing import data_cleaning # This module wasn't provided
#
# def extract_text_from_pdf(pdf_url: str, session: requests.Session) -> str | None:
#     """
#     Downloads a PDF from a URL using the provided session and extracts text from it.
#     Returns the text as a single string, or None if it fails.
#
#     Note: Removed BASE_HEADERS parameter. The session object already has the
#     correct User-Agent from the Safari driver.
#     """
#     try:
#         # The session already has the correct User-Agent.
#         # Passing headers= here would override it.
#         response = session.get(pdf_url, timeout=20)
#         response.raise_for_status()  # Check for 4xx/5xx errors
#
#         pdf_file = io.BytesIO(response.content)
#
#         reader = PyPDF2.PdfReader(pdf_file)
#
#         all_pdf_text = []
#         for page in reader.pages:
#             page_text = page.extract_text()
#             if page_text:
#                 all_pdf_text.append(page_text)
#
#         return "\n".join(all_pdf_text)
#
#     except PyPDF2.errors.PdfReadError:
#         print(f"Failed to read PDF (corrupt?): {pdf_url}")
#         return None
#     except requests.exceptions.RequestException as e:
#         print(f"Failed to download PDF {pdf_url}: {e}")
#         return None
#     except Exception as e:
#         print(f"An unknown error occurred during PDF extraction: {e}")
#         return None
#
#
# def handle_popups(driver: webdriver.Safari):
#     """Tries to find and click common cookie/promo close buttons."""
#
#     common_selectors = [
#         (By.XPATH, "//button[contains(translate(., 'ACCEPT', 'accept'), 'accept')]"),
#         # Matches "Accept", "ACCEPT", "accept all"
#         (By.XPATH, "//button[contains(translate(., 'CLOSE', 'close'), 'close')]"),  # Matches "Close", "CLOSE"
#         (By.XPATH, "//button[@aria-label='close' or @aria-label='Close']"),  # Common aria-label
#         (By.XPATH, "//div[contains(@class, 'modal')]//button[contains(@class, 'close')]"),
#         # Close button within a modal
#         (By.CSS_SELECTOR, "#onetrust-accept-btn-handler"),  # Common cookie banner ID
#     ]
#
#     print("Looking for popups/banners...")
#     for selector in common_selectors:
#         try:
#             button = WebDriverWait(driver, 2).until(
#                 EC.element_to_be_clickable(selector)
#             )
#             print(f"Found banner/popup button with selector: {selector}. Clicking...")
#             driver.execute_script("arguments[0].click();", button)
#             # Use randomized sleep to appear more human
#             time.sleep(random.uniform(0.5, 1.0))
#             print("Clicked banner/popup button.")
#         except TimeoutException:
#             pass
#         except Exception as e:
#             print(f"Error clicking banner button ({selector}): {e}")
#
#
# def get_all_page_content_stealth(driver: webdriver.Safari, session: requests.Session, url: str) -> str:
#     """
#     Uses Safari, scrolls, waits, expands, gets text from body, iframes, PDFs.
#     (Note: 'stealth' part is no longer active as it was Chrome-specific)
#     """
#     all_text_sources = []
#
#     try:
#         print(f"Navigating to {url} with Safari...")
#         driver.get(url)
#         wait = WebDriverWait(driver, 15)
#         # Wait for the body tag to be present
#         wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
#     except Exception as e:
#         print(f"Driver failed to get URL: {url}. Error: {e}")
#         return ""
#
#     time.sleep(random.uniform(1.0, 2.0))  # Wait for popups
#
#     handle_popups(driver)
#
#     scroll_page(driver)
#
#     # Get body text once after scrolling
#     try:
#         body_text = driver.find_element(By.TAG_NAME, "body").text
#         all_text_sources.append(body_text)
#     except NoSuchElementException:
#         print("Could not find <body> tag.")
#
#     try:
#         accordion_xpath = "//button[.//h3] | //div[@role='button' and @aria-expanded='false']"
#         time.sleep(random.uniform(0.5, 1.0))
#
#         header_count = len(driver.find_elements(By.XPATH, accordion_xpath))
#         print(f"Found {header_count} expandable button sections. Expanding one by one...")
#
#         unique_pdf_urls = set()
#         for i in range(header_count):
#             try:
#                 all_headers = driver.find_elements(By.XPATH, accordion_xpath)
#
#                 if i >= len(all_headers):
#                     print("Header list changed unexpectedly, stopping expand loop.")
#                     break
#
#                 header_to_click = all_headers[i]
#                 header_text = header_to_click.text.splitlines()[0] if header_to_click.text else "[No Text Header]"
#
#                 print(f"Clicking header {i + 1}/{header_count}: {header_text}")
#
#                 driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", header_to_click)
#                 time.sleep(random.uniform(0.3, 0.6))
#                 driver.execute_script("arguments[0].click();", header_to_click)
#                 time.sleep(random.uniform(0.5, 1.0))
#
#                 # Note: Scraping the *entire* body text on every click is inefficient
#                 # and was commented out in the previous version.
#                 # This logic now relies on finding an overlay.
#
#                 close_button_xpath = "//button[@aria-label='Close Sheet']"
#                 try:
#                     close_button = WebDriverWait(driver, 10).until(
#                         EC.element_to_be_clickable((By.XPATH, close_button_xpath))
#                     )
#
#                     overlay_xpath = "//div[@role='dialog'][@aria-label]"
#                     try:
#                         overlay = WebDriverWait(driver, 5).until(
#                             EC.visibility_of_element_located((By.XPATH, overlay_xpath))
#                         )
#                         print(f"Overlay '{header_text}' is open. Scraping its text...")
#                         overlay_text = overlay.text
#                         all_text_sources.append(overlay_text)  # Append ONLY the overlay text
#
#                         overlay_pdfs = overlay.find_elements(By.XPATH, ".//a[contains(@href, '.pdf')]")
#                         for pdf in overlay_pdfs:
#                             if href := pdf.get_attribute('href'):
#                                 unique_pdf_urls.add(href)
#                         print(f"Found {len(overlay_pdfs)} PDFs in overlay. Total unique PDFs: {len(unique_pdf_urls)}")
#                     except Exception as e:
#                         print(f"Could not find or scrape overlay content: {e}")
#
#                     driver.execute_script("arguments[0].click();", close_button)
#                     print(f"Clicked 'Close Sheet' button for '{header_text}'.")
#
#                     WebDriverWait(driver, 10).until(
#                         EC.invisibility_of_element_located((By.XPATH, close_button_xpath))
#                     )
#                     print("Overlay is closed.")
#                     time.sleep(random.uniform(0.5, 0.8))
#
#                 except TimeoutException:
#                     print(f"No 'Close Sheet' overlay found for '{header_text}'. Assuming it was an in-page expand.")
#                     pass
#
#             except Exception as e:
#                 print(f"Could not click header {i} or its close button: {e}")
#
#     except Exception as e:
#         print(f"Error in main accordion header loop: {e}")
#
#     try:
#         print("Looking for Salsify iframe...")
#         iframe_id = "salsify-key-features-summary"
#         wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, iframe_id)))
#
#         print("Switched into iframe. Waiting for body...")
#         wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
#
#         iframe_text = driver.find_element(By.TAG_NAME, "body").text
#         all_text_sources.append(iframe_text)
#
#     except TimeoutException:
#         print("Iframe (salsify-key-features-summary) did not load in time, even after scrolling.")
#     except Exception as e:
#         print(f"Error processing iframe: {e}")
#     finally:
#         driver.switch_to.default_content()
#
#     try:
#         pdf_xpath = "//a[contains(@href, '.pdf')]"
#         print("Looking for PDF section...")
#         # Wait for at least one PDF link
#         wait.until(EC.presence_of_element_located((By.XPATH, pdf_xpath)))
#
#         pdf_elements = driver.find_elements(By.XPATH, pdf_xpath)
#         pdf_urls = set(el.get_attribute('href') for el in pdf_elements if el.get_attribute('href'))
#
#         # Add URLs found in overlays
#         pdf_urls.update(unique_pdf_urls)
#
#         print(f"Found {len(pdf_urls)} unique PDFs. Extracting text...")
#
#         for pdf_url in pdf_urls:
#             # Add a random delay before each PDF request to be polite
#             time.sleep(random.uniform(1.0, 2.5))
#             # Pass the session, not the old BASE_HEADERS
#             pdf_text = extract_text_from_pdf(pdf_url, session)
#             if pdf_text:
#                 all_text_sources.append(pdf_text)
#
#     except TimeoutException:
#         print("PDF section did not load or no PDFs found.")
#     except Exception as e:
#         print(f"Error extracting PDF text: {e}")
#
#     print("Combining all text sources.")
#     return "\n\n--- SEPARATOR ---\n\n".join(all_text_sources)
#
#
# def scroll_page(driver: webdriver.Safari):
#     """Scrolls down the page gradually to trigger lazy loading."""
#     print("Scrolling down to load content...")
#     last_height = driver.execute_script("return document.body.scrollHeight")
#
#     while True:
#         # Scroll a random amount
#         scroll_increment = random.randint(400, 700)
#         driver.execute_script(f"window.scrollBy(0, {scroll_increment});")
#
#         # Wait a random amount
#         time.sleep(random.uniform(1.5, 2.5))
#
#         try:
#             new_height = driver.execute_script("return document.body.scrollHeight")
#             if new_height == last_height:
#                 print("Reached bottom of page.")
#                 break  # Exit loop if scroll height hasn't changed
#             last_height = new_height
#         except JavascriptException as e:
#             print(f"Error getting scroll height: {e}. Assuming bottom.")
#             break
#
#
# def try_selenium(BASE_HEADERS, url):
#     try:
#         # Safari options are very limited and often not needed.
#         # options = webdriver.SafariOptions()
#         # All the Chrome-specific options are removed.
#
#         # SafariDriver is built into macOS.
#         # Make sure "Allow Remote Automation" is enabled in Safari's Develop menu.
#         print("Starting Safari driver... Make sure 'Allow Remote Automation' is on.")
#         driver = webdriver.Safari()
#         driver.maximize_window()
#
#         # The 'stealth' function is Chrome-specific and must be removed.
#         # This makes the script much more detectable.
#         print("WARNING: selenium-stealth is not compatible with Safari.")
#         # stealth(driver, ...) # This line is removed.
#
#         session = requests.Session()
#         # This is great: update the session to use Safari's User-Agent
#         safari_user_agent = driver.execute_script("return navigator.userAgent;")
#         print(f"Using User-Agent: {safari_user_agent}")
#         session.headers.update({'User-Agent': safari_user_agent})
#
#         # Pass the driver and session to the main logic
#         all_page_text = get_all_page_content_stealth(driver, session, url)
#
#         driver.quit()  # Use quit() instead of close() to end the session
#         return all_page_text
#     except Exception as err:
#         print(f"An error occurred in try_selenium: {err}")
#         return ""
#
#
# if __name__ == "__main__":
#     # This is now just a fallback header for the session,
#     # as it gets overwritten by the driver's actual User-Agent.
#     BASE_HEADERS = {
#         'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0',
#         "Accept-Language": "en-US,en;q=0.9",
#     }
#
#     # URL from your previous example
#     test_url = "https://www.homedepot.com/p/GE-4-5-cu-ft-Top-Load-Washer-in-White-with-Dual-Action-Agitator-and-Cold-Plus-Sanitize-with-Oxi-GTW485ASWWB/328425526"
#
#     text = try_selenium(BASE_HEADERS, test_url)
#
#     if text:
#         # Assuming data_cleaning is a function you have in that module
#         # clean_text = data_cleaning(text)
#
#         # Using a simple cleaner since data_cleaning isn't available
#         clean_text_lines = [line.strip() for line in text.splitlines() if line.strip()]
#         clean_text = "\n".join(clean_text_lines)
#
#         print("--- CLEANED TEXT ---")
#         print(clean_text)
#     else:
#         print("No text was extracted.")
