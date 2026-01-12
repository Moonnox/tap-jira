from tap_jira.streams.base import CommonBaseStream


class SettingsStream(CommonBaseStream):
    name = "settings"

    @property
    def primary_keys(self) -> list[str]:
        return ["site"]

    def sync(self) -> None:
        fields = self._get_fields()

        self.write_page(
            [
                {
                    "fields": fields,
                    "features": self._get_features(fields),
                    "timezone": self.context.jira.timezone(),
                    "site": self.context.config.site_name,
                }
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

    def _get_features(self, fields: dict) -> list[str]:
        features = []

        if fields.get("sprint"):
            features.append("SPRINTS_SUPPORTED")

        return features
