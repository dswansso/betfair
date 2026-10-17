import datetime
import unittest

from racing import results

CATALOGUE = [
    {
        "marketId": "1.200",
        "marketName": "2m Hcap",
        "marketStartTime": "2026-10-17T14:05:00.000Z",
        "event": {"venue": "Ascot", "name": "Ascot 17th Oct"},
        "runners": [
            {"selectionId": 11, "runnerName": "Alpha"},
            {"selectionId": 22, "runnerName": "Bravo"},
            {"selectionId": 33, "runnerName": "Charlie"},
        ],
    },
    {
        "marketId": "1.100",
        "marketName": "1m Mdn",
        "marketStartTime": "2026-10-17T13:30:00.000Z",
        "event": {"name": "Leopardstown 17th Oct"},
        "runners": [{"selectionId": 44, "runnerName": "Delta"}],
    },
]

BOOKS = [
    {
        "marketId": "1.200",
        "status": "CLOSED",
        "runners": [
            {"selectionId": 11, "status": "WINNER", "sp": {"actualSP": 4.2}},
            {"selectionId": 22, "status": "LOSER", "sp": {"actualSP": 3.1}},
            {"selectionId": 33, "status": "REMOVED"},
        ],
    },
    {
        "marketId": "1.100",
        "status": "OPEN",
        "runners": [{"selectionId": 44, "status": "ACTIVE"}],
    },
]


class ResultsTest(unittest.TestCase):
    def test_day_window_covers_whole_utc_day(self):
        start, end = results.day_window(datetime.date(2026, 10, 17))
        self.assertEqual(start.isoformat(), "2026-10-17T00:00:00+00:00")
        self.assertEqual(end.isoformat(), "2026-10-17T23:59:59+00:00")

    def test_merge_catalogue_counts_new_markets(self):
        racecard = {}
        self.assertEqual(results.merge_catalogue(racecard, CATALOGUE), 2)
        self.assertEqual(results.merge_catalogue(racecard, CATALOGUE[:1]), 0)
        self.assertEqual(racecard["1.100"]["course"], "Leopardstown 17th Oct")
        self.assertEqual(racecard["1.200"]["runners"]["22"], "Bravo")

    def test_rows_only_for_closed_markets(self):
        racecard = {}
        results.merge_catalogue(racecard, CATALOGUE)
        rows = results.rows_from_books(racecard, BOOKS)
        self.assertEqual([r["runner"] for r in rows], ["Alpha", "Bravo", "Charlie"])
        self.assertEqual(rows[0]["result"], "WINNER")
        self.assertEqual(rows[0]["bsp"], 4.2)
        self.assertEqual(rows[0]["course"], "Ascot")
        self.assertEqual(rows[0]["date"], "2026-10-17")
        self.assertEqual(rows[2]["bsp"], "")
        self.assertEqual(rows[2]["non_runner"], "yes")
        self.assertEqual(rows[1]["non_runner"], "no")


if __name__ == "__main__":
    unittest.main()
