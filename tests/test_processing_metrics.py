import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import app
import processing_metrics as metrics


class MetricsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old = app.DATA
        app.DATA = Path(self.temp.name)
        app.initialize()
        app.enqueue([{'url':f'https://www.instagram.com/p/m_{i}/'} for i in range(6)])
        with app.connect() as db:
            db.execute('UPDATE reels SET metadata_attempts=10')
            db.execute("INSERT INTO boxes(name,description,embedding) VALUES('Code','Programming','[1,0]')")

    def tearDown(self):
        app.DATA = self.old
        app.PROCESSING_STOP.clear()
        self.temp.cleanup()

    def summary(self, now=200):
        with app.connect() as db:
            return metrics.summary(db, 1, now)

    def success(self, rid, now):
        with app.connect() as db:
            db.execute('INSERT OR IGNORE INTO reel_boxes VALUES(?,1)',(rid,))
            db.execute("UPDATE reels SET status='ready',analysis=? WHERE id=?",(json.dumps({'title':rid}),rid))
            metrics.finish(db,rid,now)

    def test_no_historical_timings_and_no_unassigned_success(self):
        self.assertFalse(self.summary()['measured'])
        with app.connect() as db: metrics.claim(db,1,'m_0',100)
        app.update('m_0','ready')
        self.assertEqual(self.summary()['organized'],0)
        self.assertEqual(self.summary()['review'],1)

    def test_wall_time_median_and_unique_success(self):
        with app.connect() as db:
            metrics.claim(db,1,'m_0',100);metrics.claim(db,1,'m_1',110)
        self.success('m_0',120);self.success('m_1',150);self.success('m_1',160)
        result=self.summary(200)
        self.assertEqual(result['organized'],2)
        self.assertEqual(result['median_seconds'],30)
        self.assertEqual(result['elapsed_seconds'],100)
        self.assertAlmostEqual(result['reels_per_minute'],1.2)

    def test_retry_stop_restart_preserve_first_claim(self):
        with patch.object(metrics.time,'time',return_value=100): row=app.claim_next_reel()
        rid=row['id'];app.update(rid,'waiting_model')
        app.configure_processing('stop');app.initialize()
        self.assertIsNone(app.claim_next_reel())
        app.configure_processing('resume')
        with patch.object(metrics.time,'time',return_value=150):app.claim_next_reel()
        self.success(rid,180)
        self.assertEqual(self.summary()['tracked'],1)
        self.assertEqual(self.summary()['median_seconds'],80)

    def test_review_failed_and_parallel_claims_are_separate(self):
        with ThreadPoolExecutor(max_workers=5) as pool: rows=list(pool.map(lambda _: app.claim_next_reel(),range(5)))
        self.assertEqual(self.summary()['tracked'],5)
        app.update(rows[0]['id'],'failed');app.update(rows[1]['id'],'review')
        result=self.summary()
        self.assertEqual((result['organized'],result['errors'],result['review']),(0,1,1))
        with app.connect() as db: board=metrics.board(db,app.DATA,1)
        self.assertEqual(board['counts']['organizing'],3)
        self.assertEqual(board['counts']['organized'],0)

    def test_completed_run_freezes_clock_and_retry_reopens_it(self):
        with app.connect() as db:
            db.execute("DELETE FROM reels WHERE id!='m_0'")
            metrics.claim(db,1,'m_0',100)
        self.success('m_0',120)
        self.assertEqual(self.summary(1000)['elapsed_seconds'],20)
        with app.connect() as db: metrics.claim(db,1,'m_0',1100)
        self.assertEqual(self.summary(1120)['organized'],0)
        self.success('m_0',1140)
        self.assertEqual(self.summary(2000)['organized'],1)
        self.assertEqual(self.summary(2000)['elapsed_seconds'],1040)

    def test_metadata_only_backfill_does_not_measure_old_organization(self):
        with app.connect() as db:
            db.execute("UPDATE reels SET info_only='ready' WHERE id='m_0'")
        app.claim_next_reel()
        self.assertFalse(self.summary()['measured'])

    def test_metadata_only_queue_does_not_keep_inference_clock_running(self):
        with app.connect() as db:
            db.execute("UPDATE reels SET info_only='ready' WHERE id!='m_0'")
            metrics.claim(db,1,'m_0',100)
        self.success('m_0',120)
        self.assertEqual(self.summary(1000)['elapsed_seconds'],20)


if __name__=='__main__': unittest.main()
