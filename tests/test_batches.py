import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import app


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.old=app.DATA;app.DATA=Path(self.temp.name);app.initialize()

    def tearDown(self):
        app.DATA=self.old;self.temp.cleanup()

    def seed(self,count):
        app.enqueue([{'url':f'https://www.instagram.com/p/reel_{i}/','scan_started':100,'saved_position':i} for i in range(count)])
        with app.connect() as db:db.execute('UPDATE reels SET metadata_attempts=10')

    def state(self):
        with app.connect() as db:return app.processing_status(db)

    def finish(self,count,status='ready'):
        ids=[]
        for _ in range(count):
            row=app.claim_next_reel();self.assertIsNotNone(row)
            ids.append(row['id']);app.update(row['id'],status)
        return ids

    def test_first_fifty_pause_and_continue_next_fifty_in_top_order(self):
        self.seed(101)
        self.assertEqual(self.finish(50),[f'reel_{i}' for i in range(50)])
        self.assertIsNone(app.claim_next_reel())
        self.assertTrue(self.state()['paused']);self.assertEqual(self.state()['queued'],51)
        app.configure_processing('continue')
        self.assertEqual(self.finish(50),[f'reel_{i}' for i in range(50,100)])
        self.assertIsNone(app.claim_next_reel());self.assertEqual(self.state()['queued'],1)

    def test_restart_does_not_reset_review_pause(self):
        self.seed(51);self.finish(50)
        app.initialize()
        self.assertTrue(self.state()['paused']);self.assertIsNone(app.claim_next_reel())
        self.assertEqual(self.state()['attempted'],50)

    def test_interrupted_last_reel_resumes_without_an_extra_slot(self):
        self.seed(51);self.finish(49)
        last=app.claim_next_reel();self.assertEqual(last['id'],'reel_49')
        app.initialize()
        resumed=app.claim_next_reel();self.assertEqual(resumed['id'],'reel_49')
        self.assertEqual(self.state()['attempted'],50)
        app.update(resumed['id'],'ready');self.assertIsNone(app.claim_next_reel())

    def test_failures_count_toward_limit(self):
        self.seed(51);self.finish(50,'failed')
        self.assertEqual(self.state()['completed'],50);self.assertTrue(self.state()['paused'])
        self.assertIsNone(app.claim_next_reel())

    def test_continue_rejected_while_last_reel_is_in_progress(self):
        self.seed(51);self.finish(49);app.claim_next_reel()
        with self.assertRaises(ValueError):app.configure_processing('continue')
        self.assertEqual(self.state()['batch_id'],1)

    def test_configurable_limit_and_explicit_unlimited_mode(self):
        self.seed(12);app.configure_processing('configure',10);self.finish(10)
        self.assertIsNone(app.claim_next_reel())
        app.configure_processing('configure',0);self.finish(2)
        self.assertFalse(self.state()['paused'])
        with self.assertRaises(ValueError):app.configure_processing('configure',True)

    def test_parallel_claims_cannot_overshoot_the_limit(self):
        self.seed(11);app.configure_processing('configure',10);self.finish(9)
        with ThreadPoolExecutor(max_workers=2) as pool:rows=list(pool.map(lambda _:app.claim_next_reel(),range(2)))
        self.assertEqual(sum(row is not None for row in rows),1)
        self.assertEqual(self.state()['attempted'],10)

    def test_rolling_window_refills_one_place_and_survives_restart(self):
        self.seed(25)
        self.assertEqual(self.state()['queue_window'],[f'reel_{i}' for i in range(app.QUEUE_WINDOW)])
        row=app.claim_next_reel()
        self.assertEqual(self.state()['in_flight'],1)
        self.assertEqual(len(self.state()['queue_window']),app.QUEUE_WINDOW)
        app.update(row['id'],'ready')
        self.assertEqual(self.state()['queue_window'],[f'reel_{i}' for i in range(1,1+app.QUEUE_WINDOW)])
        app.initialize()
        self.assertEqual(self.state()['queue_window'],[f'reel_{i}' for i in range(1,1+app.QUEUE_WINDOW)])

    def test_window_respects_exact_reserved_rerun_and_batch_limit(self):
        self.seed(25)
        app.configure_processing('configure',10)
        with app.connect() as db:
            db.executemany('INSERT INTO processing_batch_items VALUES(?,?)',[(1,f'reel_{i}') for i in range(10,20)])
        self.assertEqual(self.state()['queue_window'],[f'reel_{i}' for i in range(10,10+app.QUEUE_WINDOW)])
        self.assertEqual(self.finish(10),[f'reel_{i}' for i in range(10,20)])
        self.assertEqual(self.state()['queue_window'],[])
        self.assertIsNone(app.claim_next_reel())

    def test_five_concurrent_claims_refill_without_duplicates(self):
        self.seed(20)
        with ThreadPoolExecutor(max_workers=5) as pool:
            rows=list(pool.map(lambda _:app.claim_next_reel(),range(5)))
        self.assertEqual({r['id'] for r in rows},{f'reel_{i}' for i in range(5)})
        self.assertIsNone(app.claim_next_reel())
        app.update('reel_0','ready')
        self.assertEqual(app.claim_next_reel()['id'],'reel_5')
        self.assertIsNone(app.claim_next_reel())


if __name__=='__main__':unittest.main()
