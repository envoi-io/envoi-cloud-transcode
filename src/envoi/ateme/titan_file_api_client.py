import http.client
import urllib.parse
import json
import ssl


class AtemeTitanFileApiBaseClient:
    def __init__(self, base_url, username=None, password=None, access_token=None, refresh_token=None,
                 verify_ssl=True):
        if base_url and base_url.endswith("/"):
            base_url = base_url[:-1]

        self.base_url = base_url
        self.api_base_url = f"{self.base_url}/api"

        base_url_parsed = urllib.parse.urlparse(self.base_url)
        self.host = base_url_parsed.hostname
        self.base_path = base_url_parsed.path
        self.username = username
        self.password = password
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.verify_ssl = verify_ssl
        if not self.verify_ssl:
            self.ssl_context = ssl._create_unverified_context()
        else:
            self.ssl_context = None

        if not self.access_token:
            self.get_token()

    def get_token(self):
        payload = json.dumps({"username": self.username, "password": self.password, "domain": ""})
        headers = {"Content-Type": "application/json"}
        data = self.direct_request("POST", f"{self.base_path}/users/token", body=payload, headers=headers)
        if not isinstance(data, dict):
            raise Exception(f"Failed to get token: {data}")
        self.access_token = data["access_token"]
        self.refresh_token = data["refresh_token"]

    def refresh_token(self):
        payload = json.dumps({"refresh_token": self.refresh_token})
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.refresh_token}"}
        data = self.direct_request("POST", f"{self.base_path}/users/refresh_token", body=payload, headers=headers)
        self.access_token = data["access_token"]

    def direct_request(self, method, endpoint, **kwargs):
        conn = http.client.HTTPSConnection(self.host, context=self.ssl_context)
        conn.request(method, endpoint, **kwargs)
        res = conn.getresponse()
        res_data = res.read().decode()

        if res_data:
            try:
                data = json.loads(res_data)
                if isinstance(data, dict):
                    return data
                else:
                    return res_data
            except json.JSONDecodeError:
                return res_data
        else:
            return None

    def request(self, method, endpoint, **kwargs):
        headers = kwargs.get("headers", {})
        path = f"{self.base_path}/{endpoint}"
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        return self.direct_request(method, path, headers=headers, **kwargs)

    def get(self, endpoint, **kwargs):
        return self.request("GET", endpoint, **kwargs)

    def post(self, endpoint, **kwargs):
        return self.request("POST", endpoint, **kwargs)


class AtemeTitanFileApiClient(AtemeTitanFileApiBaseClient):

    def create_job(self, job_def, **kwargs):
        endpoint = "api/jobs"
        body = json.dumps(job_def)
        return self.post(endpoint, body=body)

    def create_template(self, template_def, **kwargs):
        endpoint = "api/templates"
        body = json.dumps(template_def)
        return self.post(endpoint, body=body)

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