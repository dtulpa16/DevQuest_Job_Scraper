import os
from flask import Flask
import logging
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
import json
import re
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

def extract_json_data(soup):
    # Find the script tag that contains the `window._initialData`
    for script in soup.find_all('script'):
        if 'window._initialData' in script.text:
            # Improved Regex pattern to robustly find JSON object
            pattern = re.compile(r'window\._initialData\s*=\s*(\{.*?\});', re.DOTALL)
            match = pattern.search(script.text)
            if match:
                # Using json.loads to parse the JSON string
                try:
                    json_data = json.loads(match.group(1))
                    return json_data
                except json.JSONDecodeError as e:
                    print("Error decoding JSON:", e)
    
    return None

#Scrapes a single job
def fetch_job_details(session, job_data, proxy):
    # job_url = os.getenv('SCRAPE_URL') + '/viewjob?jk=' + job_data['href']  # job details url to scrape
    job_url = os.getenv('SCRAPE_URL') + '/viewjob?jk=' + '30eb562caef8a2a6' # job details url to scrape
    job_soup = scrape_url(session, job_url, proxy)  # returns the HTML parsed with BeautifulSoup

    if not job_soup:
        return None
    
    json_data = extract_json_data(job_soup)
    try:
        job_details = {}
        
        job_details["employer_logo"] = json_data['jobInfoWrapperModel']['jobInfoModel']['jobInfoHeaderModel']['companyImagesModel']['logoUrl'] if json_data['jobInfoWrapperModel']['jobInfoModel']['jobInfoHeaderModel']['companyImagesModel']['logoUrl'] else None
        job_details["employer_name"] = json_data['hostQueryExecutionResult']['data']['jobData']['results'][0]['job']['sourceEmployerName'] if json_data['hostQueryExecutionResult']['data']['jobData']['results'][0]['job']['sourceEmployerName'] else json_data['jobInfoWrapperModel']['jobInfoModel']['jobInfoHeaderModel']['companyName']
        
        job_details["job_title"] = json_data['hostQueryExecutionResult']['data']['jobData']['results'][0]['job']['title'] or json_data['jobInfoWrapperModel']['jobInfoModel']['jobInfoHeaderModel']['jobTitle']
        
        job_details["job_apply_link"] = json_data['hostQueryExecutionResult']['data']['jobData']['results'][0]['job']['url'] if json_data['hostQueryExecutionResult']['data']['jobData']['results'][0]['job']['url'] else json_data['jobMetadataFooterModel']['originalJobLink']['href']
        
        # location
        job_details["job_city"] = json_data['hostQueryExecutionResult']['data']['jobData']['results'][0]['job']['location']['city'] if json_data['hostQueryExecutionResult']['data']['jobData']['results'][0]['job']['location']['city'] else json_data['hostQueryExecutionResult']['data']['jobData']['results'][0]['job']['location']['formatted']['short']
        if job_details["job_city"].lower() == "remote":
                job_details['job_is_remote'] = True
        
        #salary
        job_details["salary_text"] = json_data['salaryInfoModel']['salaryText'] if json_data['salaryInfoModel']['salaryText'] else 'None Provided'
        job_details["min_salary"] = json_data['salaryInfoModel']['salaryMin'] if json_data['salaryInfoModel']['salaryMin'] else 'None Provided'
        job_details["max_salary"] = json_data['salaryInfoModel']['salaryMax'] if json_data['salaryInfoModel']['salaryMax'] else 'None Provided'
        job_details["job_salary_currency"] = json_data['salaryInfoModel']['salaryCurrency'] if json_data['salaryInfoModel']['salaryCurrency'] else 'USD'
        
        
        job_details["job_description"] = json_data['hostQueryExecutionResult']['data']['jobData']['results'][0]['job']['description']['text'] if json_data['hostQueryExecutionResult']['data']['jobData']['results'][0]['job']['description']['text'] else json_data['hostQueryExecutionResult']['data']['jobData']['results'][0]['job']['description']['html']
        job_details["job_description_html"] = json_data['hostQueryExecutionResult']['data']['jobData']['results'][0]['job']['description']['html'] if json_data['hostQueryExecutionResult']['data']['jobData']['results'][0]['job']['description']['html'] else json_data['jobInfoWrapperModel']['jobInfoModel']['sanitizedJobDescription']

        benefits = json_data['benefitsModel']['benefits'] if json_data['benefitsModel']['benefits'] else json_data['hostQueryExecutionResult']['data']['jobData']['results'][0]['job']['benefits']
        job_details['job_benefits'] = benefits
        # if benefits:
        #     job_details['job_benefits'] = [benefit.label for benefit in benefits]
        # else:
        #     benefits = []

        job_details['job_age'] = json_data['hiringInsightsModel']['age'] or None

        # required_skills = json_data['hostQueryExecutionResult']['data']['jobData']['results'][0]['job']['attributes']
        # if required_skills:
        #     job_details['job_required_skills'] = [skill.label for skill in required_skills]
        # else:
        #     benefits = []

        #TODO - Get Required Skills
        # skills_container = job_soup.find('div', class_="js-match-insights-provider-kyg8or")
        # # skills_list = skills_container.find('ul',class_="js-match-insights-provider-18foz0k")
        # skills_list = job_soup.find_all('li', class_="js-match-insights-provider-o8j44y")
        # required_skills_list = []
        # for item in skills_list:
        #     full_text = item.get_text(strip=True)
        #     required_skills_list.append(full_text) 
        # job_details['job_required_skills'] = required_skills_list

        return job_details
    
    except Exception as e:
        logging.error(f"Failed to process job {job_url}: {e}")
        return None
    


# Scrapes list of jobs
def fetch_jobs(proxies, target_url):
    jobs_data = []

    with ThreadPoolExecutor(max_workers=1) as executor:
            for proxy in proxies:
                if not proxy['valid']:
                    logging.info("Invalid Proxy")
                    continue
                # create one session per proxy
                session = requests.Session()  
                test_data = fetch_job_details(session,"",proxy)

                data = scrape_url(session, target_url, proxy)
                if data:
                    jobs_data = []
                    job_list = data.find('div', id='mosaic-jobResults')
                    job_list = job_list.find('ul')
                    if job_list:
                        jobs = job_list.find_all('li')
                        futures = []
                        for job in jobs:
                            job_data = {}
                            # job id
                            link = job.find('h2', class_="jobTitle").find("a")
                            job_data['job_id'] = link['data-jk'] if link['data-jk'] else "no id"


                            if link and link.has_attr('href'):
                                pass
                                # link['data-jk'] - job ID
                                # fetch_job_details(session, {'href': link['data-jk']}, proxy)
                                # future = executor.submit(fetch_job_details, session, {'href': link['href']}, proxy)
                                # futures.append(future)

                        # collect results from futures
                        # for future in futures:
                        #     job_data = future.result()
                        #     if job_data:
                        #         jobs_data.append(job_data)

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