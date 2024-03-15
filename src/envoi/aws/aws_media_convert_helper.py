from envoi.aws.aws_helper import AwsHelper


class AwsMediaConvertHelper:

    def __init__(self, **kwargs):
        self.media_convert = AwsHelper.init_client('mediaconvert', **kwargs)

    def create_job(self,
                   acceleration_settings,
                   billing_tags_source,
                   client_request_token,
                   hop_destinations,
                   job_template,
                   priority,
                   queue,
                   role,
                   settings,
                   status_update_interval,
                   tags,
                   user_metadata,
                   ):
        """
        Create a job

        see https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/mediaconvert/client/create_job.html


        :param acceleration_settings:
        :param billing_tags_source:
        :param client_request_token:
        :param hop_destinations:
        :param job_template:
        :param priority:
        :param queue:
        :param role:
        :param settings:
        :param status_update_interval:
        :param tags:
        :param user_metadata:
        :return:
        """
        create_job_args = {}
        if acceleration_settings is not None:
            create_job_args["AccelerationSettings"] = acceleration_settings
        if billing_tags_source is not None:
            create_job_args["BillingTagsSource"] = billing_tags_source
        if client_request_token is not None:
            create_job_args["ClientRequestToken"] = client_request_token
        if hop_destinations is not None:
            create_job_args["HopDestinations"] = hop_destinations
        if job_template is not None:
            create_job_args["JobTemplate"] = job_template
        if priority is not None:
            create_job_args["Priority"] = priority
        if queue is not None:
            create_job_args["Queue"] = queue
        if role is not None:
            create_job_args["Role"] = role
        if settings is not None:
            create_job_args["Settings"] = settings
        if status_update_interval is not None:
            create_job_args["StatusUpdateInterval"] = status_update_interval
        if tags is not None:
            create_job_args["Tags"] = tags
        if user_metadata is not None:
            create_job_args["UserMetadata"] = user_metadata

        return self.media_convert.create_job(**create_job_args)

    def create_template(self, name, description, settings, tags):
        """
        Create a template

        see https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/mediaconvert/client/create_job_template.html

        :param name:
        :param description:
        :param settings:
        :param tags:
        :return:
        """
        return self.media_convert.create_job_template(Name=name, Description=description, Settings=settings, Tags=tags)

    def get_job(self, job_id):
        """
        Get job by job_id

        see https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/mediaconvert/client/get_job.html

        :param job_id:
        :return:
        """
        return self.media_convert.get_job(Id=job_id)

    def list_jobs(self, max_results, next_token, order, queue, status):
        """
        List jobs

        see https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/mediaconvert/client/list_jobs.html

        :param max_results:
        :param next_token:
        :param order:
        :param queue:
        :param status:
        :return:
        """
        return self.media_convert.list_jobs(MaxResults=max_results, NextToken=next_token, Order=order, Queue=queue,
                                            Status=status)
