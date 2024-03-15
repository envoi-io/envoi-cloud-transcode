from envoi.cli import CliCommand

from envoi.cli.transcode.aws.media_convert import AwsMediaConvertCommand


class AwsCommand(CliCommand):
    DESCRIPTION = "AWS Commands"
    SUBCOMMANDS = {
        'media-convert': AwsMediaConvertCommand
    }
