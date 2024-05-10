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
    
def fetch_job_details(session, article_data, proxy):
    article_url = os.getenv('SCRAPE_URL') + '/viewjob?jk=' + article_data['href']
    article_soup = scrape_url(session, article_url, proxy)
    #! main container - <div class="jobsearch-JobComponent">
    # Job title - <h1 class="jobsearch-JobInfoHeader-title"> <span> Title </span> </h1>
    # Company name - <div data-testid="jobsearch-CompanyInfoContainer"> <a> Company name </a> </div>
    # Job Location - <div id="jobLocationText"> <span> Job Location </span> </div>
    # Benefits - <div id="benefits"> <li> benefit </li> <li> benefit </li> <li> benefit </li> <li> benefit </li> </div>
    # Job Description - <div id="jobDescriptionText"> *a lot of HTML. If possible, I want to grab all the raw HTML* </div>
    # Apply link - 
    
    if not article_soup:
        return None
    try:
       pass
    except Exception as e:
        logging.error(f"Failed to process article {article_url}: {e}")
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