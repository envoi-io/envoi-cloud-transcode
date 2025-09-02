# Envoi Cloud Transcoding SDK

This project is a Python based command line utility ("CLI") for the creating and managing video transcoding and quality assurance jobs using the AWS MediaConvert, Dolby Hybrik Media Cloud, Dolby Resource Agnostic Swarm Processing "RASP", and Ateme TITAN File API's. It provides methods and examples for job creation and job monitoring and interacting with each API.

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
  --no-verify-ssl    Turns off SSL Certificate Verification (default: True)
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
  --no-verify-ssl    Turns off SSL Certificate Verification (default: True)
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
  --no-verify-ssl     Turns off SSL Certificate Verification (default: True)
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
usage: envoi-transcode dolby hybrik create-job [-h] [--api-url API_URL] [--oapi-key OAPI_KEY] [--oapi-secret OAPI_SECRET] [--auth-key AUTH_KEY] [--auth-secret AUTH_SECRET] [--name NAME] [--payload PAYLOAD]
                                               [--schema SCHEMA] [--definitions DEFINITIONS] [--expiration EXPIRATION] [--priority PRIORITY] [--task-tags TASK_TAGS] [--user-tag USER_TAG]
                                               [--task-retry-count TASK_RETRY_COUNT] [--task-retry-delay-secs TASK_RETRY_DELAY_SECS]

options:
  -h, --help            show this help message and exit
  --api-url API_URL     The URL of the Hybrik API (default: https://api-demo.hybrik.com/v1)
  --oapi-key OAPI_KEY   Hybrik OAPI Key (default: None)
  --oapi-secret OAPI_SECRET
                        Hybrik OAPI Secret (default: None)
  --auth-key AUTH_KEY   Hybrik Auth Key (default: None)
  --auth-secret AUTH_SECRET
                        Hybrik Auth Secret (default: None)
  --name NAME           The visible name of the job (default: None)
  --payload PAYLOAD     Job Definition. This must be a JSON object (default: None)
  --schema SCHEMA       Optional. Hybrik will be supporting some third-party job schemas, which can be specified in this string. The default is "hybrik". (default: None)
  --definitions DEFINITIONS
                        Global string replacements can be defined in this section. Anything in the Job JSON that is enclosed with double parentheses such as {{to_be_replaced}} will be replaced. (default: None)
  --expiration EXPIRATION
                        Expiration (in minutes) of the job. A completed job will expire and be deleted after [expiration] minutes. Default is 30 days. (default: None)
  --priority PRIORITY   The priority of the job (default: 100)
  --task-tags TASK_TAGS
                        A list of tags to apply to the job (default: None)
  --user-tag USER_TAG   A user tag to apply to the job (default: None)
  --task-retry-count TASK_RETRY_COUNT
                        The number of times to retry a task (default: None)
  --task-retry-delay-secs TASK_RETRY_DELAY_SECS
                        The number of seconds to wait before retrying a task (default: None)

```

```shell
envoi-transcode dolby hybrik create-job [--api-url API_URL] [--oapi-key OAPI_KEY] [--oapi-secret OAPI_SECRET] [--auth-key AUTH_KEY] [--auth-secret AUTH_SECRET] [--name NAME] [--payload PAYLOAD] [--schema SCHEMA] [--definitions DEFINITIONS] [--expiration EXPIRATION] [--priority PRIORITY] [--task-tags TASK_TAGS] [--user-tag USER_TAG] [--task-retry-count TASK_RETRY_COUNT] [--task-retry-delay-secs TASK_RETRY_DELAY_SECS]
```



### Dolby Resource Agnostic Swarm Processing API "RASP"  - Create Job

```text
usage: envoi-transcode dolby rasp create-asset [-h] [--base-url BASE_URL] [--name NAME] [--url URL] [--mime-type MIME_TYPE]

options:
  -h, --help            show this help message and exit
  --base-url BASE_URL   Base URL of the RASP API (default: None)
  --name NAME           Name of the asset (default: None)
  --url URL             URL of the asset (default: None)
  --mime-type MIME_TYPE
                        MIME type of the asset (default: None)

```

```shell
envoi-transcode dolby rasp create-asset [--base-url BASE_URL] [--name NAME] [--url URL] [--mime-type MIME_TYPE]
```
