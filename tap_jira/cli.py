import singer

from singer.catalog import Catalog

from tap_jira import discover, sync
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
    context = Context.from_args(args, LOGGER)

    catalog: Catalog = args.catalog
    if not catalog:
        catalog = discover.run(context)

    if args.discover:
        catalog.dump()

        print()  # Add a newline
    else:
        sync.run(context, catalog)
