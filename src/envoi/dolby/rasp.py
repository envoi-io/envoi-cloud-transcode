from utils.http_client import HttpClient
import logging

LOG = logging.getLogger(__name__)

class RaspApiClient(HttpClient):
    base_url = "api.dolbyrasp.com"

    def __init__(self, base_url):
        super().__init__(base_url)

    def create_asset(self, data):
        endpoint = 'api/asset'
        return self.post(endpoint, data)

    def create_asset_vurl(self, ruid, data):
        endpoint = f'api/asset/vurl?ruid={ruid}'
        return self.put(endpoint, data)

    def get_asset_file(self, ruid, file_path):
        endpoint = f'asset/{ruid}/{file_path}'
        return self.get(endpoint)

