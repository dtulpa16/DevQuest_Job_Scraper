# DevQuest_Job_Scraper

This is a Python web scraper that fetches job listings from a specified URL using proxies for anonymity. The scraper uses the Flask framework for setting up a simple API and the `httpx` library for making asynchronous HTTP requests.

## Requirements

- Python 3.8+
- Flask[Async]
- httpx
- beautifulsoup4
- lxml
- python-dotenv

## Installation

1. Clone the repository:

   `git clone https://github.com/dtulpa16/DevQuest_Job_Scraper`

   `cd DevQuest_Job_Scraper`

3. Create and activate a virtual environment:

   `pipenv install`
   
   `pipenv shell`

5. Install the dependencies:

   `pip install Flask[async] python-dotenv httpx requests beautifulsoup4 lxml`

## Environment Variables

You will need a WebShare API key to use the proxy service. Add the following environment variables to a `.env` file in the root of your project:

```
PROXY_API_SECRET=your_webshare_api_key
SCRAPE_URL=your_target_url
```

If you need any other environment variables, please email me at `dtulpa16@yahoo.com`.

## Usage

1. Run the Flask application:

   `python main.py`

2. Access the following endpoints:

   ### Health Check

   `GET /health-check`

   Returns a simple "OK" response to verify the server is running.

   ### Get Jobs

   `GET /get-jobs?role=software+developer&location=remote`

   Fetches job listings based on the specified role and location.

   #### Parameters:
   - `role`: The job role to search for (default: "software developer")
   - `location`: The job location to search for (default: "remote")

   #### Response:
   A JSON response with the job listings.

   #### Data Structure:
   - `jobs`: List of job objects
     - `job_id`: String
     - `job_title`: String
     - `employer_name`: String
     - `job_city`: String
     - `job_is_remote`: Boolean
     - `job_min_salary`: Number
     - `job_max_salary`: Number
     - `job_required_skills`: List of strings
     - `salary_text`: String
     - `job_benefits`: List of strings
     - `employer_logo`: String (URL)
     - `html_snippet`: String (HTML)
     - `job_apply_link`: String (URL)
     - `job_description`: List of strings

   ### Get Job Details

   `GET /get-job/<jobId>`

   Fetches detailed information about a specific job based on its ID.

   #### Parameters:
   - `jobId`: The ID of the job to fetch details for

   #### Response:
   A JSON response with the job details.

   #### Data Structure:
   - `job`: Object containing job details
     - `job_id`: String
     - `job_title`: String
     - `employer_name`: String
     - `job_city`: String
     - `job_is_remote`: Boolean
     - `min_salary`: Number
     - `max_salary`: Number
     - `job_salary_currency`: String
     - `salary_text`: String
     - `job_description`: String
     - `job_description_html`: String (HTML)
     - `job_apply_link`: String (URL)
     - `job_benefits`: List of strings
     - `attributes`: List of strings
     - `job_age`: String
     - `employer_logo`: String (URL)

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.

## Contact

For any inquiries, please contact me at `dtulpa16@yahoo.com`.
