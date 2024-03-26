import json

from envoi.ateme.titan_file_api_client import AtemeTitanFileApiClient
from envoi.cli import CliCommand, json_argument

COMMON_PARAMS = {
    "base-url": {
        'help': 'Ateme base URL',
        'required': True
    },
    "username": {
        'help': 'Ateme user'
    },
    "password": {
        'help': 'Ateme password'
    },
    "token": {
        'help': 'Ateme token'
    },
    "--no-verify-ssl": {
        'help': 'Turns off SSL Certificate Verification',
        'default': True,
        'action': 'store_true'

    }
}


def init_ateme_client(opts):
    base_url = getattr(opts, 'base_url')
    username = getattr(opts, 'username')
    password = getattr(opts, 'password')
    token = getattr(opts, 'token')
    no_verify_ssl = getattr(opts, 'no_verify_ssl')
    verify_ssl = not no_verify_ssl
    return AtemeTitanFileApiClient(base_url, username, password, token, verify_ssl=verify_ssl)


class CreateJobCommand(CliCommand):
    DESCRIPTION = "Create a job"
    PARAMS = {
        **COMMON_PARAMS,
        "job-def": {
            'help': 'The Job Definition',
            'required': True,
            'type': json_argument
        },
        "job-name": {
            'help': 'Job Name',
            'required': False,
            'default': None,
            'type': str
        },
        "input-asset-name": {
            'help': 'Asset Name',
            'required': False,
            'default': 'asset_1',
            'type': str
        },
        "input-asset-url": {
            'help': 'Asset URL',
            'required': False,
            'default': None,
            'type': str
        },

    }

    def run(self, opts=None):
        if opts is None:
            opts = self.opts
        client = init_ateme_client(opts)

        job_def = getattr(opts, 'job-def')
        job_name = getattr(opts, 'job_name')
        if job_name:
            job_def['name'] = job_name

        asset_url = getattr(opts, 'input_asset_url')
        if asset_url:
            assets = job_def['assets'] or {}
            asset_name = getattr(opts, 'input_asset_name')
            assets[asset_name] = asset_url
            job_def['assets'] = assets

        response = client.create_job(job_def)
        try:
            response_as_string = json.dumps(response)
        except TypeError:
            response_as_string = response
        print(response_as_string)


class CreateTemplateCommand(CliCommand):
    DESCRIPTION = "Create a template"
    PARAMS = {
        **COMMON_PARAMS,
        "template-def": {
            'help': 'The Template Definition',
            'required': True,
            'type': json_argument
        }
    }

    def run(self, opts=None):
        if opts is None:
            opts = self.opts
        client = init_ateme_client(opts)
        response = client.create_template(opts['template-def'])
        try:
            response_as_string = json.dumps(response)
        except TypeError:
            response_as_string = response
        print(response_as_string)


class GetJobCommand(CliCommand):
    DESCRIPTION = "Get a job"
    PARAMS = {
        "job-id": {
            'help': 'Job ID',
            'required': True
        }
    }

    def run(self, opts=None):
        if opts is None:
            opts = self.opts
        client = init_ateme_client(opts)
        response = client.get_job(opts['job-id'])
        try:
            response_as_string = json.dumps(response)
        except TypeError:
            response_as_string = response
        print(response_as_string)


class ListJobsCommand(CliCommand):
    DESCRIPTION = "List jobs"
    PARAMS = {
        **COMMON_PARAMS,
        "offset": {
            'help': 'Offset'
        },
        "limit": {
            'help': 'Limit'
        },
        "name": {
            'help': 'Name'
        },
        "status": {
            'help': 'Status'
        }
    }

    def run(self, opts=None):
        if opts is None:
            opts = self.opts
        client = init_ateme_client(opts)
        response = client.list_jobs(getattr(opts, 'offset'),
                                    getattr(opts, 'limit'),
                                    getattr(opts, 'name'),
                                    getattr(opts, 'status'))
        try:
            response_as_string = json.dumps(response)
        except TypeError:
            response_as_string = response
        print(response_as_string)


class ListTemplatesCommand(CliCommand):
    DESCRIPTION = "List templates"
    PARAMS = {
        **COMMON_PARAMS
    }

    def run(self, opts=None):
        if opts is None:
            opts = self.opts
        client = init_ateme_client(opts)
        response = client.list_templates()
        try:
            response_as_string = json.dumps(response)
        except TypeError:
            response_as_string = response
        print(response_as_string)


class AtemeCommand(CliCommand):
    DESCRIPTION = "Ateme Commands"
    SUBCOMMANDS = {
        'create-job': CreateJobCommand,
        'get-job': GetJobCommand,
        'list-jobs': ListJobsCommand,
        'list-templates': ListTemplatesCommand
    }
