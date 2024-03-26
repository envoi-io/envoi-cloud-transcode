# Envoi Video Transcoding SDK

This project is a Python based command line utility CLI for the creating and managing video transcoding and quality assurance jobs using the AWS MediaConvert, Dolby Hybrik, Dolby Resource Agnostic Swarm Processing "RASP", and the Ateme Titan File API's. It provides methods and examples for job creation and job monitoring and interacting with each API.

Envoi is a cloud platform that automates creating, managing, and distributing 24x7, live free ad-supported streaming television "FAST", Subscription or Pay-Per-View OTT (internet delivered) channels.

## Usage

### AWS MediaConvert - Create Job

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

### Ateme Titan File - Create Job

```text
usage: envoi-transcode ateme create-job --no-verify-ssl --base-url BASE_API_URL --username $ATEME_USERNAME --password $ATEME_PASSWORD create-job --job-name $ATEME_JOB_NAME --job-def ateme-job.json --asset-name $ATEME_ASSET_NAME --asset-url $ATEME_ASSET_URL

options:
  -h, --help            show this help message and exit

```

```shell
envoi-transcode create-job --no-verify-ssl --base-url BASE_API_URL --username $ATEME_USERNAME --password $ATEME_PASSWORD create-job --job-name $ATEME_JOB_NAME --job-def ateme-job.json --asset-name $ATEME_ASSET_NAME --asset-url $ATEME_ASSET_URL
```


### Dolby Hybrick - Create Job

```text
usage: envoi_transcode.py hybrik create-job [-h] --settings SETTINGS [--job-template JOB_TEMPLATE] [--priority PRIORITY] [--endpoint ENDPOINT] [--job-tags QUEUE] [--role-arn ROLE_ARN] 

options:
  -h, --help            show this help message and exit
  --settings SETTINGS   JobSettings contains all the transcode settings for a job.
  --job-template JOB_TEMPLATE
                        Optional. When you create a job, you can either specify a job template or specify the transcoding settings individually.
  --priority PRIORITY   Optional. Specify the relative priority for this job. In any given queue, the service begins processing the job with the highest value first. When more than one job has the same priority, the service begins processing the job that you submitted first. If you don't specify a priority, the service uses the default value 0.
  --endpoint ENDPOINT   Optional. The URL of the Dolby Hybrik endpoint that you want to use.
  --queue QUEUE         The name of the MediaConvert queue that you want to use for this job.
  --role-arn ROLE_ARN   The Amazon Resource Name (ARN) for the IAM role that will be assumed when processing the job.
  --job-tags TAGS           Optional. A list of tags to assign to the job. Tags are metadata that you assign to the job

```

```shell
envoi_transcode.py hybrik create-job --settings file://settings.json
```

```shell
envoi_transcode.py hybrik create-job --create-job-request-body file://./create-job-request-body.json
```



### Dolby Resource Agnostic Swarm Processing API "RASP"  - Create Job

```text
usage: envoi_transcode.py rasp create-job [-h] --settings SETTINGS [--vurl-redention-configuration VURL_CONFIG] [--priority PRIORITY] [--endpoint ENDPOINT] [--job-tags QUEUE] [--role-arn ROLE_ARN] 

options:
  -h, --help            show this help message and exit
  --settings SETTINGS   JobSettings contains all the transcode settings for a job.
  --job-template JOB_TEMPLATE
                        Optional. When you create a job, you can either specify a job template or specify the transcoding settings individually.
  --priority PRIORITY   Optional. Specify the relative priority for this job. In any given queue, the service begins processing the job with the highest value first. When more than one job has the same priority, the service begins processing the job that you submitted first. If you don't specify a priority, the service uses the default value 0.
  --endpoint ENDPOINT   Optional. The URL of the Dolby Hybrik endpoint that you want to use.
  --queue QUEUE         The name of the MediaConvert queue that you want to use for this job.
  --role-arn ROLE_ARN   The Amazon Resource Name (ARN) for the IAM role that will be assumed when processing the job.
  --job-tags TAGS           Optional. A list of tags to assign to the job. Tags are metadata that you assign to the job

```

```shell
envoi_transcode.py rasp create-job --settings file://settings.json
```

```shell
envoi_transcode.py rasp create-job --create-job-request-body file://./create-job-request-body.json
```
