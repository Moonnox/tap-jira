import singer

from tap_jira import discover
from tap_jira.context import Context

REQUIRED_CONFIG_KEYS = [
    "start_date",
    "user_agent",
    "site_name",
    "access_token",
    "refresh_token",
    "client_id",
    "client_secret",
]
LOGGER = singer.get_logger()


@singer.utils.handle_top_exception(LOGGER)
def run():
    args = singer.utils.parse_args(REQUIRED_CONFIG_KEYS)
    context = Context.from_args(args)

    if args.discover:
        catalog = discover.run(context)
        catalog.dump()

        print()  # Add a newline
