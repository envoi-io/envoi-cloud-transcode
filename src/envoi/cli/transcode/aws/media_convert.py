import argparse

from envoi.aws.aws_media_convert_helper import AwsMediaConvertHelper
from envoi.cli import CliCommand, json_argument

AWS_PARAMS = {
    "region": {
        'help': 'AWS Region',
        'default': argparse.SUPPRESS
    },
    "profile": {
        'help': 'AWS Profile',
        'default': argparse.SUPPRESS
    },
    "access-key": {
        'help': 'AWS Access Key',
        'default': argparse.SUPPRESS
    },
    "secret-key": {
        'help': 'AWS Secret Key',
        'default': argparse.SUPPRESS
    }
}


def init_client_from_args(args):
    client_args = {}
    for key, value in args.items():
        if key in AWS_PARAMS:
            client_args[key] = value
    return AwsMediaConvertHelper(**client_args)


class AwsMediaConvertCreateJobCommand(CliCommand):
    DESCRIPTION = "AWS MediaConvert Create Job"
    PARAMS = {
        'template': {
            'help': 'The template to use for the job',
            'default': argparse.SUPPRESS
        },
        'queue': {

        },
        'role': {

        },
        'settings': {
            'help': 'Job Settings',
            'type': json_argument,
            'default': None
        },
        'tags': {

        },
        'user-metadata': {
            'help': 'User Metadata',
            'default': None
        },
    }

    @classmethod
    def get_settings(cls, opts):
        settings = getattr(opts, 'settings')
        settings_file = getattr(opts, 'settings_file')
        if settings is not None:
            return settings
        elif settings_file is not None:
            with open(settings_file, 'r') as f:
                return f.read()
        return None

    def run(self, opts=None):
        create_job_args = {
            "template": getattr(opts, 'template'),
            "queue": getattr(opts, 'queue'),
            "role": getattr(opts, 'role'),
            "settings": getattr(opts, 'settings'),
            "tags": getattr(opts, 'tags'),
            "user_metadata": getattr(opts, 'user_metadata')
        }
        media_convert = init_client_from_args(opts)
        response = media_convert.create_job(**create_job_args)
class AwsMediaConvertCreateJobTemplate(CliCommand):
    DESCRIPTION = "AWS MediaConvert Create Job Template"
    PARAMS = {
        'name': {
            'help': 'The name of the template',
            'required': True
        },
        'description': {
            'help': 'The description of the template',
            'default': None
        },
        'settings': {
            'help': 'The settings for the template',
            'type': json_argument,
            'default': None
        },
        'tags': {
            'help': 'The tags for the template',
            'default': None
        },
        'category': {
            'help': 'The category of the template',
            'default': None
        },
        'queue': {
            'help': 'The queue for the template',
            'default': None
        },
        'priority': {
            'help': 'The priority for the template',
            'default': 0
        }

    }

    def run(self, opts=None):
        create_job_template_args = {
            "name": getattr(opts, 'name'),
            "description": getattr(opts, 'description'),
            "settings": getattr(opts, 'settings'),
            "tags": getattr(opts, 'tags'),
            "category": getattr(opts, 'category'),
            "queue": getattr(opts, 'queue'),
            "priority": getattr(opts, 'priority')
        }
        media_convert = init_client_from_args(opts)
        response = media_convert.create_job_template(**create_job_template_args)
        print(response)


class AwsMediaConvertListJobsCommand(CliCommand):
    DESCRIPTION = "AWS MediaConvert List Jobs"
    PARAMS = {
        'max-results': {
            'help': 'The maximum number of results to return',
            'default': 20
        },
        'next-token': {
            'help': 'A token to specify where to start paginating',
            'default': None
        },
        'order': {
            'help': 'The order in which to list jobs',
            'default': 'ASCENDING'
        },
        'queue': {
            'help': 'The queue to list jobs for',
            'default': None
        },
        'status': {
            'help': 'The status of the jobs to list',
            'default': None
        }
    }


class AwsMediaConvertGetJobCommand(CliCommand):
    DESCRIPTION = "AWS MediaConvert Get Job"
    PARAMS = {
        'id': {
            'help': 'The ID of the job',
            'required': True
        }
    }

    def run(self, opts=None):
        if opts is None:
            opts = self.opts
        id = getattr(opts, 'id')

        media_convert = init_client_from_args(opts)
        response = media_convert.get_job(id)
        return response


class AwsMediaConvertCommand(CliCommand):
    DESCRIPTION = "AWS MediaConvert Commands"
    SUBCOMMANDS = {
        'create-job': AwsMediaConvertCreateJobCommand,
        'create-job-template': AwsMediaConvertCreateJobTemplate,
        'get-job': AwsMediaConvertGetJobCommand,
        'list-jobs': AwsMediaConvertListJobsCommand
    }
