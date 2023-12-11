#!/usr/bin/env python3
import argparse
import datetime

import boto3
import json
import logging
import os
import sys

logger = logging.Logger('envoi-media-convert')


def default_json_converter(o):
    if isinstance(o, datetime.datetime):
        return o.isoformat()


def json_argument_type(value_in):
    """
        Handles arguments that are passed in for JSON type arguments.

        If the argument is a string that starts with 'file://' then it
        is treated as a path to a JSON file.  If the argument is a string
        that does not start with 'file://' then it is treated as a JSON.
    """
    if value_in is None:
        return None
    if value_in.startswith('file://'):
        file_path = value_in[7:]  # removes 'file://' from the path
        if not os.path.isfile(file_path):
            raise ValueError(f"File {file_path} does not exist")
        with open(file_path, 'r') as f:
            return json.load(f)
    return json.loads(value_in)


class JsonArgumentAction(argparse.Action):

    @classmethod
    def process_value(cls, _parser, _namespace, value, _option_string=None):
        return json_argument_type(value)

    def process_values(self, parser, namespace, values, option_string=None):
        if isinstance(values, list):
            values = [self.__class__.process_value(parser, namespace, v, option_string) for v in values]
        else:
            values = self.__class__.process_value(parser, namespace, values, option_string)
        setattr(namespace, self.dest, values)

    def __call__(self, parser, namespace, values, option_string=None):
        self.process_values(parser, namespace, values, option_string)


class AwsHelper:

    @classmethod
    def get_account_id(cls):
        sts_client = boto3.client('sts')
        account_id = sts_client.get_caller_identity()['Account']
        return account_id


class AwsMediaConvertHelper:

    @classmethod
    def get_default_endpoint_url(cls, media_convert_client=None):
        if media_convert_client is None:
            media_convert_client = boto3.client('mediaconvert')

        endpoints = media_convert_client.describe_endpoints()
        return endpoints['Endpoints'][0]['Url']

    @classmethod
    def build_default_role_arn(cls):
        aws_account_id = AwsHelper.get_account_id()
        return f'arn:aws:iam::{aws_account_id}:role/service-role/MediaConvert_Default_Role'

    @classmethod
    def update_file_input_in_settings(cls, settings, file_input):
        inputs = settings['Inputs'] or []
        settings_input = inputs[0] if len(inputs) > 0 else {}
        settings_input['FileInput'] = file_input
        if len(inputs) > 0:
            settings['Inputs'][0] = inputs
        else:
            settings['Inputs'] = [settings_input]
        return settings


class EnvoiMediaConvertCreateJobCommand:

    def __init__(self, opts=None, auto_exec=True):
        self.opts = opts
        if auto_exec:
            self.run()

    def set_job_arg(self, name, create_job_request_body, opt_value, fallback_fn=None):
        if not hasattr(create_job_request_body, name):
            if opt_value is not None:
                create_job_request_body[name] = opt_value
            elif fallback_fn is not None:
                create_job_request_body[name] = fallback_fn()

    def run(self, opts=None):
        if opts is None:
            opts = self.opts

        endpoint = opts.endpoint or AwsMediaConvertHelper.get_default_endpoint_url()

        media_convert_client = boto3.client('mediaconvert', endpoint_url=endpoint)

        create_job_request_body = opts.create_job_request_body or {}

        self.set_job_arg('Settings', create_job_request_body, opts.settings)
        self.set_job_arg('Role', create_job_request_body, opts.role_arn,
                         fallback_fn=AwsMediaConvertHelper.build_default_role_arn)
        self.set_job_arg('JobTemplate', create_job_request_body, opts.job_template)
        self.set_job_arg('Priority', create_job_request_body, opts.priority)
        self.set_job_arg('Queue', create_job_request_body, opts.queue)
        self.set_job_arg('Tags', create_job_request_body, opts.tags)
        self.set_job_arg('UserMetadata', create_job_request_body, opts.user_metadata)

        job = media_convert_client.create_job(**create_job_request_body)
        print(json.dumps(job, indent=2, default=default_json_converter))
        return True

    @classmethod
    def init_parser(cls, subparsers, command_name=None):

        if subparsers is None:
            parser = argparse.ArgumentParser()
        else:
            parser = subparsers.add_parser(
                command_name,
                help='Create a new MediaConvert job.',
            )
        parser.set_defaults(handler=cls)
        parser.add_argument(
            '--settings',
            action=JsonArgumentAction,
            help='Settings contains all the transcode settings for a job. This is a required argument if not '
            'provided in the `create-job-request-body` argument.')
        parser.add_argument(
            '--create-job-request-body',
            default={},
            action=JsonArgumentAction,
            help='Optional. A JSON string that contains all the transcode settings for a job. This can be used to run '
            ' a job using the `Create job request body` in the MediaConvert console.'
        )
        parser.add_argument(
            '--job-template',
            default=None,
            help='Optional. When you create a job, you can either specify a job template or specify the transcoding '
                 'settings individually.',
        )
        parser.add_argument(
            '--priority',
            type=int,
            default=None,
            help="Optional. Specify the relative priority for this job. In any given queue, the service begins "
                 "processing the job with the highest value first. When more than one job has the same priority, the "
                 "service begins processing the job that you submitted first. If you don't specify a priority, the "
                 "service uses the default value 0."
        )
        parser.add_argument(
            '--endpoint',
            default=None,
            help='Optional. The URL of the MediaConvert endpoint that you want to use.',
        )
        parser.add_argument(
            '--queue',
            default=None,
            help='The name of the MediaConvert queue that you want to use for this job.',
        )
        parser.add_argument(
            '--role-arn',
            default=None,
            help='The Amazon Resource Name (ARN) for the IAM role that will be assumed when processing the job.',
        )
        parser.add_argument(
            '--simulate-reserve-queue',
            choices=['DISABLED', 'ENABLED'],
            default=None,
            help='Optional. Enable this setting when you run a test job to estimate how many reserved transcoding '
            'slots (RTS) you need. When this is enabled, MediaConvert runs your job from an on-demand queue with '
            'similar performance to what you will see with one RTS in a reserved queue. This setting is disabled by '
            'default.'
        )
        parser.add_argument(
            '--status-update-interval',
            choices=['SECONDS_10', 'SECONDS_12', 'SECONDS_15', 'SECONDS_20', 'SECONDS_30',
                     'SECONDS_60', 'SECONDS_120', 'SECONDS_180', 'SECONDS_240', 'SECONDS_300',
                     'SECONDS_360', 'SECONDS_420', 'SECONDS_480', 'SECONDS_540', 'SECONDS_600'],
            default=None,
            help='Optional. Specify how often MediaConvert sends STATUS_UPDATE events to Amazon CloudWatch Events. '
            'Set the interval, in seconds, between status updates. MediaConvert sends an update at this interval from '
            'the time the service begins processing your job to the time it completes the transcode or encounters an '
            'error.'
        )
        parser.add_argument(
            '--tags',
            default=None,
            help='Optional. A list of tags to assign to the job. Tags are metadata that you assign to the job.'
        )
        parser.add_argument(
            '--user-metadata',
            default=None,
            help='Optional. A list of key-value pairs, in the form of name-value pairs, to associate with the job.'
        )
        return parser


class EnvoiCommandLineUtility:

    @classmethod
    def parse_command_line(cls, cli_args, env_vars, sub_commands=None):
        parser = argparse.ArgumentParser(
            description='Envoi MediaConvert Command Line Utility',
        )

        parser.add_argument("--log-level", dest="log_level",
                            default="WARNING",
                            help="Set the logging level (options: DEBUG, INFO, WARNING, ERROR, CRITICAL)")

        if sub_commands is not None:
            sub_command_parsers = {}
            sub_parsers = parser.add_subparsers(dest='command')
            sub_parsers.required = True

            for sub_command_name, sub_command_handler in sub_commands.items():
                sub_command_parser = sub_command_handler.init_parser(sub_parsers, command_name=sub_command_name)
                sub_command_parser.required = True
                sub_command_parsers[sub_command_name] = sub_command_parser

        (opts, args) = parser.parse_known_args(cli_args)
        return opts, args, env_vars, parser

    @classmethod
    def handle_cli_execution(cls):
        """
        Handles the execution of the command-line interface (CLI) for the application.

        :returns: Returns 0 if successful, 1 otherwise.
        """
        cli_args = sys.argv[1:]
        env_vars = os.environ.copy()

        sub_commands = {
            'create-job': EnvoiMediaConvertCreateJobCommand
        }

        opts, _unhandled_args, env_vars, parser = cls.parse_command_line(cli_args, env_vars, sub_commands)

        # We create a new handler for the root logger, so that we can get
        # setLevel to set the desired log level.
        ch = logging.StreamHandler()
        ch.setLevel(opts.log_level.upper())
        logger.addHandler(ch)

        try:
            # If 'handler' is in args, run the correct handler
            if hasattr(opts, 'handler'):
                opts.handler(opts)
            else:
                parser.print_help()
                return 1

            return 0
        except Exception as e:
            logger.exception(e)
            return 1


if __name__ == '__main__':
    EXIT_CODE = EnvoiCommandLineUtility.handle_cli_execution()
    sys.exit(EXIT_CODE)
