discovery:
	@tap-jira -c config.json --discover > catalog.json

sync:
	@tap-jira -c config.json --catalog catalog.json --state state.json
