import unittest

from dashboard_metrics import build_kpi_summary_text


class DashboardMetricsTests(unittest.TestCase):
    def test_summary_text_shows_total_and_filtered_counts(self):
        text = build_kpi_summary_text(19313, 1234)

        self.assertIn("19,313", text)
        self.assertIn("1,234", text)
        self.assertIn("ทั้งหมดในฐานข้อมูล", text)
        self.assertIn("ตามตัวกรองปัจจุบัน", text)


if __name__ == "__main__":
    unittest.main()
