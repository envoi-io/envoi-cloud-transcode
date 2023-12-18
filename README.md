# Envoi MediaConvert Utility

## Installation of

### Clone Repository

```shell
git clone https://github.com/envoi-io/envoi-media-convert.git
```

### Change Directory to the Project Root

```shell
cd envoi-media-convert
```

### Create Symbolic Link

```shell
ln -s `realpath envoi_media_convert.py` /usr/local/bin
```

## Usage

### Create Job

```text
usage: envoi_media_convert.py create-job [-h] [--settings SETTINGS] [--create-job-request-body CREATE_JOB_REQUEST_BODY] [--job-template JOB_TEMPLATE] [--priority PRIORITY] [--endpoint ENDPOINT] [--queue QUEUE] [--role-arn ROLE_ARN] [--simulate-reserve-queue {DISABLED,ENABLED}]
                                         [--status-update-interval {SECONDS_10,SECONDS_12,SECONDS_15,SECONDS_20,SECONDS_30,SECONDS_60,SECONDS_120,SECONDS_180,SECONDS_240,SECONDS_300,SECONDS_360,SECONDS_420,SECONDS_480,SECONDS_540,SECONDS_600}] [--tags TAGS] [--user-metadata USER_METADATA]

options:
  -h, --help            show this help message and exit
  --settings SETTINGS   Settings contains all the transcode settings for a job. This is a required argument if not provided in the `create-job-request-body` argument.
  --create-job-request-body CREATE_JOB_REQUEST_BODY
                        Optional. A JSON string that contains all the transcode settings for a job. This can be used to run a job using the `Create job request body` in the MediaConvert console.
  --job-template JOB_TEMPLATE
                        Optional. When you create a job, you can either specify a job template or specify the transcoding settings individually.
  --priority PRIORITY   Optional. Specify the relative priority for this job. In any given queue, the service begins processing the job with the highest value first. When more than one job has the same priority, the service begins processing the job that you submitted first. If you don't specify a priority, the service uses the default value 0.
  --endpoint ENDPOINT   Optional. The URL of the MediaConvert endpoint that you want to use.
  --queue QUEUE         The name of the MediaConvert queue that you want to use for this job.
  --role-arn ROLE_ARN   The Amazon Resource Name (ARN) for the IAM role that will be assumed when processing the job.
  --simulate-reserve-queue {DISABLED,ENABLED}
                        Optional. Enable this setting when you run a test job to estimate how many reserved transcoding slots (RTS) you need. When this is enabled, MediaConvert runs your job from an on-demand queue with similar performance to what you will see with one RTS in a reserved queue. This setting is disabled by default.
  --status-update-interval {SECONDS_10,SECONDS_12,SECONDS_15,SECONDS_20,SECONDS_30,SECONDS_60,SECONDS_120,SECONDS_180,SECONDS_240,SECONDS_300,SECONDS_360,SECONDS_420,SECONDS_480,SECONDS_540,SECONDS_600}
                        Optional. Specify how often MediaConvert sends STATUS_UPDATE events to Amazon CloudWatch Events. Set the interval, in seconds, between status updates. MediaConvert sends an update at this interval from the time the service begins processing your job to the time it completes the transcode or encounters an error.
  --tags TAGS           Optional. A list of tags to assign to the job. Tags are metadata that you assign to the job.
  --user-metadata USER_METADATA
                        Optional. A list of key-value pairs, in the form of name-value pairs, to associate with the job.
```

Create a job specifying just the job settings from a file
```shell
envoi_media_convert.py create-job --settings file://settings.json
```

Create a job specifying the full request body from a file

> You can get a full request body from an existing job by navigating to `MediaConvert console > Job summary` and pressing the `View JSON` button. 
```shell
envoi_media_convert.py create-job --create-job-request-body file://./create-job-request-body.json
```