import unittest

import pandas as pd

from finance import (
    empty_data, amount, from_dart, from_wide, parse_paste,
    account_value, compute_metrics, health_screening_score,
)


class FinancialCoreTests(unittest.TestCase):
    def test_amount_negatives_and_missing(self):
        self.assertEqual(amount("(1,230)"), -1230)
        self.assertEqual(amount("△123"), -123)
        self.assertIsNone(amount("-"))

    def test_account_not_accidentally_substring(self):
        df = from_wide(pd.DataFrame({
            "항목": ["금융수익", "기타매출채권", "매출액", "자산총계"],
            "2025": [999, 444, 300, 400],
        }), "손익계산서", 1, "test")
        value, _ = account_value(df, "revenue", "2025")
        self.assertEqual(value, 300)

    def test_non_krw_dart_is_not_assumed_won(self):
        rows = [{
            "sj_div": "IS", "account_nm": "매출액", "currency": "USD",
            "thstrm_amount": "120", "frmtrm_amount": "110",
        }]
        with self.assertRaises(ValueError):
            from_dart(rows, 2025, "사업보고서")

    def test_quarter_cumulative_preference(self):
        rows = [{
            "sj_div": "IS", "account_nm": "매출액",
            "account_id": "ifrs-full_Revenue",
            "thstrm_amount": "100", "thstrm_add_amount": "260",
            "frmtrm_amount": "80", "frmtrm_add_amount": "220",
            "bsns_year": "2025",
        }]
        df = from_dart(rows, 2025, "반기보고서")
        self.assertEqual(account_value(df, "revenue", "2025")[0], 260)
        self.assertEqual(account_value(df, "revenue", "2024")[0], 220)

    def test_dart_periods_annual(self):
        rows = [{
            "sj_div": "BS", "account_nm": "자산총계",
            "account_id": "ifrs-full_Assets",
            "thstrm_amount": "1000", "frmtrm_amount": "900",
            "bfefrmtrm_amount": "850",
        }]
        df = from_dart(rows, 2025, "사업보고서")
        self.assertEqual(set(df["period"]), {"2025", "2024", "2023"})

    def test_missing_metrics_does_not_invent_score(self):
        df = parse_paste("항목\t2025\n매출액\t1000", "손익계산서", 1)
        result, _, quality = compute_metrics(df)
        self.assertIsNone(health_screening_score(result, quality))
        self.assertTrue(any("영업이익" in x for x in quality))

    def test_balance_equation_mismatch_flag(self):
        df = pd.concat([
            from_wide(pd.DataFrame({"항목": ["자산총계", "부채총계", "자본총계"], "2025": [1000, 500, 200]}),
                      "재무상태표", 1000000, "test"),
            from_wide(pd.DataFrame({"항목": ["매출액", "영업이익", "당기순이익"], "2025": [1000, 100, 80]}),
                      "손익계산서", 1000000, "test"),
            from_wide(pd.DataFrame({"항목": ["영업활동현금흐름"], "2025": [90]}),
                      "현금흐름표", 1000000, "test"),
        ], ignore_index=True)
        m, _, q = compute_metrics(df)
        self.assertTrue(any("차이" in x for x in q))
        self.assertIsNone(health_screening_score(m, q))

    def test_no_growth_from_quarterly(self):
        df = from_wide(pd.DataFrame({"항목": ["매출액"], "2024": [100], "2025": [200]}),
                       "손익계산서", 1, "test")
        m, _, _ = compute_metrics(df, annual=False)
        self.assertIsNone(m["revenue_growth"])


if __name__ == "__main__":
    unittest.main()
