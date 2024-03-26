import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class AtemeTitanFileApiBaseClient:
    def __init__(self, base_url, username=None, password=None, access_token=None, refresh_token=None,
                 verify_ssl=True):
        if base_url and base_url.endswith("/"):
            base_url = base_url[:-1]

        self.base_url = base_url
        self.api_base_url = f"{self.base_url}/api"

        self.username = username
        self.password = password
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.verify_ssl = verify_ssl
        if not self.access_token:
            self.get_token()

    def get_token(self):
        response = requests.post(
            f"{self.base_url}/users/token",
            json={"username": self.username, "password": self.password, "domain": ""},
            verify=self.verify_ssl
        )
        response.raise_for_status()
        data = response.json()
        self.access_token = data["access_token"]
        self.refresh_token = data["refresh_token"]

    def refresh_token(self):
        body = {"refresh_token": self.refresh_token}
        response = requests.post(
            f"{self.base_url}/users/refresh_token",
            json=body,
            headers={"Authorization": f"Bearer {self.refresh_token}"},
            verify=self.verify_ssl
        )

        response.raise_for_status()
        data = response.json()
        self.access_token = data["access_token"]

    def request(self, method, endpoint, **kwargs):
        headers = kwargs.get("headers", {})

        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        kwargs["headers"] = headers
        response = requests.request(method, f"{self.base_url}/{endpoint}",
                                    verify=self.verify_ssl,
                                    **kwargs)
        if response.status_code == 401:
            self.refresh_token()
            headers["Authorization"] = f"Bearer {self.access_token}"
            response = requests.request(method, f"{self.base_url}/{endpoint}",
                                        verify=self.verify_ssl,
                                        **kwargs)
        response.raise_for_status()
        return response.json()

    @classmethod
    def build_query_string(cls, query=None):
        if query is None:
            return ""
        return "&".join([f"{k}={v}" for k, v in query.items()])

    def get(self, endpoint, **kwargs):
        return self.request("GET", endpoint, **kwargs)

    def post(self, endpoint, **kwargs):
        return self.request("POST", endpoint, **kwargs)


class AtemeTitanFileApiClient(AtemeTitanFileApiBaseClient):

    def create_job(self, job_def, **kwargs):
        endpoint = "api/jobs"
        body = job_def
        return self.post(endpoint, json=body)

    def create_template(self, template_def, **kwargs):
        endpoint = "api/templates"
        body = template_def
        return self.post(endpoint, json=body)

    def get_job(self, job_id):
        endpoint = "api/jobs"
        return self.get(f"{endpoint}/{job_id}")

    def get_jobs(self):
        endpoint = "api/jobs"
        return self.get(endpoint)

    def get_template(self, template_id):
        endpoint = "api/templates"
        return self.get(f"{endpoint}/{template_id}")

    def list_jobs(self,
                  limit, offset, name, status):
        endpoint = "api/jobs"
        return self.get(endpoint)

    def list_templates(self):
        endpoint = "api/templates"
        return self.get(endpoint)
