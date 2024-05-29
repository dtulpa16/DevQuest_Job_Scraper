import os
import random
import re
import logging
from bs4 import BeautifulSoup
from flask import Flask, jsonify, request
from dotenv import load_dotenv

logging.basicConfig(level=logging.DEBUG)
load_dotenv()

app = Flask(__name__)

# Regex patterns for extracting data from scripts in the HTML
import re
INITIAL_DATA_PATTERN = re.compile(r'window._initialData\s*=\s*(\{.*?\});', re.DOTALL)
JOB_CARDS_PATTERN = re.compile(r'window.mosaic.providerData\["mosaic-provider-jobcards"\]\s*=\s*(\{.*?\});', re.DOTALL)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.2420.81",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 OPR/109.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.4; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 OPR/109.0.0.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
]
# Headers for making requests to the job site
def get_random_headers():
    return {
        # "Host":"www.indeed.com",
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "en-US,en;q=0.5",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Referer": os.getenv('SCRAPE_URL') + "/",
        # "X-Amzn-Trace-Id":""
    }


# Fetch URL content using HTTP client
# Parameters:
# - client: the HTTP client instance
# - url: the URL to fetch
# Returns: BeautifulSoup object with parsed HTML or None if failed
async def fetch(client, url):
    from bs4 import BeautifulSoup
    try:
        response = await client.get(url,headers=get_random_headers())
        response.raise_for_status()
        html = response.text
        return BeautifulSoup(html, 'lxml')
    except Exception as e:
        logging.error(f"Error fetching URL {url}: {e}")
        return None

# Extract JSON data from BeautifulSoup object
# Parameters:
# - soup: BeautifulSoup object containing the HTML
# Returns: JSON object extracted from the script tag or None if failed
def extract_json_data(soup):
    import json
    for script in soup.find_all('script'):
        if 'window._initialData' in script.text:
            match = INITIAL_DATA_PATTERN.search(script.text)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError as e:
                    logging.error(f"Error decoding JSON: {e}")
    return None

# Extract metadata from HTML content
# Parameters:
# - html_content: BeautifulSoup object containing the HTML
# Returns: list of job metadata or None if failed
def extract_metadata(html_content):
    import json
    try:
        script_tag = html_content.find('script', {'id': 'mosaic-data'})
        if script_tag:
            match = JOB_CARDS_PATTERN.search(script_tag.string)
            if match:
                jobcards_data = json.loads(match.group(1))
                return jobcards_data.get("metaData", {}).get('mosaicProviderJobCardsModel', {}).get('results', None)
    except Exception as e:
        logging.error(f"Error extracting metadata: {e}")
    return None

# Fetch job details using a specific proxy
# Parameters:
# - client: the HTTP client instance
# - job_id: the ID of the job to fetch details for
# - proxy: proxy configuration to use for the request
# Returns: dictionary with job details or None if failed
async def fetch_job_details(client, job_id, proxy):
    try:
        job_url = os.getenv('SCRAPE_URL') + '/viewjob?jk=' + job_id
        job_soup = await fetch(client, job_url)
        if not job_soup:
            logging.error(f"Failed to fetch job page for job ID {job_id} with proxy {proxy}")
            return None


        json_data = extract_json_data(job_soup)
        if not json_data:
            logging.error(f"Failed to extract JSON data for job ID {job_id} from {job_url}")
            return None

        benefits = json_data['hostQueryExecutionResult']['data']['jobData']['results'][0]['job'].get('benefits', [])
        if not benefits:
            benefits = []
        job_details = {
            "employer_logo": json_data['jobInfoWrapperModel']['jobInfoModel']['jobInfoHeaderModel']['companyImagesModel']['logoUrl'] if json_data['jobInfoWrapperModel']['jobInfoModel']['jobInfoHeaderModel']['companyImagesModel']['logoUrl'] else None,
            "employer_name": json_data['hostQueryExecutionResult']['data']['jobData']['results'][0]['job']['sourceEmployerName'] if json_data['hostQueryExecutionResult']['data']['jobData']['results'][0]['job']['sourceEmployerName'] else json_data['jobInfoWrapperModel']['jobInfoModel']['jobInfoHeaderModel']['companyName'],
            "job_title": json_data['hostQueryExecutionResult']['data']['jobData']['results'][0]['job']['title'] or json_data['jobInfoWrapperModel']['jobInfoModel']['jobInfoHeaderModel']['jobTitle'],
            "job_apply_link": json_data['hostQueryExecutionResult']['data']['jobData']['results'][0]['job']['url'] if json_data['hostQueryExecutionResult']['data']['jobData']['results'][0]['job']['url'] else json_data['jobMetadataFooterModel']['originalJobLink']['href'],
            "job_city": json_data['hostQueryExecutionResult']['data']['jobData']['results'][0]['job']['location']['city'] if json_data['hostQueryExecutionResult']['data']['jobData']['results'][0]['job']['location']['city'] else json_data['hostQueryExecutionResult']['data']['jobData']['results'][0]['job']['location']['formatted']['short'],
            "job_is_remote": json_data['hostQueryExecutionResult']['data']['jobData']['results'][0]['job']['location']['city'].lower() == "remote" if json_data['hostQueryExecutionResult']['data']['jobData']['results'][0]['job']['location']['city'] else False,
            "salary_text": json_data['salaryInfoModel']['salaryText'] if json_data.get('salaryInfoModel') else json_data['salaryGuideModel']['estimatedSalaryModel']['formattedRange'] if json_data['salaryGuideModel'].get('estimatedSalaryModel') else 'Not Specified',
            "min_salary": json_data['salaryInfoModel']['salaryMin'] if json_data.get('salaryInfoModel') else json_data['salaryGuideModel']['estimatedSalaryModel']['min'] if json_data['salaryGuideModel'].get('estimatedSalaryModel') else None,
            "max_salary": json_data['salaryInfoModel']['salaryMax'] if json_data.get('salaryInfoModel') else json_data['salaryGuideModel']['estimatedSalaryModel']['max'] if json_data['salaryGuideModel'].get('estimatedSalaryModel') else None,
            "job_salary_currency": json_data['salaryInfoModel']['salaryCurrency'] if json_data.get('salaryInfoModel') else 'USD',
            "job_description": json_data['hostQueryExecutionResult']['data']['jobData']['results'][0]['job']['description']['text'] if json_data['hostQueryExecutionResult']['data']['jobData']['results'][0]['job']['description']['text'] else json_data['hostQueryExecutionResult']['data']['jobData']['results'][0]['job']['description']['html'],
            "job_description_html": json_data['hostQueryExecutionResult']['data']['jobData']['results'][0]['job']['description']['html'] if json_data['hostQueryExecutionResult']['data']['jobData']['results'][0]['job']['description']['html'] else json_data['jobInfoWrapperModel']['jobInfoModel']['sanitizedJobDescription'],
            "job_benefits": [attr.get('label') for attr in benefits] if benefits else [],
            "job_age": json_data['hiringInsightsModel']['age'] or None,
            "attributes": [attr.get('label') for attr in (json_data['hostQueryExecutionResult']['data']['jobData']['results'][0]['job']['attributes'])] if json_data['hostQueryExecutionResult']['data']['jobData']['results'][0]['job']['attributes'] else [],
        }
        return job_details

    except Exception as e:
        logging.error(f"Failed to process job details for job ID {job_id}: {e}")
        return None

# Fetch jobs using a list of proxies
# Parameters:
# - proxies: list of proxy configurations
# - target_url: URL to fetch job listings from
# Returns: list of job data dictionaries or empty list if all proxies fail
async def fetch_jobs(proxies, target_url):
    import httpx
    jobs_data = []
    for proxy in proxies: 
        formatted_proxy_url = f"http://{proxy['username']}:{proxy['password']}@{proxy['proxy_address']}:{proxy['port']}"
        proxies_config = {
            'http://': formatted_proxy_url,
            'https://': formatted_proxy_url
        }
        # import requests

        # proxies = proxies_config

        # r = requests.get('http://httpbin.org/headers', proxies=proxies, verify=False)
        # print(r.text)
        async with httpx.AsyncClient( proxies=proxies_config,limits=httpx.Limits(max_connections=1, max_keepalive_connections=1), timeout=httpx.Timeout(5.0)) as client:

            data = await fetch(client, target_url)
            if not data:
                logging.info("INVALID PROXY: ", proxy)
                continue
            json_data = extract_metadata(data)

            if not json_data:
                continue
            if json_data:

                for job in json_data:
                    snippet_html = job.get('snippet', '')
                    if not snippet_html:
                        snippet_html = '<div></div>'
                    job_data = {
                        'job_id': job.get('jobkey', 'No Job ID'),
                        'job_title': job.get('displayTitle') or job.get('title', 'Unknown Title'),
                        'employer_name': job.get('company', 'Unknown Company'),
                        'job_city': job.get('formattedLocation') or job.get('jobLocationCity', 'Unknown Location'),
                        'job_is_remote': "remote" in job.get('remoteWorkModel', {}).get('text', '').lower(),
                        'job_min_salary': job.get('extractedSalary', {}).get('min') or job.get('estimatedSalary', {}).get('min'),
                        'job_max_salary': job.get('extractedSalary', {}).get('max') or job.get('estimatedSalary', {}).get('max'),
                        'job_required_skills': [req.get('label') for req in (job.get('jobCardRequirementsModel', {}).get('jobTagRequirements') or job.get('jobCardRequirementsModel', {}).get('jobOnlyRequirements', []))],
                        'salary_text': job.get('salarySnippet', {}).get('text') or job.get('estimatedSalary', {}).get('formattedRange'),
                        'job_benefits': [attr.get('label') for attr in (next((item for item in job.get('taxonomyAttributes', []) if item.get('label') == 'benefits'), {}).get('attributes', []))],
                        'employer_logo': job.get('companyBrandingAttributes', {}).get('logoUrl'),
                        'html_snippet': job.get('snippet', '<></>'),
                        'job_apply_link': job.get('thirdPartyApplyUrl'),
                        'job_description': [li.get_text(strip=True) for li in BeautifulSoup(snippet_html, 'html.parser').find_all('li') if li.text.strip()]
                    }
                    jobs_data.append(job_data)
                
                return jobs_data
    logging.error("Failed to fetch jobs from all proxies.")
    return []

# Get list of proxies from API
# Parameters:
# - api_key: API key for the proxy service
# - page_size: number of proxies to fetch per page
# Returns: list of proxy configurations
def get_proxies(api_key, page_size=15):
    import requests
    proxies_response = requests.get(
            f"https://proxy.webshare.io/api/v2/proxy/list/?mode=direct&country_code__in=US",
            headers={"Authorization": f"Token {api_key}"}
        )
    proxies_response.raise_for_status()
    return proxies_response.json().get('results', [])


@app.route('/health-check')
def home():
    return "OK"

#! Route to get jobs based on role and location
# URL Parameters:
# - role: job role to search for (default: "software engineer")
# - location: job location to search for (default: "remote")
# Returns: JSON response with job listings
@app.route('/get-jobs', methods=['GET'])
async def get_jobs():
    try:
        role = request.args.get('role', 'software+developer')
        location = request.args.get('location', 'remote')
        logging.debug(f"Role: {role}, Location: {location}")

        api_key = os.getenv('PROXY_API_SECRET')

        proxies = get_proxies(api_key, page_size=15)

        scrape_url = os.getenv('SCRAPE_URL')
        url = f"{scrape_url}/jobs?q={role}&l={location}"

        jobs = await fetch_jobs(proxies, url)

        return jsonify({
            'role': role,
            'location': location,
            'jobs': jobs,
         
        })
    except Exception as e:
        logging.error(f"Error in /get-jobs: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500

#! Route to get job details based on job ID
# URL Parameters:
# - jobId: the ID of the job to fetch details for
# Returns: JSON response with job details
@app.route('/get-job/<jobId>', methods=['GET'])
async def get_job(jobId):
    import httpx
    try:
        api_key = os.getenv('PROXY_API_SECRET')
        proxies = get_proxies(api_key, page_size=15)

        for proxy in proxies:
            formatted_proxy_url = f"http://{proxy['username']}:{proxy['password']}@{proxy['proxy_address']}:{proxy['port']}"
            proxies_config = {
                'http://': formatted_proxy_url,
                'https://': formatted_proxy_url
            }
            async with httpx.AsyncClient(proxies=proxies_config,limits=httpx.Limits(max_connections=1, max_keepalive_connections=1), timeout=httpx.Timeout(5.0)) as client:
                if not proxy.get('valid', False):
                    logging.info("Invalid Proxy")
                    continue

                result = await fetch_job_details(client, jobId, proxy)
                if not result:
                    continue
                if result:
                    return jsonify({'jobId': jobId, 'job': result})

        logging.error(f"Failed to fetch job details for jobId {jobId} from all proxies.")
        
        return jsonify({"error": "Failed to retrieve data"}), 500

    except httpx.RequestError as e:
        logging.error(f"Error fetching proxies: {e}")
        return jsonify({"error": "Failed to retrieve proxies"}), 500

    except Exception as e:
        logging.error(f"Error in /get-job: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500
    
if __name__ == '__main__':
    app.run(debug=True)
