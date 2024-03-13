import sys

from envoi.cli import CliApp
# from envoi.cli.transcode.aws import AwsCommand
from envoi.cli.transcode.dolby import DolbyCommand
# from envoi.cli.transcode.envoi import EnvoiCommand
# from envoi.cli.channels.gcp import GcpCommand

import logging

LOG = logging.getLogger(__name__)


class EnvoiTranscodeCli(CliApp):
    DESCRIPTION = "Envoi Transcode Command Line Utility"
    PARAMS = {
        "log_level": {
            "flags": ['--log-level'],
            "type": str,
            "default": "INFO",
            "help": "Set the logging level (options: DEBUG, INFO, WARNING, ERROR, CRITICAL)"
        },
    }
    SUBCOMMANDS = {
        'aws': None,  # AwsCommand,
        'dolby': DolbyCommand,
        'envoi': None,  # EnvoiCommand,
        'gcp': None,  # GcpCommand
    }


def main():
    cli = EnvoiTranscodeCli(auto_exec=False)
    return cli.run()


if __name__ == "__main__":
    sys.exit(main())
