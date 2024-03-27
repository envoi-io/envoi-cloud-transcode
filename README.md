# Envoi Media Transcoding SDK

This project is a Python based command line utility CLI for the creating and managing video transcoding and quality assurance jobs using the AWS MediaConvert, Dolby Hybrik Media Cloud, Dolby Resource Agnostic Swarm Processing "RASP", and the Ateme TITAN File API's. It provides methods and examples for job creation and job monitoring and interacting with each API.

Envoi is a cloud platform that automates creating, managing, and distributing 24x7, live free ad-supported streaming television "FAST", Subscription or Pay-Per-View OTT (internet delivered) channels.

## Usage

### AWS MediaConvert - Create Job

```text
./envoi-transcode aws media-convert --help
usage: envoi-transcode aws media-convert [-h] {create-job,create-job-template,create-preset,get-job,list-jobs} ...

positional arguments:
  {create-job,create-job-template,create-preset,get-job,list-jobs}
    create-job          AWS MediaConvert Create Job
    create-job-template
                        AWS MediaConvert Create Job Template
    create-preset       AWS MediaConvert Create Preset
    get-job             AWS MediaConvert Get Job
    list-jobs           AWS MediaConvert List Jobs

options:
  -h, --help            show this help message and exit
```

```shell
envoi-transcode aws media-convert create-job --settings file://settings.json
```

```shell
envoi-transcode aws media-convert create-job --create-job-request-body file://./create-job-request-body.json
```

### Ateme TITAN File - List Jobs

```text

usage: envoi-transcode ateme list-jobs [-h] --base-url BASE_URL [--username USERNAME] [--password PASSWORD] [--token TOKEN] [----no-verify-ssl] [--offset OFFSET] [--limit LIMIT] [--name NAME] [--status STATUS]

options:
  -h, --help           show this help message and exit
  --base-url BASE_URL  Ateme base URL (default: None)
  --username USERNAME  Ateme user (default: None)
  --password PASSWORD  Ateme password (default: None)
  --token TOKEN        Ateme token (default: None)
  ----no-verify-ssl    Turns off SSL Certificate Verification (default: True)
  --offset OFFSET      Offset (default: None)
  --limit LIMIT        Limit (default: None)
  --name NAME          Name (default: None)
  --status STATUS      Status (default: None)

```

```shell
./envoi-transcode ateme list-jobs --no-verify-ssl --base-url $ATEME_BASE_URL --username $ATEME_USERNAME --password $ATEME_PASSWORD
```


### Ateme TITAN File - Get Job

```text

envoi-transcode ateme get-job [-h] --base-url BASE_URL [--username USERNAME] [--password PASSWORD] [--token TOKEN] [----no-verify-ssl] --job-id JOB_ID

options:
  -h, --help           show this help message and exit
  --base-url BASE_URL  Ateme base URL (default: None)
  --username USERNAME  Ateme user (default: None)
  --password PASSWORD  Ateme password (default: None)
  --token TOKEN        Ateme token (default: None)
  ----no-verify-ssl    Turns off SSL Certificate Verification (default: True)
  --job-id JOB_ID      Job ID (default: None)

```

```shell
./envoi-transcode ateme get-job --no-verify-ssl --base-url $ATEME_BASE_URL --username $ATEME_USERNAME --password $ATEME_PASSWORD --job-id $ATEME_JOB_ID_USERNAME
```

### Ateme TITAN File - Create Job

```text

usage: envoi-transcode ateme create-job --no-verify-ssl --base-url BASE_API_URL --username $ATEME_USERNAME --password $ATEME_PASSWORD create-job --job-name $ATEME_JOB_NAME --job-def ateme-job.json --asset-name $ATEME_ASSET_NAME --asset-url $ATEME_ASSET_URL


usage: envoi-transcode ateme create-job [-h] --base-url BASE_URL [--username USERNAME] [--password PASSWORD] [--token TOKEN] [----no-verify-ssl] --job-def JOB_DEF [--job-name JOB_NAME]
                                        [--input-asset-name INPUT_ASSET_NAME] [--input-asset-url INPUT_ASSET_URL]

options:
  -h, --help            show this help message and exit
  --base-url BASE_URL   Ateme base URL (default: None)
  --username USERNAME   Ateme user (default: None)
  --password PASSWORD   Ateme password (default: None)
  --token TOKEN         Ateme token (default: None)
  ----no-verify-ssl     Turns off SSL Certificate Verification (default: True)
  --job-def JOB_DEF     The Job Definition (default: None)
  --job-name JOB_NAME   Job Name (default: None)
  --input-asset-name INPUT_ASSET_NAME
                        Asset Name (default: asset_1)
  --input-asset-url INPUT_ASSET_URL
                        Asset URL (default: None)

```

```shell
./envoi-transcode ateme create-job --no-verify-ssl --base-url $ATEME_BASE_URL --username $ATEME_USERNAME --password $ATEME_PASSWORD --job-name "test-job2" --job-def file:///ateme-test-job.json
```


### Dolby Hybrik - Create Job

```text
usage: envoi-transcode hybrik create-job [-h] --settings SETTINGS [--job-template JOB_TEMPLATE] [--priority PRIORITY] [--endpoint ENDPOINT] [--job-tags QUEUE] [--role-arn ROLE_ARN] 

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
envoi-transcode hybrik create-job --settings file://settings.json
```

```shell
envoi-transcode hybrik create-job --create-job-request-body file://./create-job-request-body.json
```



### Dolby Resource Agnostic Swarm Processing API "RASP"  - Create Job

```text
usage: envoi-transcode rasp create-job [-h] --settings SETTINGS [--vurl-redention-configuration VURL_CONFIG] [--priority PRIORITY] [--endpoint ENDPOINT] [--job-tags QUEUE] [--role-arn ROLE_ARN] 

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
envoi-transcode rasp create-job --settings file://settings.json
```

```shell
envoi-transcode rasp create-job --create-job-request-body file://./create-job-request-body.json
```
