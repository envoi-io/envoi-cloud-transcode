#!/usr/bin/env python3
import boto3
import time
import json
import argparse
import sys

# --- Configuration Section ---
AWS_PROFILE = "kj-aws"
REGION = "us-east-1"
PROJECT_NAME = "envoi-media-worker-ecs"
REPO_NAME = "envoi-media-worker-repo"
TASK_FAMILY = "envoi-media-task"
CLUSTER_NAME = "envoi-media-cluster"
ROLE_ARN = "arn:aws:iam::833740154547:role/envoi-media-worker"

# URL of the Dockerfile (ensure this points to the ECS version without Lambda RIC)
DOCKERFILE_URL = "https://raw.githubusercontent.com/envoi-io/envoi-cloud-transcode/refs/heads/main/Dockerfile-ecs.worker"

# URL of the actual media worker Python script
SCRIPT_URL = "https://raw.githubusercontent.com/envoi-io/envoi-cloud-transcode/refs/heads/main/envoi-media-worker-ecs.py"

def get_clients(profile_name):
    session = boto3.Session(profile_name=profile_name)
    return {
        "cb": session.client('codebuild', region_name=REGION),
        "ecr": session.client('ecr', region_name=REGION),
        "ecs": session.client('ecs', region_name=REGION)
    }

def setup_ecr(ecr):
    print(f"Checking ECR Repository: {REPO_NAME}...")
    try:
        ecr.create_repository(repositoryName=REPO_NAME)
    except ecr.exceptions.RepositoryAlreadyExistsException:
        pass
    return ecr.describe_repositories(repositoryNames=[REPO_NAME])['repositories'][0]['repositoryUri']

def create_codebuild_project(cb, repo_uri):
    print("Configuring CodeBuild Project...")
    buildspec = {
        "version": "0.2",
        "phases": {
            "pre_build": {"commands": [
                "aws ecr get-login-password --region $AWS_DEFAULT_REGION | docker login --username AWS --password-stdin $REPOSITORY_URI",
                f"curl -o Dockerfile {DOCKERFILE_URL}"
            ]},
            "build": {"commands": [
                f"docker build --build-arg WORKER_SCRIPT_URL='{SCRIPT_URL}' -t $REPOSITORY_URI:latest ."
            ]},
            "post_build": {"commands": [
                "docker push $REPOSITORY_URI:latest"
            ]}
        }
    }
    
    params = {
        "name": PROJECT_NAME,
        "artifacts": {"type": "NO_ARTIFACTS"}, 
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
        print(f"Created CodeBuild project: {PROJECT_NAME}")
    except cb.exceptions.ResourceAlreadyExistsException:
        print(f"Updating existing CodeBuild project: {PROJECT_NAME}")
        cb.update_project(**params)

def run_build(cb):
    print("Starting Build Process (Building Docker Image)...")
    build_id = cb.start_build(projectName=PROJECT_NAME)['build']['id']
    while True:
        status = cb.batch_get_builds(ids=[build_id])['builds'][0]['buildStatus']
        if status == 'SUCCEEDED': 
            print("\nBuild Successful!")
            return True
        if status in ['FAILED', 'STOPPED']: 
            print(f"\nBuild {status}. Check AWS Console for logs.")
            return False
        sys.stdout.write('.')
        sys.stdout.flush()
        time.sleep(10)

def deploy_ecs(ecs, repo_uri):
    print(f"\nEnsuring ECS Cluster: {CLUSTER_NAME}...")
    ecs.create_cluster(clusterName=CLUSTER_NAME, capacityProviders=['FARGATE'])

    print(f"Registering Task Definition (4 vCPU, 10GB RAM, 200GB Ephemeral Storage)...")
    
    container_env = [
        {'name': 'input_url', 'value': ''}, 
        {'name': 'output_bucket', 'value': ''},
        {'name': 'output_key', 'value': 'output/media'},
        {'name': 'mode', 'value': 'sprite'},
        {'name': 'zoom', 'value': '128'},
        {'name': 'bits', 'value': '8'},
        {'name': 'fps_num', 'value': '24000'},
        {'name': 'fps_den', 'value': '1001'},
        {'name': 'frame_interval', 'value': '120'}
    ]

    ecs.register_task_definition(
        family=TASK_FAMILY,
        networkMode='awsvpc',
        requiresCompatibilities=['FARGATE'],
        cpu='4096',    # 4 vCPUs
        memory='10240', # 10 GB
        executionRoleArn=ROLE_ARN,
        taskRoleArn=ROLE_ARN,
        ephemeralStorage={'sizeInGiB': 200},
        containerDefinitions=[{
            'name': 'media-worker',
            'image': f"{repo_uri}:latest",
            'essential': True,
            'environment': container_env,
            'logConfiguration': {
                'logDriver': 'awslogs',
                'options': {
                    'awslogs-group': f"/ecs/{TASK_FAMILY}",
                    'awslogs-region': REGION,
                    'awslogs-stream-prefix': 'ecs',
                    'awslogs-create-group': 'true'
                }
            }
        }]
    )

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default=AWS_PROFILE)
    args = parser.parse_args()
    
    clients = get_clients(args.profile)
    
    # 1. Prepare Registry
    uri = setup_ecr(clients['ecr'])
    
    # 2. Configure Build
    create_codebuild_project(clients['cb'], uri)
    
    # 3. Build and Push Image
    if run_build(clients['cb']):
        # 4. Update ECS configuration
        deploy_ecs(clients['ecs'], uri)
        print(f"\nDeployment Complete. You can now trigger tasks using the Node.js script.")
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
