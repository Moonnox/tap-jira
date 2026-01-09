from tap_jira.streams.base import CommonBaseStream


class SettingsStream(CommonBaseStream):
    @property
    def name(self) -> str:
        return "settings"

    @property
    def primary_keys(self) -> list[str]:
        return ["key"]

    def sync(self) -> None:
        self.write_page(
            [
                {
                    "key": "field_ids",
                    "value": self._get_fields(),
                },
                {
                    "key": "timezone",
                    "value": self.context.jira.timezone(),
                },
            ]
        )

    def _get_fields(self):
        fields = self.context.jira.fields()
        sprint_field = next(
            (field for field in fields if self._is_sprint_field(field)), None
        )

        return {"sprint": sprint_field["id"] if sprint_field else None}

    def _is_sprint_field(self, field: dict) -> bool:
        return (
            field.get("name") == "Sprint"
            and field.get("schema", {}).get("type") == "array"
        )
