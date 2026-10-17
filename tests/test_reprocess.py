import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
import app
import reprocess


class RerunTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.old=app.DATA
        app.DATA=Path(self.temp.name);app.initialize()
        app.enqueue([{'url':'https://www.instagram.com/p/first/'},{'url':'https://www.instagram.com/p/second/'}])
        app.update('first','ready',analysis=json.dumps({'summary':'Keep this'}),force_video=1,metadata_attempts=10)
        with app.connect() as db:
            db.execute("INSERT INTO boxes(id,name,description,embedding) VALUES(1,'Long programming topic','Programming','[1,0]')")
            db.execute("INSERT INTO boxes(id,name,description,embedding) VALUES(2,'Another coding topic','Programming','[1,0]')")
            db.execute("INSERT INTO reel_boxes VALUES('first',1)")
            db.execute("INSERT INTO reel_boxes VALUES('second',2)")
        app.configure_processing('stop')
        self.plan=[{'id':1,'name':'Code','description':'Programming'},{'id':2,'name':'code','description':'Programming'}]

    def tearDown(self):
        app.PROCESSING_STOP.clear();app.DATA=self.old;self.temp.cleanup()

    def test_full_rerun_preserves_results_merges_topics_and_starts_new_unlimited_batch(self):
        self.assertEqual(reprocess.apply_plan(self.plan,{'code':[1,0]}),2)
        with app.connect() as db:
            row=dict(db.execute("SELECT * FROM reels WHERE id='first'").fetchone())
            self.assertEqual(row['status'],'queued');self.assertEqual(json.loads(row['analysis'])['summary'],'Keep this')
            self.assertEqual(row['metadata_attempts'],0);self.assertEqual(row['force_video'],0)
            self.assertEqual(db.execute('SELECT count(*) FROM boxes').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT count(*) FROM reel_boxes WHERE box_id=1').fetchone()[0],2)
            state=app.processing_status(db)
            self.assertEqual(state['batch_size'],0);self.assertEqual(state['batch_id'],2)
            self.assertTrue(state['stopped']);self.assertEqual(state['attempted'],0)

    def test_incomplete_plan_cannot_change_library(self):
        with self.assertRaises(ValueError):reprocess.apply_plan(self.plan[:1],{'code':[1,0]})
        with app.connect() as db:self.assertEqual(db.execute('SELECT count(*) FROM boxes').fetchone()[0],2)

    def test_long_name_rejected_before_rename(self):
        self.plan[0]['name']='a very long sentence about coding'
        with self.assertRaises(ValueError):reprocess.apply_plan(self.plan,{'code':[1,0]})

    def test_cannot_prepare_while_worker_running(self):
        app.configure_processing('resume')
        with self.assertRaises(ValueError):reprocess.apply_plan(self.plan,{'code':[1,0]})

    def test_short_names_keep_acronyms_and_normalize_manhwa(self):
        self.assertEqual(app.short_topic_name('ui'),'UI')
        self.assertEqual(app.short_topic_name('Mahnwa'),'Manhwa')
        self.assertEqual(app.short_topic_name('cool projects'),'Cool Projects')

    def test_local_decision_names_existing_folder_from_subject(self):
        box={'id':8,'name':'open-source design systems','description':'Interface components for React'}
        with patch.object(app,'decide',return_value={'folder':{'choice':'UI'}}) as decide:
            result=reprocess.name_existing_folder(box)
        self.assertEqual(result['name'],'UI')
        self.assertEqual(decide.call_args.args[0]['folder_subject']['name'],box['name'])


if __name__=='__main__':unittest.main()
