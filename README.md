## Envoi Cloud Transcoding SDK

This project is a Python-based command-line utility ("CLI") for creating and managing video transcoding and quality assurance jobs using the **AWS MediaConvert**, **Dolby Hybrik Media Cloud**, **Dolby Resource Agnostic Swarm Processing ("RASP")**, and **Ateme TITAN File** API's. It provides methods and examples for job creation and job monitoring and interacting with each API.

Envoi is a cloud platform that automates creating, managing, and distributing 24x7, live free ad-supported streaming television ("FAST"), Subscription or Pay-Per-View OTT (internet-delivered) channels.

-----

### Usage

### AWS MediaConvert ☁️

The `aws media-convert` subcommands are a wrapper for the AWS MediaConvert API, specifically using the **Boto3** library. These commands allow you to create and manage transcoding jobs, presets, and job templates.

#### **Create Job (`create-job`)**

  * `--settings file://settings.json`: This is a required argument that specifies the **path to a JSON file** containing the full MediaConvert job settings. The JSON file defines all aspects of the transcoding job, including the input and output file paths, codecs, resolutions, and other encoding parameters. The `file://` prefix indicates that the settings are being loaded from a local file.
  * `--create-job-request-body file://./create-job-request-body.json`: This is an alternative to the `--settings` flag. It allows you to provide a complete JSON request body for the `CreateJob` API call. This gives you granular control over all possible API parameters, including metadata, tags, and queue settings, not just the encoding settings.

**Example: Creating a Transcoding Job**

1.  **Create a `settings.json` file**. This file must follow the AWS MediaConvert API schema.

    ```json
    {
      "Inputs": [
        {
          "FileInput": "s3://your-input-bucket/your_source_video.mp4"
        }
      ],
      "OutputGroups": [
        {
          "OutputGroupSettings": {
            "Type": "FILE_GROUP_SETTINGS",
            "FileGroupSettings": {
              "Destination": "s3://your-output-bucket/output/"
            }
          },
          "Outputs": [
            {
              "VideoDescription": {
                "CodecSettings": {
                  "Codec": "H_264",
                  "H264Settings": {
                    "Bitrate": 5000000,
                    "GopSize": 90
                  }
                }
              },
              "AudioDescriptions": [
                {
                  "CodecSettings": {
                    "Codec": "AAC",
                    "AacSettings": {
                      "Bitrate": 192000
                    }
                  }
                }
              ],
              "NameModifier": "_high_res"
            }
          ]
        }
      ]
    }
    ```

2.  **Run the command**. Make sure you've configured your AWS credentials (e.g., via `aws configure`).

    ```bash
    ./envoi-transcode aws media-convert create-job --settings file://settings.json
    ```

-----

### Ateme TITAN File 🗂️

The `ateme` subcommands are designed to interact with the Ateme TITAN File REST API. Authentication is managed through a token, which is automatically retrieved using the provided credentials.

#### **List Jobs (`list-jobs`)**

  * `--base-url BASE_URL`: **(Required)** The base URL of your Ateme TITAN File API endpoint. This is the root address for all API calls.
  * `--username USERNAME`: The username for authenticating with the Ateme API.
  * `--password PASSWORD`: The password for the specified user.
  * `--token TOKEN`: An optional access token. If you already have a valid token, you can provide it directly instead of using the username and password. The code shows the client will get a new token if one isn't provided.
  * `--no-verify-ssl`: A boolean flag that, when present, **disables SSL certificate verification**. This is useful for development environments or when connecting to a server with a self-signed certificate, but it's not recommended for production.
  * `--offset OFFSET`: An integer that specifies the **starting point for the list of jobs**. This is used for pagination, allowing you to skip a certain number of jobs from the beginning of the list.
  * `--limit LIMIT`: An integer that specifies the **maximum number of jobs to return** in a single request. Also used for pagination.
  * `--name NAME`: A string to filter jobs by their name.
  * `--status STATUS`: A string to filter jobs by their current status (e.g., `completed`, `pending`, `error`).

**Example: Listing Jobs**

1.  **Set environment variables**. Replace the placeholder values with your actual credentials.

    ```bash
    export ATEME_BASE_URL="https://your-ateme-instance.com"
    export ATEME_USERNAME="your-username"
    export ATEME_PASSWORD="your-password"
    ```

2.  **Run the command**.

    ```bash
    ./envoi-transcode ateme list-jobs --base-url $ATEME_BASE_URL --username $ATEME_USERNAME --password $ATEME_PASSWORD --status completed
    ```

#### **Get Job (`get-job`)**

  * `--job-id JOB_ID`: **(Required)** The unique identifier for the specific job you want to retrieve details for.
  * `--base-url`, `--username`, `--password`, `--token`, `--no-verify-ssl`: These are the same authentication and connection arguments as for the `list-jobs` command.

**Example: Creating a Job**

1.  **Create a `ateme-job.json` definition file.**

    ```json
    {
      "name": "My New Transcode Job",
      "template_id": "your-template-id",
      "inputs": [
        {
          "asset_url": "s3://your-input-bucket/source_file.mov"
        }
      ],
      "outputs": [
        {
          "asset_url": "s3://your-output-bucket/output/encoded.mp4"
        }
      ]
    }
    ```

2.  **Run the command**. The `--job-def` flag points to this file.

    ```bash
    ./envoi-transcode ateme create-job --no-verify-ssl \
      --base-url $ATEME_BASE_URL --username $ATEME_USERNAME \
      --password $ATEME_PASSWORD --job-name "new-test-job" \
      --job-def ateme-job.json
    ```

-----

### Dolby Hybrik 🎶

The `dolby hybrik` subcommands are used to interact with the Dolby Hybrik Media Cloud API. The client handles a two-step authentication process: a basic `oapi` key/secret for the initial call, and then an `auth` key/secret for retrieving a session token.

#### **Create Job (`create-job`)**

  * `--api-url API_URL`: The base URL for the Hybrik API. Defaults to `https://api-demo.hybrik.com/v1` if not specified.
  * `--oapi-key OAPI_KEY`: The key for **OAPI (Organization API)** authentication.
  * `--oapi-secret OAPI_SECRET`: The secret for OAPI authentication.
  * `--auth-key AUTH_KEY`: The key for user authentication to get a session token.
  * `--auth-secret AUTH_SECRET`: The secret for user authentication.
  * `--name NAME`: A user-defined, visible name for the job.
  * `--payload PAYLOAD`: **(Required)** A JSON object representing the job definition. The code shows this is a string, which can be a path to a file (`file://`) or the raw JSON content itself.
  * `--schema SCHEMA`: An optional string to specify the job schema. The default is "hybrik".
  * `--definitions DEFINITIONS`: A JSON object for defining global string replacements within the job payload, allowing for templates.
  * `--expiration EXPIRATION`: An integer representing the expiration time in minutes for the job after it's completed.
  * `--priority PRIORITY`: An integer that sets the job's priority. The higher the number, the higher the priority. The default is 100.
  * `--task-tags TASK_TAGS`: A list of tags to apply to the job for organization and filtering.
  * `--user-tag USER_TAG`: A single user tag to apply to the job.
  * `--task-retry-count TASK_RETRY_COUNT`\*\*: An integer for the number of times to retry a failed task.
  * `--task-retry-delay-secs TASK_RETRY_DELAY_SECS`: An integer for the number of seconds to wait before retrying a task.

**Example: Creating a Transcoding Job**

1.  **Set environment variables** for your Hybrik credentials.

    ```bash
    export HYBRIK_OAPI_KEY="your-oapi-key"
    export HYBRIK_OAPI_SECRET="your-oapi-secret"
    export HYBRIK_AUTH_KEY="your-auth-key"
    export HYBRIK_AUTH_SECRET="your-auth-secret"
    ```

2.  **Create a `hybrik-job.json` payload file.** This JSON defines the workflow and tasks.

    ```json
    {
      "payload": {
        "sources": [
          {
            "location": "s3://your-hybrik-input-bucket/input.mov",
            "name": "input_file"
          }
        ],
        "tasks": [
          {
            "label": "transcode_task",
            "actions": [
              {
                "action": "transcode",
                "inputs": [
                  {
                    "source": "input_file"
                  }
                ],
                "outputs": [
                  {
                    "location": "s3://your-hybrik-output-bucket/output.mp4"
                  }
                ]
              }
            ]
          }
        ]
      }
    }
    ```

3.  **Run the command.** The `--payload` flag should point to your JSON file.

    ```bash
    ./envoi-transcode dolby hybrik create-job \
      --oapi-key $HYBRIK_OAPI_KEY --oapi-secret $HYBRIK_OAPI_SECRET \
      --auth-key $HYBRIK_AUTH_KEY --auth-secret $HYBRIK_AUTH_SECRET \
      --name "My First Hybrik Job" --payload file://hybrik-job.json
    ```

-----

### Dolby Resource Agnostic Swarm Processing (RASP) 📡

The `dolby rasp` subcommand is for asset management on the RASP platform.

#### **Create Asset (`create-asset`)**

  * `--base-url BASE_URL`: The base URL for the RASP API.
  * `--name NAME`: An optional name for the asset.
  * `--url URL`: An optional URL where the asset is located (e.g., an S3 bucket URL).
  * `--mime-type MIME_TYPE`: An optional MIME type of the asset, such as `video/mp4`.

**Example: Creating a New Asset**

1.  **Run the command.** Provide the `base-url`, `name`, `url`, and `mime-type` as arguments.

    ```bash
    ./envoi-transcode dolby rasp create-asset \
      --base-url "https://api.dolbyrasp.com" \
      --name "Product Launch Video" \
      --url "s3://my-cloud-storage/product-video.mov" \
      --mime-type "video/quicktime"
    ```
