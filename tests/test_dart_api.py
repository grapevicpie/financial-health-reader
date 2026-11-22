import io
import unittest
import zipfile
from unittest.mock import MagicMock

import requests

from dart_api import DartClient, DartError, resolve_direct, search_company_list


class DartClientTests(unittest.TestCase):
    def test_direct_corp_code_bypasses_list(self):
        self.assertEqual(resolve_direct("00126380")["corp_code"], "00126380")
        self.assertIsNone(resolve_direct("알 수 없는 기업"))

    def test_timeout_safe_error_does_not_contain_secret(self):
        secret = "VERY_SECRET_API_KEY_12345"
        def fail(*args, **kwargs):
            raise requests.exceptions.ConnectTimeout(f"request?crtfc_key={secret}")
        client = DartClient(secret, getter=fail, sleeper=lambda _: None)
        with self.assertRaises(DartError) as raised:
            client.company_info()
        self.assertEqual(raised.exception.kind, "connect_timeout")
        self.assertNotIn(secret, str(raised.exception))
        self.assertNotIn("crtfc_key", str(raised.exception))

    def test_http_200_status_is_not_success(self):
        reply = MagicMock()
        reply.status_code = 200
        reply.json.return_value = {"status": "012", "message": "some key info"}
        client = DartClient("x", getter=lambda *args, **kwargs: reply)
        with self.assertRaises(DartError) as raised:
            client.company_info()
        self.assertEqual(raised.exception.code, "012")

    def test_corp_list_zip_parsing(self):
        xml = (b"<?xml version='1.0' encoding='UTF-8'?>"
               b"<result><list><corp_code>00126380</corp_code>"
               b"<corp_name>Samsung</corp_name><stock_code>005930</stock_code>"
               b"</list></result>")
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("CORPCODE.xml", xml)
        reply = MagicMock()
        reply.status_code = 200
        reply.content = buffer.getvalue()
        client = DartClient("x", getter=lambda *args, **kwargs: reply)
        df = client.fetch_corp_codes()
        self.assertEqual(df.iloc[0]["corp_code"], "00126380")
        match = search_company_list(df, "005930")
        self.assertEqual(match.iloc[0]["corp_name"], "Samsung")

    def test_wrong_corp_response_is_rejected(self):
        reply = MagicMock()
        reply.status_code = 200
        reply.json.return_value = {
            "status": "000", "list": [{
                "bsns_year":"2025", "corp_code":"00000000"
            }]
        }
        client = DartClient("x", getter=lambda *args, **kwargs: reply)
        with self.assertRaises(DartError):
            client.fetch_financials("00126380", 2025, "사업보고서", "CFS")

    def test_financials_validate_year(self):
        reply = MagicMock()
        reply.status_code = 200
        reply.json.return_value = {"status":"000", "list":[{"bsns_year":"2024"}]}
        client = DartClient("x", getter=lambda *args, **kwargs: reply)
        with self.assertRaises(DartError):
            client.fetch_financials("00126380", 2025, "사업보고서", "CFS")


if __name__ == "__main__":
    unittest.main()
