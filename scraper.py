import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re
import time
from django.utils.timezone import make_aware

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    from selenium.webdriver.common.action_chains import ActionChains
    from webdriver_manager.chrome import ChromeDriverManager
    from selenium.webdriver.chrome.service import Service
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False


class ReviewScraper:
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
    }

    @classmethod
    def _get_session(cls):
        session = requests.Session()
        session.headers.update(cls.HEADERS)
        return session

    @classmethod
    def scrape(cls, url, max_reviews=20):
        if 'trustpilot' in url.lower():
            return cls._scrape_trustpilot(url, max_reviews)
        elif 'google.com/maps' in url.lower():
            if not SELENIUM_AVAILABLE:
                return [{'reviewer': 'Error', 'rating': 0, 'content': 'Selenium not installed', 'date': None, 'avatar': None, 'is_verified': False, 'images': []}]
            return cls._scrape_google_maps(url, max_reviews)
        else:
            return cls._scrape_generic(url, max_reviews)

    @classmethod
    def _scrape_trustpilot(cls, url, max_reviews):
        # (same as before)
        session = cls._get_session()
        response = session.get(url, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        reviews = []
        containers = soup.select('div[data-service-review]')
        for container in containers[:max_reviews]:
            try:
                rating_elem = container.select_one('.star-rating')
                rating = len(rating_elem.find_all('svg')) if rating_elem else 0
                name_elem = container.select_one('.consumer-information__name')
                reviewer = name_elem.text.strip() if name_elem else 'Anonymous'
                avatar_elem = container.select_one('.consumer-avatar img')
                avatar_url = avatar_elem.get('src') if avatar_elem else None
                if avatar_url and avatar_url.startswith('//'):
                    avatar_url = 'https:' + avatar_url
                content_elem = container.select_one('.review-content p')
                content = content_elem.text.strip() if content_elem else ''
                date_elem = container.select_one('time')
                date_str = date_elem.get('datetime') if date_elem else None
                date = None
                if date_str:
                    try:
                        date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                        date = make_aware(date)
                    except:
                        pass
                verified_elem = container.select_one('.verified-purchase')
                is_verified = bool(verified_elem)
                reviews.append({
                    'reviewer': reviewer,
                    'rating': rating,
                    'content': content,
                    'date': date.strftime('%Y-%m-%d') if date else None,
                    'avatar': avatar_url,
                    'is_verified': is_verified,
                    'images': [],
                })
            except Exception as e:
                print(f"Trustpilot error: {e}")
                continue
        return reviews

    @classmethod
    def _scrape_google_maps(cls, url, max_reviews=20):
        if not SELENIUM_AVAILABLE:
            return [{'reviewer': 'Error', 'rating': 0, 'content': 'Selenium not installed', 'date': None, 'avatar': None, 'is_verified': False, 'images': []}]

        chrome_options = Options()
        # chrome_options.add_argument("--headless")  # Uncomment for headless
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        driver.set_page_load_timeout(10)

        reviews = []
        try:
            driver.get(url)
            time.sleep(4)

            # ========== ENHANCED REVIEWS TAB CLICK ==========
            clicked = False
            # 1) Wait for the tab to be present (longer wait)
            try:
                tab = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//button[contains(@aria-label,'Reviews')]"))
                )
                # Scroll into view and click with JS
                driver.execute_script("arguments[0].scrollIntoView(true);", tab)
                time.sleep(0.5)
                driver.execute_script("arguments[0].click();", tab)
                clicked = True
                print("✅ Reviews tab clicked (by aria-label).")
            except:
                pass

            # 2) Try by role='tab' and text
            if not clicked:
                try:
                    tab = WebDriverWait(driver, 8).until(
                        EC.element_to_be_clickable((By.XPATH, "//div[@role='tab'][contains(.,'Reviews')]"))
                    )
                    driver.execute_script("arguments[0].click();", tab)
                    clicked = True
                    print("✅ Reviews tab clicked (by role).")
                except:
                    pass

            # 3) Try by button text
            if not clicked:
                try:
                    tab = WebDriverWait(driver, 8).until(
                        EC.element_to_be_clickable((By.XPATH, "//button[contains(.,'Reviews')]"))
                    )
                    driver.execute_script("arguments[0].click();", tab)
                    clicked = True
                    print("✅ Reviews tab clicked (by button text).")
                except:
                    pass

            # 4) Try by class containing 'tab' and text
            if not clicked:
                try:
                    tab = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, "//div[contains(@class, 'tab')][contains(.,'Reviews')]"))
                    )
                    driver.execute_script("arguments[0].click();", tab)
                    clicked = True
                    print("✅ Reviews tab clicked (by class).")
                except:
                    pass

            # 5) Try any element with text 'Reviews' (JavaScript click)
            if not clicked:
                try:
                    elements = driver.find_elements(By.XPATH, "//*[contains(text(),'Reviews')]")
                    for elem in elements:
                        if elem.is_displayed() and elem.is_enabled():
                            driver.execute_script("arguments[0].click();", elem)
                            clicked = True
                            print("✅ Reviews tab clicked (by text search).")
                            break
                except:
                    pass

            # 6) If still not clicked, try to navigate to the reviews section via URL parameter
            if not clicked:
                try:
                    # Append '?hl=en' to force the reviews tab to load
                    current_url = driver.current_url
                    if '?' in current_url:
                        new_url = current_url + '&hl=en'
                    else:
                        new_url = current_url + '?hl=en'
                    driver.get(new_url)
                    time.sleep(3)
                    clicked = True
                    print("✅ Navigated to URL with '?hl=en'.")
                except:
                    pass

            if not clicked:
                print("⚠️ Could not click Reviews tab. Trying to scroll anyway...")

            # Wait for reviews to appear after click
            if clicked:
                time.sleep(4)
            else:
                time.sleep(2)

            # ========== FIND SCROLL PANEL ==========
            panel = None
            panel_selectors = [
                "//div[@role='feed']",
                "//div[contains(@class,'m6QErb') and contains(@class,'DxyBCb')]",
                "//div[contains(@class,'m6QErb') and @tabindex]",
                "//div[contains(@class,'m6QErb')]",
                "//div[contains(@class,'section-scrollbox')]",
            ]
            for xp in panel_selectors:
                try:
                    panel = driver.find_element(By.XPATH, xp)
                    if panel.is_displayed() and panel.size['height'] > 200:
                        print("✅ Found scroll panel.")
                        break
                except:
                    pass

            if not panel:
                with open('debug_no_panel.html', 'w', encoding='utf-8') as f:
                    f.write(driver.page_source)
                print("⚠️ No scroll panel found. Page saved to debug_no_panel.html")

            seen = set()
            already_clicked = set()
            total_extracted = 0
            no_new = 0
            scroll_count = 0
            max_scrolls = 3000

            while total_extracted < max_reviews and scroll_count < max_scrolls:
                scroll_count += 1

                # Expand "More" buttons
                more_buttons = driver.find_elements(By.XPATH,
                    "//button[contains(@aria-label,'See more')] | //span[contains(@class,'w8nwRe')] | //button[contains(.,'More')]")
                for btn in more_buttons:
                    try:
                        loc = btn.location
                        key = (round(loc['x']), round(loc['y']))
                        if key in already_clicked:
                            continue
                        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
                        time.sleep(0.1)
                        driver.execute_script("arguments[0].click();", btn)
                        already_clicked.add(key)
                        time.sleep(0.1)
                    except:
                        pass

                # Click "Show more" list button (if any)
                try:
                    load_more = driver.find_element(By.XPATH, "//button[contains(.,'Show more') or contains(.,'Load more') or contains(@aria-label,'Load more')]")
                    if load_more.is_displayed():
                        driver.execute_script("arguments[0].click();", load_more)
                        time.sleep(1)
                        print("🔄 Clicked 'Show more' list button.")
                except:
                    pass

                # ---------- CONTAINER SELECTION ----------
                containers = []

                # 1) Known classes
                class_list = [
                    "jftiEf", "bwb7ce", "WMbnJf", "MyEned",
                    "section-review", "review-container", "gws-localreviews__review",
                    "review-card", "review", "comment"
                ]
                for cls in class_list:
                    containers = driver.find_elements(By.CLASS_NAME, cls)
                    if containers:
                        break

                # 2) data-review-id
                if not containers:
                    containers = driver.find_elements(By.XPATH, "//div[@data-review-id]")
                    if containers:
                        print(f"🔍 Found {len(containers)} containers by data-review-id")

                # 3) Generic XPath (span + text)
                if not containers:
                    try:
                        containers = driver.find_elements(By.XPATH,
                            "//div[.//span[@role='img'] and .//div[text() and string-length(text()) > 20]]")
                        if containers:
                            print(f"🔍 Found {len(containers)} containers by generic XPath")
                    except:
                        pass

                if not containers and scroll_count == 1:
                    with open('debug_no_containers.html', 'w', encoding='utf-8') as f:
                        f.write(driver.page_source)
                    print("⚠️ No review containers found. Page saved to debug_no_containers.html")
                    break

                added_this_round = 0

                for container in containers:
                    try:
                        # ---- EXTRACT NAME ----
                        name = ""
                        for nc in ("Vpc5Fe", "d4r55", "al6Kxe", "lDqWXb", "reviewer-name"):
                            try:
                                name = container.find_element(By.CLASS_NAME, nc).text.strip()
                                if name:
                                    break
                            except:
                                pass
                        if not name:
                            try:
                                name = container.find_element(By.XPATH, ".//div[contains(@class, 'name') or contains(@class, 'reviewer')]").text.strip()
                            except:
                                pass
                        if not name:
                            try:
                                divs = container.find_elements(By.XPATH, ".//div[text() and string-length(text()) > 1]")
                                if len(divs) >= 2:
                                    name = divs[0].text.strip()
                            except:
                                pass

                        # ---- FILTER OUT INVALID ----
                        invalid_names = ["Saved", "Add", "Write", "Review", "Photos", ""]
                        if name in invalid_names:
                            continue

                        # ---- EXTRACT TEXT ----
                        text = ""
                        for tc in ("OA1nbd", "wiI7pd", "MyEned", "rsqaWe", "kZ91ed", "review-text"):
                            try:
                                text = container.find_element(By.CLASS_NAME, tc).text.strip()
                                if text:
                                    break
                            except:
                                pass
                        if not text:
                            try:
                                text = container.find_element(By.XPATH, ".//div[contains(@class, 'review') or contains(@class, 'text')]").text.strip()
                            except:
                                pass
                        if not text and name:
                            try:
                                divs = container.find_elements(By.XPATH, ".//div[text() and string-length(text()) > 20]")
                                if len(divs) >= 1:
                                    text = divs[0].text.strip()
                                    if name and text.startswith(name):
                                        text = text[len(name):].strip()
                            except:
                                pass
                        if not text:
                            text = container.text.strip()
                            if name and text.startswith(name):
                                text = text[len(name):].strip()

                        # ---- RATING ----
                        rating = 0
                        try:
                            rating_el = container.find_element(By.XPATH, ".//span[@role='img']")
                            aria = rating_el.get_attribute("aria-label") or ""
                            if aria:
                                match = re.search(r'(\d+\.?\d*)', aria)
                                if match:
                                    rating = int(float(match.group(1)))
                        except:
                            pass

                        # ---- AVATAR ----
                        avatar = ""
                        # (use the same 7 methods as before)
                        try:
                            img = container.find_element(By.XPATH,
                                ".//img[contains(@class, 'lDY1rd') or contains(@class, 'Nn7UJ') or contains(@class, 'wxB2Ff')]")
                            src = img.get_attribute("src")
                            if src and "lh3.googleusercontent.com" in src:
                                avatar = re.sub(r'=w\d+-h\d+.*$', '=w100-h100-p-rp-mo', src)
                        except:
                            pass
                        if not avatar:
                            try:
                                img = container.find_element(By.XPATH, ".//img[contains(@src, 'lh3.googleusercontent.com')]")
                                src = img.get_attribute("src")
                                if src:
                                    avatar = re.sub(r'=w\d+-h\d+.*$', '=w100-h100-p-rp-mo', src)
                            except:
                                pass
                        if not avatar:
                            try:
                                imgs = container.find_elements(By.XPATH,
                                    ".//img[not(contains(@src, 'star')) and not(contains(@src, 'placeholder'))]")
                                for img in imgs:
                                    src = img.get_attribute("src")
                                    if src and ("lh3.googleusercontent.com" in src or "googleusercontent" in src):
                                        avatar = re.sub(r'=w\d+-h\d+.*$', '=w100-h100-p-rp-mo', src)
                                        break
                            except:
                                pass
                        if not avatar:
                            try:
                                img = container.find_element(By.XPATH,
                                    ".//img[@data-original-src and contains(@data-original-src, 'googleusercontent')]")
                                src = img.get_attribute("data-original-src")
                                if src:
                                    avatar = re.sub(r'=w\d+-h\d+.*$', '=w100-h100-p-rp-mo', src)
                            except:
                                pass
                        if not avatar:
                            try:
                                img = container.find_element(By.XPATH,
                                    ".//img[@data-src and contains(@data-src, 'googleusercontent')]")
                                src = img.get_attribute("data-src")
                                if src:
                                    avatar = re.sub(r'=w\d+-h\d+.*$', '=w100-h100-p-rp-mo', src)
                            except:
                                pass
                        if not avatar:
                            try:
                                el = container.find_element(By.XPATH,
                                    ".//div[contains(@style, 'background-image') and contains(@style, 'googleusercontent')]")
                                style = el.get_attribute("style")
                                if style:
                                    match = re.search(r'url\(["\']?([^"\'\)]+)["\']?\)', style)
                                    if match:
                                        url_img = match.group(1)
                                        if "googleusercontent" in url_img:
                                            avatar = re.sub(r'=w\d+-h\d+.*$', '=w100-h100-p-rp-mo', url_img)
                            except:
                                pass
                        if not avatar:
                            try:
                                imgs = container.find_elements(By.XPATH, ".//img[contains(@src, 'google') and not(contains(@src, 'logo'))]")
                                for img in imgs:
                                    src = img.get_attribute("src")
                                    if src and "lh3.googleusercontent.com" in src:
                                        avatar = re.sub(r'=w\d+-h\d+.*$', '=w100-h100-p-rp-mo', src)
                                        break
                            except:
                                pass

                        # ---- DEDUPLICATION ----
                        review_id = container.get_attribute('data-review-id') or ''
                        key = review_id or (name + text + str(rating))

                        if key not in seen and name and text:
                            seen.add(key)
                            reviews.append({
                                'reviewer': name,
                                'rating': rating,
                                'content': text,
                                'date': None,
                                'avatar': avatar,
                                'is_verified': False,
                                'images': [avatar] if avatar else []
                            })
                            added_this_round += 1
                            total_extracted += 1

                            if total_extracted >= max_reviews:
                                break
                    except Exception as e:
                        continue

                print(f"📝 Scroll {scroll_count}: Added {added_this_round}, Total {total_extracted}")

                if total_extracted >= max_reviews:
                    break

                # ---------- SCROLL ----------
                if panel:
                    driver.execute_script("arguments[0].scrollTop += arguments[0].offsetHeight * 8;", panel)
                else:
                    driver.execute_script("window.scrollBy(0, 2000);")
                time.sleep(1.5)

                if added_this_round == 0:
                    no_new += 1
                    if no_new >= 30:
                        print("No new reviews after 30 scrolls. Stopping.")
                        break
                else:
                    no_new = 0

            if scroll_count >= max_scrolls:
                print(f"Reached max scrolls ({max_scrolls}). Stopping.")

        except Exception as e:
            print(f"Google Maps scraping error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            driver.quit()

        if not reviews:
            return [{
                'reviewer': 'Google Maps',
                'rating': 0,
                'content': 'No reviews found. Please ensure the URL is a valid Google Maps place page and the reviews are visible.',
                'date': None,
                'avatar': None,
                'is_verified': False,
                'images': []
            }]

        return reviews

    @classmethod
    def _scrape_generic(cls, url, max_reviews):
        session = cls._get_session()
        response = session.get(url, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        reviews = []
        selectors = ['.review', '.comment', '.customer-review', '.user-review', '.product-review', '.feedback']
        containers = []
        for sel in selectors:
            containers = soup.select(sel)
            if containers:
                break
        for container in containers[:max_reviews]:
            try:
                rating = 0
                rating_elem = container.select_one('.rating, .stars, .star-rating')
                if rating_elem:
                    stars = rating_elem.find_all('svg') or rating_elem.find_all('i', class_=re.compile(r'star'))
                    if stars:
                        rating = len(stars)
                    else:
                        match = re.search(r'(\d+)', rating_elem.text)
                        if match:
                            rating = int(match.group(1))
                rating = min(max(rating, 0), 5)
                name_elem = container.select_one('.author, .name, .reviewer')
                reviewer = name_elem.text.strip() if name_elem else 'Anonymous'
                avatar_elem = container.select_one('img.avatar, img.profile')
                avatar_url = avatar_elem.get('src') if avatar_elem else None
                content_elem = container.select_one('.content, .text, .description, .review-text')
                content = content_elem.text.strip() if content_elem else ''
                date_elem = container.select_one('time, .date, .timestamp')
                date_str = date_elem.get('datetime') if date_elem and hasattr(date_elem, 'get') else None
                if not date_str and date_elem:
                    date_str = date_elem.text.strip()
                date = None
                if date_str:
                    try:
                        date = datetime.strptime(date_str, '%Y-%m-%d')
                        date = date.strftime('%Y-%m-%d')
                    except:
                        try:
                            date = datetime.strptime(date_str, '%b %d, %Y')
                            date = date.strftime('%Y-%m-%d')
                        except:
                            pass
                images = []
                img_elems = container.select('img:not(.avatar):not(.profile)')
                for img in img_elems:
                    src = img.get('src')
                    if src and not src.startswith('data:'):
                        images.append(src)
                reviews.append({
                    'reviewer': reviewer,
                    'rating': rating,
                    'content': content,
                    'date': date,
                    'avatar': avatar_url,
                    'is_verified': False,
                    'images': images[:3],
                })
            except Exception:
                continue
        return reviews