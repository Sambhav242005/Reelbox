import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app
import model_client


class FolderMatchingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.old=app.DATA;app.DATA=Path(self.temp.name);app.initialize()
        app.STOP.clear();app.PROCESSING_STOP.clear()
        app.enqueue([{'url':f'https://www.instagram.com/p/{rid}/','title':rid,'caption':caption,'creator':'test'}
                     for rid,caption in [('match','CSS interface layout'),('other','Growing basil')]])
        with app.connect() as db:
            db.execute("INSERT INTO boxes VALUES(1,'Original','Original folder','[1,0]')")
            db.execute("INSERT INTO boxes VALUES(2,'Design','Interface design','[1,0]')")
            for rid in ('match','other'):
                db.execute("UPDATE reels SET status='ready',analysis=?,embedding=?,metadata_attempts=10 WHERE id=?",
                           (json.dumps({'title':rid,'summary':'Stored result','source_evidence':{'caption':'source'}}),json.dumps([1,0] if rid=='match' else [0,1]),rid))
                db.execute('INSERT INTO reel_boxes VALUES(?,1)',(rid,))
                (app.DATA/'thumbnails'/f'{rid}.jpg').write_bytes(b'cover')
            app.queue_folder_matches(db,2)

    def tearDown(self):
        app.CURRENT_JOB.active=False;app.PROCESSING_STOP.clear()
        app.DATA=self.old;self.temp.cleanup()

    def step(self):
        with patch.object(app,'embed',return_value=[1,0]),patch.object(app,'decide',return_value={'match':{'noul':1}}) as decide:
            result=app.folder_match_step()
        return result,decide

    def test_additive_matching_keeps_original_and_skips_unrelated(self):
        with app.connect() as db:before=[tuple(r) for r in db.execute('SELECT id,status,analysis,updated FROM reels ORDER BY id')]
        _,decision=self.step();self.assertTrue(decision.called)
        self.assertEqual(decision.call_args.args[2],[app.DATA/'thumbnails'/'match.jpg'])
        self.step()
        with app.connect() as db:
            self.assertEqual([tuple(r) for r in db.execute('SELECT reel_id,box_id FROM reel_boxes ORDER BY reel_id,box_id')],[('match',1),('match',2),('other',1)])
            self.assertEqual(before,[tuple(r) for r in db.execute('SELECT id,status,analysis,updated FROM reels ORDER BY id')])
            job=db.execute('SELECT * FROM folder_matches').fetchone()
            self.assertEqual((job['scanned'],job['added'],job['state']),(2,1,'done'))

    def test_missing_cover_never_calls_vision_or_downloads(self):
        (app.DATA/'thumbnails'/'match.jpg').unlink()
        with patch.object(app,'decide',side_effect=AssertionError('No text-only vision')),patch.object(app,'download',side_effect=AssertionError('No downloads')):
            self.assertTrue(app.folder_match_step())

    def test_repeated_scan_is_idempotent(self):
        self.step();self.step()
        with app.connect() as db:app.queue_folder_matches(db,2)
        self.step();self.step()
        with app.connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM reel_boxes WHERE box_id=2').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT added FROM folder_matches').fetchone()[0],0)

    def test_outage_backoff_and_restart_keep_same_cursor(self):
        with patch.object(app,'embed',side_effect=model_client.ProviderUnavailable('offline',app.MODEL)):
            self.assertFalse(app.folder_match_step())
        app.initialize()
        with app.connect() as db:
            job=db.execute('SELECT * FROM folder_matches').fetchone()
            self.assertEqual(job['scanned'],0);self.assertEqual(job['state'],'waiting')
            db.execute('UPDATE folder_matches SET retry_at=0')
        self.step()
        with app.connect() as db:self.assertEqual(db.execute('SELECT scanned FROM folder_matches').fetchone()[0],1)

    def test_stopped_processing_does_not_match(self):
        app.configure_processing('stop')
        self.assertFalse(app.folder_match_step())
        with app.connect() as db:self.assertEqual(db.execute('SELECT scanned FROM folder_matches').fetchone()[0],0)

    def test_stale_folder_definition_cannot_add_links(self):
        def change(*args,**kwargs):
            with app.connect() as db:app.queue_folder_matches(db,2)
            return {'match':{'noul':1}}
        with patch.object(app,'embed',return_value=[1,0]),patch.object(app,'decide',side_effect=change):
            app.folder_match_step()
        with app.connect() as db:self.assertIsNone(db.execute('SELECT 1 FROM reel_boxes WHERE box_id=2').fetchone())

    def test_future_reels_append_and_reanalysis_preserves_secondary_folder(self):
        self.step();self.step()
        with app.connect() as db:
            app.append_folder_match_reel(db,'future')
            job=db.execute('SELECT * FROM folder_matches').fetchone()
            self.assertEqual(job['state'],'pending');self.assertIn('future',json.loads(job['reel_ids']))
        app.save_analysis('match',{'title':'Updated'},[1,0],'caption_cover',[1],'Updated',{'route':'accept'})
        with app.connect() as db:
            self.assertEqual({r[0] for r in db.execute("SELECT box_id FROM reel_boxes WHERE reel_id='match'")},{1,2})


if __name__=='__main__':unittest.main()
