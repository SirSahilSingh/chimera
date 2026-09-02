import os
import unittest
from unittest.mock import patch

from backend.app.core.config import load_settings


class ExotelConfigurationTests(unittest.TestCase):
    def test_derives_current_flow_url_from_account_and_app_ids(self) -> None:
        with patch.dict(
            os.environ,
            {
                "EXOTEL_PORTAL_BASE_URL": "https://my.exotel.com",
                "EXOTEL_ACCOUNT_SID": "account-sid",
                "EXOTEL_APP_ID": "flow-123",
            },
            clear=False,
        ):
            settings = load_settings()

        self.assertEqual(
            settings.exotel_flow_url,
            "https://my.exotel.com/account-sid/exoml/start_voice/flow-123",
        )

    def test_explicit_flow_url_remains_authoritative(self) -> None:
        with patch.dict(
            os.environ,
            {
                "EXOTEL_FLOW_URL": "https://my.exotel.in/custom-flow",
                "EXOTEL_ACCOUNT_SID": "account-sid",
                "EXOTEL_APP_ID": "flow-123",
            },
            clear=False,
        ):
            settings = load_settings()

        self.assertEqual(settings.exotel_flow_url, "https://my.exotel.in/custom-flow")


if __name__ == "__main__":
    unittest.main()
