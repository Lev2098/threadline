from django.apps import AppConfig


class CliConfig(AppConfig):
    """Hosts management commands (an inbound adapter driven by an operator)."""

    name = "comments.adapters.inbound.cli"
    label = "comments_cli"
