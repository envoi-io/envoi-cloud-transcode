from envoi.cli import CliCommand

from .hybrik import HybrikCommand
from .rasp import RaspCommand


class DolbyCommand(CliCommand):
    DESCRIPTION = "Dolby Related Commands"
    SUBCOMMANDS = {
        'hybrik': HybrikCommand,
        'rasp': RaspCommand
    }