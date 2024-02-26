# Envoi Transcode

## Usage

### Create Job

```text
usage: envoi_media_convert.py create-job [-h] --settings SETTINGS [--job-template JOB_TEMPLATE] [--priority PRIORITY] [--endpoint ENDPOINT] [--queue QUEUE] [--role-arn ROLE_ARN] [--simulate-reserve-queue] [--status-update-interval STATUS_UPDATE_INTERVAL] [--tags TAGS] [--user-metadata USER_METADATA]

options:
  -h, --help            show this help message and exit
  --settings SETTINGS   JobSettings contains all the transcode settings for a job.
  --job-template JOB_TEMPLATE
                        Optional. When you create a job, you can either specify a job template or specify the transcoding settings individually.
  --priority PRIORITY   Optional. Specify the relative priority for this job. In any given queue, the service begins processing the job with the highest value first. When more than one job has the same priority, the service begins processing the job that you submitted first. If you don't specify a priority, the service uses the default value 0.
  --endpoint ENDPOINT   Optional. The URL of the MediaConvert endpoint that you want to use.
  --queue QUEUE         The name of the MediaConvert queue that you want to use for this job.
  --role-arn ROLE_ARN   The Amazon Resource Name (ARN) for the IAM role that will be assumed when processing the job.
  --simulate-reserve-queue
  --status-update-interval STATUS_UPDATE_INTERVAL
                        Optional. The interval, in seconds, between each status update.
  --tags TAGS           Optional. A list of tags to assign to the job. Tags are metadata that you assign to the job
  --user-metadata USER_METADATA
                        Optional. A list of key-value pairs, in the form of name-value pairs, to associate with the job.
```

```shell
envoi_media_convert.py create-job --settings file://settings.json
```

```shell
envoi_media_convert.py create-job --create-job-request-body file://./create-job-request-body.json
```
