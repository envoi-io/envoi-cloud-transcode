from envoi.cli import CliCommand
from envoi.dolby.rasp import RaspApiClient


class CreateAssetCommand(CliCommand):
    DESCRIPTION = "Dolby Rasp - Create Asset"
    PARAMS = {
        "base-url": {
            "help": "Base URL of the RASP API"
        },
        "name": {
            "help": "Name of the asset"
        },
        "url": {
            "help": "URL of the asset"
        },
        "mime-type": {
            "help": "MIME type of the asset"
        }
    }

    def run(self, opts=None):
        if opts is None:
            opts = self.opts

        base_url = getattr(opts, 'base_url')
        name = getattr(opts, 'name')
        url = getattr(opts, 'url')
        mime_type = getattr(opts, 'mime_type')
        data = {
            "name": name,
            "urls": [{"url": url}],
            "asset_mime": mime_type
        }
        client = RaspApiClient(base_url)
        response = client.create_asset(data)
        print(response)
        return response


class CreateVurlCommand(CliCommand):
    DESCRIPTION = "Dolby Rasp - Create VURL"
    PARAMS = {
        "base-url": {
            "help": "Base URL of the RASP API"
        },
        "ruid": {
            "help": "RUID of the asset"
        },
        "body": {
            "help": "The body of the request, as a JSON object. This is an array of VURL objects. If not provided, the "
                    "body will be constructed from the other parameters.",
            "type": json_argument,
            "default": None
        },
        "vurl": {
            "help": "VURL of the asset. Only used if body is not provided"
        },
        "config": {
            "help": "VURL Configuration. Only used if body is not provided",
            "type": json_argument,
            "default": None

        },
        "config-mime": {
            "help": "VURL Configuration MIME type. Only used if body is not provided",
            "default": "application/json"
        },
        "mime-type": {
            "help": "VURL response mime type. Only used if body is not provided",
        }
    }

    def run(self, opts=None):
        if opts is None:
            opts = self.opts

        base_url = getattr(opts, 'base_url')
        ruid = getattr(opts, 'ruid')
        body = getattr(opts, 'body')
        if not body:
            vurl = getattr(opts, 'vurl')
            config = getattr(opts, 'config')
            config_mime = getattr(opts, 'config_mime')
            mime_type = getattr(opts, 'mime_type')

            body = [{
                "vurl": vurl,
                "config": config,
                "config_mime": config_mime,
                "mime": mime_type
            }]

        client = RaspApiClient(base_url)
        response = client.create_asset_vurl(ruid, body)
        print(response)
        return response


class RaspCommand(CliCommand):
    DESCRIPTION = "Dolby Rasp Commands"
    SUBCOMMANDS = {
        "create-ruid": CreateAssetCommand,
        "create-vurl": CreateVurlCommand,
    }

