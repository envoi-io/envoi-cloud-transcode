#!/usr/bin/env python3
import boto3
import time
import json
import argparse
import sys

# --- Configuration Section ---
AWS_PROFILE = "kj-aws"  # <--- Set your profile name here
REGION = "us-east-1"
PROJECT_NAME = "envoi-media-worker"
REPO_NAME = "envoi-media-worker-lambda"
LAMBDA_FUNC_NAME = "envoi-media-worker"
ROLE_ARN = "arn:aws:iam::833740154547:role/envoi-media-worker"

# URLs
DOCKERFILE_URL = "https://raw.githubusercontent.com/envoi-io/envoi-cloud-transcode/refs/heads/main/Dockerfile.worker"
SCRIPT_URL = "https://raw.githubusercontent.com/envoi-io/envoi-cloud-transcode/refs/heads/main/generate_sprite_v2.py"

def get_clients(profile_name):
    """Initializes AWS clients using the configured profile."""
    try:
        print(f"--- Using AWS Profile: {profile_name} ---")
        session = boto3.Session(profile_name=profile_name)
        return {
            "cb": session.client('codebuild', region_name=REGION),
            "ecr": session.client('ecr', region_name=REGION),
            "awslambda": session.client('lambda', region_name=REGION)
        }
    except Exception as e:
        print(f"Error: Could not find profile '{profile_name}'. Check ~/.aws/credentials")
        print(f"Details: {e}")
        sys.exit(1)

def setup_ecr(ecr):
    print(f"Checking ECR Repository: {REPO_NAME}...")
    try:
        ecr.create_repository(repositoryName=REPO_NAME)
    except ecr.exceptions.RepositoryAlreadyExistsException:
        pass
    
    desc = ecr.describe_repositories(repositoryNames=[REPO_NAME])
    return desc['repositories'][0]['repositoryUri']

def create_codebuild_project(cb, repo_uri):
    print("Configuring CodeBuild Project...")
    buildspec = {
        "version": "0.2",
        "phases": {
            "pre_build": {
                "commands": [
                    "echo Logging in to Amazon ECR...",
                    "aws ecr get-login-password --region $AWS_DEFAULT_REGION | docker login --username AWS --password-stdin $REPOSITORY_URI",
                    f"curl -o Dockerfile {DOCKERFILE_URL}"
                ]
            },
            "build": {
                "commands": [
                    "echo Building Docker image for Lambda...",
                    f"docker build --build-arg WORKER_SCRIPT_URL='{SCRIPT_URL}' -t $REPOSITORY_URI:latest ."
                ]
            },
            "post_build": {
                "commands": [
                    "echo Pushing image to ECR...",
                    "docker push $REPOSITORY_URI:latest"
                ]
            }
        }
    }

    params = {
        "name": PROJECT_NAME,
        "artifacts": {'type': 'NO_ARTIFACTS'},
        "environment": {
            'type': 'LINUX_CONTAINER',
            'image': 'aws/codebuild/amazonlinux2-x86_64-standard:5.0',
            'computeType': 'BUILD_GENERAL1_SMALL',
            'environmentVariables': [{'name': 'REPOSITORY_URI', 'value': repo_uri}],
            'privilegedMode': True
        },
        "serviceRole": ROLE_ARN,
        "source": {
            'type': 'NO_SOURCE',
            'buildspec': json.dumps(buildspec)
        }
    }

    try:
        cb.create_project(**params)
    except cb.exceptions.ResourceAlreadyExistsException:
        cb.update_project(**params)

def run_build(cb):
    print("Starting Build Process (this takes 2-4 minutes)...")
    response = cb.start_build(projectName=PROJECT_NAME)
    build_id = response['build']['id']
    
    while True:
        status_resp = cb.batch_get_builds(ids=[build_id])
        status = status_resp['builds'][0]['buildStatus']
        if status == 'SUCCEEDED':
            print("\nBuild SUCCEEDED")
            return True
        elif status in ['FAILED', 'STOPPED']:
            print(f"\nBuild {status}. Check CloudWatch Logs for CodeBuild.")
            return False
        
        sys.stdout.write('.')
        sys.stdout.flush()
        time.sleep(10)

def deploy_lambda(awslambda, repo_uri):
    image_uri = f"{repo_uri}:latest"
    try:
        print(f"Creating Lambda Function: {LAMBDA_FUNC_NAME}...")
        awslambda.create_function(
            FunctionName=LAMBDA_FUNC_NAME,
            PackageType='Image',
            Code={'ImageUri': image_uri},
            Role=ROLE_ARN,
            Timeout=600,  # 10 minutes for heavy processing
            MemorySize=3008 # High memory helps CPU speed in Lambda
        )
    except awslambda.exceptions.ResourceConflictException:
        print("Lambda already exists, updating image...")
        awslambda.update_function_code(FunctionName=LAMBDA_FUNC_NAME, ImageUri=image_uri)

def main():
    # Allow command line to override the config variable if needed
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default=AWS_PROFILE)
    args = parser.parse_args()

    clients = get_clients(args.profile)
    
    uri = setup_ecr(clients['ecr'])
    create_codebuild_project(clients['cb'], uri)
    
    if run_build(clients['cb']):
        deploy_lambda(clients['awslambda'], uri)
        print("\nSUCCESS: Media Processor is live on Lambda.")
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()