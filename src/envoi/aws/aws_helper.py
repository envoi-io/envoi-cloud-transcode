from typing import Any

import boto3


class AwsHelper:
    @classmethod
    def init_client(cls, client_type, region_name=None, access_key=None, secret_key=None, profile=None, session_token=None,
                     role_arn=None, client_args_passthrough=None):
            client_args: dict[str, Any] = client_args_passthrough or {}
            if region_name is not None:
                client_args["region_name"] = region_name
            if access_key is not None and secret_key is not None:
                client_args["aws_access_key_id"] = access_key
                client_args["aws_secret_access_key"] = secret_key
            if session_token is not None:
                client_args["aws_session_token"] = session_token
            if profile is not None:
                client_args["profile_name"] = profile

            if role_arn is not None:
                sts = boto3.client('sts')
                assumed_role_object = sts.assume_role(
                    RoleArn=role_arn,
                    RoleSessionName="AssumeRoleSession1"
                )
                credentials = assumed_role_object['Credentials']
                client_args["aws_access_key_id"] = credentials['AccessKeyId']
                client_args["aws_secret_access_key"] = credentials['SecretAccessKey']
                client_args["aws_session_token"] = credentials['SessionToken']

            return boto3.client(client_type, **client_args)