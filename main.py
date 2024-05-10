import os
from flask import Flask
import logging
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
logging.basicConfig(level=logging.DEBUG)
load_dotenv()

app = Flask(__name__)

def scrape_url(session, url, proxy):
    try:
        formatted_proxy_url = f'http://{proxy["username"]}:{proxy["password"]}@{proxy["proxy_address"]}:{proxy["port"]}'

        session.proxies = {"http": formatted_proxy_url, "https": formatted_proxy_url}
        session.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "DNT": "1", 
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Referer": "https://www.google.com/"  
        }
        response = session.get(url)
        response.raise_for_status()
        return BeautifulSoup(response.text, 'html.parser')
    except requests.exceptions.RequestException as e:
        logging.error(f"Error accessing {url} with proxy {proxy}: {e}")
        return None


def fetch_job_details(session, job_data, proxy):
    job_url = os.getenv('SCRAPE_URL') + '/viewjob?jk=' + job_data['href']  # job details url to scrape
    job_soup = scrape_url(session, job_url, proxy)  # returns the HTML parsed with BeautifulSoup

    if not job_soup:
        return None

    try:
        job_details = {}

        # job title
        title_container = job_soup.find('h1', class_='jobsearch-JobInfoHeader-title')
        job_details['title'] = title_container.get_text(strip=True) if title_container else 'No title found'

        # ompany name
        company_container = job_soup.find('div', attrs={"data-testid": "jobsearch-CompanyInfoContainer"})
        job_details['company'] = company_container.find('a').get_text(strip=True) if company_container else 'No company found'

        # job location
        location_container = job_soup.find('div', id='jobLocationText')
        job_details['location'] = location_container.get_text(strip=True) if location_container else 'No location found'

        # benefits
        benefits_container = job_soup.find('div', id='benefits')
        if benefits_container:
            benefits = benefits_container.find_all('li')
            job_details['benefits'] = [benefit.get_text(strip=True) for benefit in benefits]
        else:
            job_details['benefits'] = 'No benefits found'

        # job description as raw HTML
        description_container = job_soup.find('div', id='jobDescriptionText')
        job_details['description_html'] = str(description_container) if description_container else 'No description found'

        # apply link
        apply_container = job_soup.find('div', id='applyButtonLinkContainer')
        if apply_container and apply_container.button and apply_container.button.has_attr('href'):
            job_details['apply_link'] = apply_container.button['href']
        else:
            job_details['apply_link'] = os.getenv('SCRAPE_URL') + '/viewjob?jk=' + job_data['href']

        return job_details
    except Exception as e:
        logging.error(f"Failed to process job {job_url}: {e}")
        return None


def fetch_jobs(proxies, target_url):
    jobs_data = []

    with ThreadPoolExecutor(max_workers=1) as executor:
            for proxy in proxies:
                if not proxy['valid']:
                    logging.info("Invalid Proxy")
                    continue
                # create one session per proxy
                session = requests.Session()  
                
                data = scrape_url(session, target_url, proxy)
                if data:
                    job_list = data.find('div', id='mosaic-jobResults')
                    job_list = job_list.find('ul')
                    if job_list:
                        jobs = job_list.find_all('li')
                        futures = []
                        for job in jobs:
                            link = job.find('h2', class_="jobTitle").find("a")
                            if link and link.has_attr('href'):
                                # link['data-jk'] - job ID
                                fetch_job_details(session, {'href': link['data-jk']}, proxy)
                                # future = executor.submit(fetch_job_details, session, {'href': link['href']}, proxy)
                                futures.append(future)

                        # collect results from futures
                        for future in futures:
                            job_data = future.result()
                            if job_data:
                                jobs_data.append(job_data)

                        successful_fetch = True
                        break  # bvreak if successful with proxy

            if not successful_fetch:
                logging.error(f"Failed to fetch jobs from all proxies.")
    return jobs_data






@app.route('/')
def home():
    api_key = os.getenv('PROXY_API_SECRET')
    # fetch proxy list
    proxies = requests.get(
        "https://proxy.webshare.io/api/v2/proxy/list/?mode=direct&page=1&page_size=50&country_code__in=US,CA",
        headers={"Authorization": f"Token {api_key}"}
    )
    proxies = proxies.json()['results']
    role = "javascript"
    location = "Colorado"
    scrape_url = os.getenv('SCRAPE_URL')
    url = f"{scrape_url}/jobs?q={role}&l={location}&from=searchOnDesktopSerp"
    jobs = fetch_jobs(proxies, url)
    return "OK"

x = home()
print(x)