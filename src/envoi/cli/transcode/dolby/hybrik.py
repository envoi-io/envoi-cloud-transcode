import json

from envoi.cli import CliCommand, json_argument
from envoi.dolby.hybrik import HybrikApiClient

COMMON_PARAMS = {
    "api-url": {
        "help": "The URL of the Hybrik API",
        "default": "https://api-demo.hybrik.com/v1"
    },
    "oapi-key": {
        "help": "Hybrik OAPI Key"
    },
    "oapi-secret": {
        "help": "Hybrik OAPI Secret"
    },
    "auth-key": {
        "help": "Hybrik Auth Key"
    },
    "auth-secret": {
        "help": "Hybrik Auth Secret"
    }
}


class HybrikApiCommand(CliCommand):
    def init_client(self, opts=None):
        opts = opts or self.opts
        client_args = {
            "oapi_key": getattr(opts, "oapi_key"),
            "oapi_secret": getattr(opts, "oapi_secret"),
            "auth_key": getattr(opts, "auth_key"),
            "auth_secret": getattr(opts, "auth_secret")
        }
        base_url = getattr(opts, "api_url")
        if base_url is not None:
            client_args["api_url"] = base_url
        client = HybrikApiClient(**client_args)
        client.connect()
        return client


class CreateJobCommand(HybrikApiCommand):
    DESCRIPTION = "Dolby Hybrik - Create Job"
    PARAMS = {
        **COMMON_PARAMS,
        "name": {
            "help": "The visible name of the job",
            "default": None
        },
        "payload": {
            "help": "Job Definition. This must be a JSON object",
            "type": json_argument,  # json.loads,
            "default": None
        },
        "schema": {
            "help": 'Optional. Hybrik will be supporting some third-party job schemas, which can be specified in this '
                    'string. The default is "hybrik".',
            "default": None

        },
        "definitions": {
            "help": "Global string replacements can be defined in this section. Anything in the Job JSON that is "
                    "enclosed with double parentheses such as {{to_be_replaced}} will be replaced.",
            "type": json_argument,
            "default": None
        },
        "expiration": {
            "help": "Expiration (in minutes) of the job. A completed job will expire and be deleted after ["
                    "expiration] minutes. Default is 30 days.",
            "default": None
        },
        "priority": {
            "help": "The priority of the job",
            "default": 100
        },
        "task-tags": {
            "help": "A list of tags to apply to the job",
            "default": None
        },
        "user-tag": {
            "help": "A user tag to apply to the job",
            "default": None
        },
        "task-retry-count": {
            "help": "The number of times to retry a task",
            "default": None
        },
        "task-retry-delay-secs": {
            "help": "The number of seconds to wait before retrying a task",
            "default": None
        }
    }

    def run(self, opts=None):
        if opts is None:
            opts = self.opts
        client = super().run(opts=opts)
        name = getattr(opts, "name")
        schema = getattr(opts, "name")
        expiration = getattr(opts, "expiration")
        priority = getattr(opts, "priority")
        task_tags = getattr(opts, "task_tags")
        user_tag = getattr(opts, "user_tag")
        task_retry_count = getattr(opts, "task_retry_count")
        task_retry_delay_secs = getattr(opts, "task_retry_delay_secs")

        payload = getattr(opts, "payload")
        definitions = getattr(opts, "definitions")

        response = client.create_job(name, payload, schema, expiration, priority, task_tags,
                                     task_retry_count, task_retry_delay_secs, user_tag, definitions)
        print(json.dumps(response))


class ListJobsCommand(HybrikApiCommand):
    DESCRIPTION = "Dolby Hybrik - List Jobs"
    PARAMS = {
        **COMMON_PARAMS,
        "fields": {
            "help": "Fields to return",
            "default": None

        },
        "ids": {
            "help": "Job IDs to return",
            "default": None
        },
        "status": {
            "help": "Job status to filter by",
            "default": "all"
        },
        "take": {
            "help": "Limit the number of jobs returned",
            "default": 100
        },
        "skip": {
            "help": "Offset the number of jobs returned",
            "default": 0
        },
        "sort_field": {
            "help": "Sort the jobs by a field",
            "default": "id"
        },


    }

    def run(self, opts=None):
        if opts is None:
            opts = self.opts

        hybrik = self.init_client(opts=opts)
        response = hybrik.list_jobs()
        print(json.dumps(response))
        return response


class GetJobResultsCommand(HybrikApiCommand):
    DESCRIPTION = "Dolby Hybrik - Get Job Results"
    PARAMS = {
        **COMMON_PARAMS,
        "job-id": {
            "help": "Job ID"
        }
    }

    def run(self, opts=None):
        job_id = getattr(opts, "job-id")
        hybrik = self.init_client(opts=opts)
        response = hybrik.get_job_results(job_id)
        print(response)


class HybrikCommand(CliCommand):
    DESCRIPTION = "Dolby Hybrik Commands"
    SUBCOMMANDS = {
        "create-job": CreateJobCommand,
        "list-jobs": ListJobsCommand,
        "get-job-definition": None,
        "get-job-results": GetJobResultsCommand,
    }
