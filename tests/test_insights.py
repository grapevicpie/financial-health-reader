import unittest
from datetime import date, timedelta

import pandas as pd

from finance import from_wide, parse_paste, compute_metrics
from insights import yearly_matrix, integrity_checks, interpret, notes_in_context, schedule_preview, schedule_example


def mock_data():
    p=[]
    for stmt, values in {
        "손익계산서": {
            "매출액": [900, 950], "영업이익": [100, 60], "당기순이익": [80, 65]
        },
        "재무상태표": {
            "자산총계": [500, 560], "부채총계": [200, 260], "자본총계": [300,300],
            "유동자산": [180,170], "유동부채": [90,110],
            "현금및현금성자산": [55,20], "매출채권": [80,110]
        },
        "현금흐름표": {
            "영업활동현금흐름": [75,-20], "투자활동현금흐름": [-25,-30],
            "재무활동현금흐름": [10,15], "유형자산의취득": [20,25]
        }
    }.items():
        df=pd.DataFrame({"항목":list(values),
                         "2024":[v[0] for v in values.values()],
                         "2025":[v[1] for v in values.values()]})
        p.append(from_wide(df,stmt,1000000,"test"))
    return pd.concat(p,ignore_index=True)


class InsightTests(unittest.TestCase):
    def test_comparison_and_working_capital(self):
        df=mock_data()
        hist=yearly_matrix(df)
        self.assertEqual(len(hist),2)
        self.assertEqual(hist.iloc[-1]["working_capital"], 60_000_000)
        self.assertEqual(hist.iloc[-1]["ocf_minus_income"],-85_000_000)

    def test_cash_vs_earnings_and_ar_signal(self):
        df=mock_data()
        m,_,q=compute_metrics(df)
        summary=interpret(m,yearly_matrix(df), True)
        titles=" ".join(s["title"] for s in summary)
        self.assertIn("이익과 영업현금흐름",titles)
        self.assertIn("매출채권",titles)
        self.assertEqual(summary[0]["kind"],"watch")

    def test_balance_sheet_validation(self):
        df=mock_data()
        self.assertTrue(any(x["level"]=="ok" for x in integrity_checks(df)))
        broken=df.copy()
        match=(broken.statement=="재무상태표") & (broken.account=="자본총계") & (broken.period=="2025")
        broken.loc[match,"amount"]=100_000_000
        checks=integrity_checks(broken)
        self.assertTrue(any(x["level"]=="error" and "합계" in x["title"] for x in checks))

    def test_conflicting_duplicate_amounts(self):
        df=mock_data()
        entry=df.iloc[[0]].copy()
        entry["amount"]=entry["amount"]+1234
        checks=integrity_checks(pd.concat([df,entry],ignore_index=True))
        self.assertTrue(any(x["level"]=="error" and "서로 다른" in x["title"] for x in checks))

    def test_no_auto_note_inference(self):
        self.assertEqual(notes_in_context(""), [])
        hits=notes_in_context("특수관계자 회사에 단기대여금을 제공했습니다.")
        self.assertTrue(any(x["분류"]=="특수관계자" for x in hits))
        self.assertTrue(all("판단하지 않습니다" in x["추가 확인"] for x in hits))

    def test_negative_cash_schedule(self):
        base=date(2026,11,23)
        events=pd.DataFrame({"일자":[base+timedelta(days=1),base+timedelta(days=2)],
                            "구분":["출금","입금"],"내용":["대금","매출"],
                            "금액(원)":[130,100]})
        out,low=schedule_preview(events,100)
        self.assertEqual(low,-30)
        self.assertEqual(out.iloc[-1]["예상 잔액(원)"],70)

    def test_reject_bad_cash_schedule(self):
        df=pd.DataFrame({"일자":["2026-12-01"],"구분":["출금"],"금액(원)":[-40]})
        with self.assertRaises(ValueError):
            schedule_preview(df,100)
        with self.assertRaises(ValueError):
            schedule_preview(df,-1)

    def test_empty_schedule(self):
        result,balance=schedule_preview(pd.DataFrame(columns=["일자","구분","금액(원)"]),1000)
        self.assertTrue(result.empty)
        self.assertEqual(balance,1000)

    def test_partial_interim_does_not_annualize(self):
        df=mock_data()
        m,_,_=compute_metrics(df,annual=False)
        self.assertIsNone(m["revenue_growth"])
        self.assertTrue(any(x["level"]=="info" for x in integrity_checks(df, annual=False)))

if __name__=="__main__":
    unittest.main()
