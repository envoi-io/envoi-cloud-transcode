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
        "vurl": {
            "help": "VURL of the asset"
        },
        "config": {
            "help": "VURL Configuration"
        },
        "config-file": {
            "help": "VURL Configuration file"
        },
        "config-mime": {
            "help": "VURL Configuration MIME type",
            "default": "application/json"
        },
        "mime-type": {
          "help": "VURL response mime type"
        }
    }

    @classmethod
    def read_config(cls, opts):
        config_file = getattr(opts, 'config_file')
        if config_file:
            with open(config_file) as f:
                return f.read()
        return getattr(opts, 'config')

    def run(self, opts=None):
        if opts is None:
            opts = self.opts

        base_url = getattr(opts, 'base_url')
        ruid = getattr(opts, 'ruid')
        vurl = getattr(opts, 'vurl')
        config = self.read_config(opts)
        config_mime = getattr(opts, 'config_mime')
        mime_type = getattr(opts, 'mime_type')
        data = {
            "vurl": vurl,
            "config": config,
            "config_mime": config_mime,
            "mime_type": mime_type
        }
        client = RaspApiClient(base_url)
        response = client.create_asset_vurl(ruid, data)
        print(response)
        return response


class RaspCommand(CliCommand):
    DESCRIPTION = "Dolby Rasp Commands"
    SUBCOMMANDS = {
        "create-ruid": CreateAssetCommand,
        "create-vurl": CreateVurlCommand,
    }

