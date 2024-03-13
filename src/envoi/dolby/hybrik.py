from utils.http_client import HttpClient

# https://docs.hybrik.com/api/v1/HybrikAPI.html?#getting-started
# https://docs.hybrik.com/api/v1/HybrikAPI.html?#create-job
# https://docs.hybrik.com/api/v1/HybrikAPI.html?#get-job-info


class HybrikApiClient(HttpClient):

    def __init__(self, api_url, compliance_date, oapi_key, oapi_secret, user_key, user_secret):
        super().__init__(api_url)
        self.default_headers = {"Content-Type": "application/json", "X-Hybrik-Compliance": compliance_date}
        self.auth = (oapi_key, oapi_secret)
        self.user_key = user_key
        self.user_secret = user_secret
        self.login_data = None

    def connect(self):
        response = self.login(self.user_key, self.user_secret)
        self.login_data = response
        return True

    def call_api(self, http_method, path, query=None, body=None):
        headers = {
            "X-Hybrik-Sapiauth": self.login_data["token"],
            "X-Hybrik-Compliance": self.default_headers["X-Hybrik-Compliance"]
        }
        if body:
            headers["Content-Type"] = "application/json"
        if http_method.lower() == "get":
            return self.get(path, query=query, headers=headers)
        elif http_method.lower() == "post":
            return self.post(path, data=body, query=query, headers=headers)
        elif http_method.lower() == "put":
            return self.put(path, data=body, query=query, headers=headers)
        elif http_method.lower() == "delete":
            return self.delete(path, query=query, headers=headers)

    def create_job(self,
                   name,
                   payload,
                   schema,
                   expiration,
                   priority,
                   task_tags,
                   user_tag,
                   task_retry_count,
                   task_retry_delay_secs):
        endpoint = "jobs"
        body = {
            "name": name,
            "payload": payload,
            "schema": schema,
            "expiration": expiration,
            "priority": priority,
            "task_tags": task_tags,
            "user_tag": user_tag,
            "task_retry_count": task_retry_count,
            "task_retry_delay_secs": task_retry_delay_secs
        }
        return self.call_api("post", endpoint, body=body)

    def delete_job(self, job_id):
        endpoint = f"jobs/{job_id}/delete"
        return self.call_api("delete", endpoint)

    def get_job_definition(self, job_id):
        endpoint = f"jobs/{job_id}/definition"
        return self.call_api("get", endpoint)

    def get_job_results(self, job_id):
        endpoint = f"jobs/{job_id}/result"
        return self.call_api("get", endpoint)

    def get_job_tasks(self, job_id):
        endpoint = f"jobs/{job_id}/tasks"
        return self.call_api("get", endpoint)

    def login(self, user_key, user_secret):
        endpoint = "/login"
        data = {
            "auth_key": user_key,
            "auth_secret": user_secret
        }
        return self.call_api("post", endpoint, body=data)
