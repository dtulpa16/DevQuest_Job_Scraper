import os
from flask import Flask, jsonify, request
import logging
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
import json
import re
import lxml
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
        return BeautifulSoup(response.text, 'lxml')
    except requests.exceptions.RequestException as e:
        logging.error(f"Error accessing {url} with proxy {proxy}: {e}")
        return None

#! Helper to extract and parse intiialData for getting a single job's details
def extract_json_data(soup):
    # script tag that contains the `window._initialData` - holds json of job data
    for script in soup.find_all('script'):
        if 'window._initialData' in script.text:
            # find JSON object in intial data
            pattern = re.compile(r'window\._initialData\s*=\s*(\{.*?\});', re.DOTALL)
            match = pattern.search(script.text)
            if match:
                # parse the JSON string
                try:
                    json_data = json.loads(match.group(1))
                    return json_data
                except json.JSONDecodeError as e:
                    print("Error decoding JSON:", e)
    return None

#Scrapes a single job
def fetch_job_details(session, job_id, proxy):
    job_url = os.getenv('SCRAPE_URL') + '/viewjob?jk=' + job_id # job details url to scrape
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
       
        job_details['job_is_remote'] = True  if job_details["job_city"].lower() == "remote" else False
        
        #salary
        job_details["salary_text"] = json_data['salaryInfoModel']['salaryText'] if json_data['salaryInfoModel']['salaryText'] else 'None Provided'
        job_details["min_salary"] = json_data['salaryInfoModel']['salaryMin'] if json_data['salaryInfoModel']['salaryMin'] else 'None Provided'
        job_details["max_salary"] = json_data['salaryInfoModel']['salaryMax'] if json_data['salaryInfoModel']['salaryMax'] else 'None Provided'
        job_details["job_salary_currency"] = json_data['salaryInfoModel']['salaryCurrency'] if json_data['salaryInfoModel']['salaryCurrency'] else 'USD'
        
        
        job_details["job_description"] = json_data['hostQueryExecutionResult']['data']['jobData']['results'][0]['job']['description']['text'] if json_data['hostQueryExecutionResult']['data']['jobData']['results'][0]['job']['description']['text'] else json_data['hostQueryExecutionResult']['data']['jobData']['results'][0]['job']['description']['html']
        job_details["job_description_html"] = json_data['hostQueryExecutionResult']['data']['jobData']['results'][0]['job']['description']['html'] if json_data['hostQueryExecutionResult']['data']['jobData']['results'][0]['job']['description']['html'] else json_data['jobInfoWrapperModel']['jobInfoModel']['sanitizedJobDescription']

        try:
            benefits = json_data['hostQueryExecutionResult']['data']['jobData']['results'][0]['job']['benefits'] if json_data['hostQueryExecutionResult']['data']['jobData']['results'][0]['job']['benefits'] else json_data['benefitsModel']['benefits']
            labels = [attr.get('label') for attr in benefits]
            job_details['job_benefits'] = labels
        except:
            job_details['job_benefits'] = []
        

        job_details['job_age'] = json_data['hiringInsightsModel']['age'] or None

        required_skills = json_data['hostQueryExecutionResult']['data']['jobData']['results'][0]['job']['attributes']
        if required_skills:
            skills_labels = [attr.get('label') for attr in required_skills]
            job_details['attributes'] = skills_labels
        else:
            job_details['attributes'] = []

        return job_details
    
    except Exception as e:
        logging.error(f"Failed to process job {job_url}: {e}")
        return None
    

# Grabs JSON Metadata from initialData - Used for Job List
def extract_metadata(html_content):
    script_tag = html_content.find('script', {'id': 'mosaic-data'})  

    if script_tag:
        script_content = script_tag.string
        pattern = re.compile(r'window\.mosaic\.providerData\["mosaic-provider-jobcards"\]\s*=\s*(\{.*?\});', re.DOTALL)
        match = pattern.search(script_content)
        if match:
            # Directly parse the JSON object for "mosaic-provider-jobcards"
            jobcards_data = json.loads(match.group(1))
            # Access 'metaData' directly from this object
            metadata = jobcards_data.get("metaData", {})
            return jobcards_data['metaData']['mosaicProviderJobCardsModel']['results'] if jobcards_data['metaData']['mosaicProviderJobCardsModel']['results'] else None
    return None


# Scrapes list of jobs
def fetch_jobs(proxies, target_url):
    jobs_data = []

    with ThreadPoolExecutor(max_workers=1) as executor:
            successful_fetch = False
            for proxy in proxies:
                if not proxy['valid']:
                    logging.info("Invalid Proxy")
                    continue
                session = requests.Session()  
                data = scrape_url(session, target_url, proxy)

                json_data = extract_metadata(data)
                if json_data:
                    jobs_data = []
                    for job in json_data:
                        job_data = {}
                        job_data['job_id'] = job.get('jobkey', 'No Job ID')
                        job_data['job_title'] = job.get('displayTitle') or job.get('title', 'Unknown Title')
                        job_data['employer_name'] = job.get('company', 'Unknown Company')
                        job_data['job_city'] = job.get('formattedLocation') or job.get('jobLocationCity', 'Unknown Location')

                        
                        remote_work_model = job.get('remoteWorkModel', {})
                        job_data['job_is_remote'] = "remote" in remote_work_model.get('text', '').lower()

                        # salary 
                        extracted_salary = job.get('extractedSalary', {})
                        estimated_salary = job.get('estimatedSalary', {})
                        job_data['job_min_salary'] = extracted_salary.get('min') or estimated_salary.get('min')
                        job_data['job_max_salary'] = extracted_salary.get('max') or estimated_salary.get('max')

                        # requirements 
                        requirements_model = job.get('jobCardRequirementsModel', {})
                        requirements = requirements_model.get('jobTagRequirements') or requirements_model.get('jobOnlyRequirements', [])
                        job_data['job_required_skills'] = [req.get('label') for req in requirements if 'label' in req]

                     
                        salary_snippet = job.get('salarySnippet', {})
                        job_data['salary_text'] = salary_snippet.get('text') or estimated_salary.get('formattedRange')

                        # Benefits
                        benefits_attributes = next((item for item in job.get('taxonomyAttributes', []) if item.get('label') == 'benefits'), None)
                        if benefits_attributes:
                            labels = [attr.get('label') for attr in benefits_attributes.get('attributes', [])]
                            job_data['job_highlights'] = {'Benefits': labels}
                            job_data['job_benefits'] = labels

                        job_data['employer_logo'] = job.get('companyBrandingAttributes', {}).get('logoUrl')
                        job_data['html_snippet'] = job.get('snippet', '<></>')

                        job_data['job_apply_link'] = job.get('thirdPartyApplyUrl')

                        # job description safely
                        description_content = job.get('snippet', '')
                        try:
                            description_soup = BeautifulSoup(description_content, 'html.parser')
                            description_items = description_soup.find_all('li')
                            job_data["job_description"] = [li.get_text(strip=True) for li in description_items if li.text.strip()]
                        except Exception as e:
                            logging.error(f"Error parsing job description for job ID {job_data['job_id']}: {e}")
                            job_data["job_description"] = description_content  # Fallback to raw content

                        jobs_data.append(job_data)

                    successful_fetch = True
                    break  # bvreak if successful with proxy

            if not successful_fetch:
                logging.error(f"Failed to fetch jobs from all proxies.")
    return jobs_data



@app.route('/')
def home():
    return "OK"

@app.route('/get-jobs', methods=['GET'])
def get_jobs():
    # parameters from URL with defaults
    role = request.args.get('role', 'software engineer')
    location = request.args.get('location', 'remote')
    print(f"role: {role}\nlocation: {location}")
    # role = "software engineer"
    # location = "remote"
    # proxy API setup
    api_key = os.getenv('PROXY_API_SECRET')
    proxies_response = requests.get(
        "https://proxy.webshare.io/api/v2/proxy/list/?mode=direct&page=1&page_size=50&country_code__in=US,CA",
        headers={"Authorization": f"Token {api_key}"}
    )
    proxies = proxies_response.json()['results']
    scrape_url = os.getenv('SCRAPE_URL')

    url = f"{scrape_url}/jobs?q={role}&l={location}"
    jobs = fetch_jobs(proxies, url)

    return jsonify({
        'role': role,
        'location': location,
        'jobs': jobs
    })


@app.route('/get-job/<jobId>', methods=['GET'])
def get_job(jobId):
    api_key = os.getenv('PROXY_API_SECRET')
    proxies_response = requests.get(
        "https://proxy.webshare.io/api/v2/proxy/list/?mode=direct&page=1&page_size=50&country_code__in=US,CA",
        headers={"Authorization": f"Token {api_key}"}
    )
    proxies = proxies_response.json()['results']
    successful_fetch = False
    data = None

    for proxy in proxies:
        if not proxy.get('valid', False):
            logging.info("Invalid Proxy")
            continue

        session = requests.Session()
        data = fetch_job_details(session, jobId, proxy)
        if data:
            successful_fetch = True
            break

    if not successful_fetch:
        logging.error(f"Failed to fetch job details for jobId {jobId} from all proxies.")
        return jsonify({"error": "Failed to retrieve data"}), 500

    return jsonify({
        'jobId': jobId,
        'job': data 
    })

if __name__ == '__main__':
    app.run(debug=True)
# get_jobs()