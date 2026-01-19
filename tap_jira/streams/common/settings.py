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
                    "account": self._get_account(),
                    "fields": fields,
                    "features": self._get_features(fields),
                    "site": self.context.config.site_name,
                }
            ]
        )

    def _get_account(self):
        account = self.context.jira.myself()

        return {
            "id": account["accountId"],
            "active": account.get("active"),
            "name": account.get("displayName"),
            "email_address": account.get("emailAddress"),
            "avatar": self._get_account_avatar(account),
            "tz": account.get("timeZone"),
        }

    def _get_account_avatar(self, account: dict) -> str | None:
        return account.get("avatarUrls", {}).get("48x48")

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
