import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch
import app

class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.retry_patch=patch.object(app,'retry_wait',return_value=False)
        self.retry_patch.start();self.addCleanup(self.retry_patch.stop)
        self.temp=tempfile.TemporaryDirectory()
        self.old_data=app.DATA
        app.DATA=Path(self.temp.name)
        app.initialize()
    def tearDown(self):
        app.DATA=self.old_data
        self.temp.cleanup()
    def test_duplicate_urls_share_one_record(self):
        self.assertEqual(app.enqueue([{'url':'https://www.instagram.com/reel/ABC_123/?igsh=hello'}]),1)
        self.assertEqual(app.enqueue([{'url':'https://www.instagram.com/p/ABC_123/'}]),0)
        with app.connect() as db:self.assertEqual(db.execute('SELECT count(*) FROM reels').fetchone()[0],1)
    def test_invalid_url_rolls_back_whole_batch(self):
        with self.assertRaises(ValueError):
            app.enqueue([{'url':'https://www.instagram.com/p/okay/'},{'url':'https://evil.test/reel/no/'}])
        with app.connect() as db:self.assertEqual(db.execute('SELECT count(*) FROM reels').fetchone()[0],0)
    def test_failed_analysis_cleans_temporary_media(self):
        app.enqueue([{'url':'https://www.instagram.com/p/test/'}])
        app.update('test','queued',force_video=1)
        with app.connect() as db:row=db.execute('SELECT * FROM reels').fetchone()
        def broken_download(url,folder):
            (folder/'video.mp4').write_bytes(b'sensitive temporary bytes')
            raise RuntimeError('test failure')
        (app.DATA/'thumbnails'/'test.jpg').write_bytes(b'cover')
        with patch.object(app,'download',broken_download), patch.object(app,'metadata',side_effect=RuntimeError('unavailable')),patch.object(app,'embed',return_value=[1,0]),patch.object(app,'decision_first',return_value={'route':'analyze_video'}):
            with self.assertRaises(RuntimeError):app.process_reel(row)
        self.assertEqual(list((app.DATA/'temp').iterdir()),[])
    def test_classification_reuses_existing_box_before_new(self):
        with app.connect() as db:
            db.execute('INSERT INTO boxes(name,description,embedding) VALUES(?,?,?)',('Gardening','Growing plants','[1,0]'))
        decision={'route':'accept','box_ids':[1],'new_box':None,'confidence':.95,'reason':'same topic'}
        with patch.object(app,'decide',side_effect=AssertionError('Already decided')):
            ids,_=app.assign_boxes({'topic':'Basil'},[1,0],decision)
        self.assertEqual(ids,[1])
        with app.connect() as db:self.assertEqual(db.execute('SELECT count(*) FROM boxes').fetchone()[0],1)
    def test_semantic_vectors_and_bad_dimensions(self):
        self.assertAlmostEqual(app.cosine([1,0],[1,0]),1)
        self.assertEqual(app.cosine([1],[1,0]),0)
        self.assertEqual(app.cosine([0,0],[1,1]),0)

class ApiTests(LibraryTests):
    def setUp(self):
        super().setUp()
        self.server=app.ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
        self.old_port=app.PORT;app.PORT=self.server.server_port
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.base=f'http://127.0.0.1:{app.PORT}'
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join()
        app.PORT=self.old_port;super().tearDown()
    def request(self,path,headers=None,body=None):
        req=urllib.request.Request(self.base+path,headers=headers or {},data=json.dumps(body).encode() if body else None)
        try:
            with urllib.request.urlopen(req) as response:return response.status,json.load(response)
        except urllib.error.HTTPError as error:return error.code,json.load(error)
    def test_api_requires_token(self):
        status,_=self.request('/api/reels');self.assertEqual(status,401)
        status,_=self.request('/api/reels',{'Authorization':'Bearer '+app.settings()['token']});self.assertEqual(status,200)
    def test_cross_site_bootstrap_is_denied(self):
        status,_=self.request('/api/bootstrap',{'Origin':'https://evil.test'});self.assertEqual(status,403)
        status,_=self.request('/api/bootstrap',{'Sec-Fetch-Site':'cross-site'});self.assertEqual(status,403)
    def test_duplicate_ingestion_through_api(self):
        auth={'Authorization':'Bearer '+app.settings()['token'],'Content-Type':'application/json'}
        status,result=self.request('/api/ingest',auth,{'items':[{'url':'https://www.instagram.com/reel/Dupe/'}]})
        self.assertEqual((status,result['added']),(200,1))
        status,result=self.request('/api/ingest',auth,{'items':[{'url':'https://www.instagram.com/p/Dupe/'}]})
        self.assertEqual((status,result['added']),(200,0))
    def test_cannot_move_unprocessed_reel(self):
        app.enqueue([{'url':'https://www.instagram.com/p/queued/'}])
        status,_=self.request('/api/reel-boxes',{'Authorization':'Bearer '+app.settings()['token']},{'id':'queued','box_ids':[]})
        self.assertEqual(status,400)
    def test_extension_rejects_other_domain_session(self):
        auth={'Authorization':'Bearer '+app.settings()['token']}
        status,_=self.request('/api/extension-session',auth,{'cookies':[{'name':'sessionid','value':'test','domain':'.example.com'}]})
        self.assertEqual(status,400)
        self.assertFalse((app.DATA/'instagram-cookies.txt').exists())
    def test_extension_session_and_sync_request(self):
        auth={'Authorization':'Bearer '+app.settings()['token']}
        status,_=self.request('/api/extension-session',auth,{'cookies':[{'name':'sessionid','value':'synthetic-session','domain':'.instagram.com','httpOnly':True,'secure':True}]})
        self.assertEqual(status,200)
        self.assertIn('#HttpOnly_.instagram.com',(app.DATA/'instagram-cookies.txt').read_text())
        status,_=self.request('/api/sync',auth,{'mode':'force'});self.assertEqual(status,200)
        status,data=self.request('/api/extension-state',auth);self.assertEqual(status,200);self.assertNotEqual(data['request'],'0')
    def test_extension_cookie_newline_rejected(self):
        status,_=self.request('/api/extension-session',{'Authorization':'Bearer '+app.settings()['token']},{'cookies':[{'name':'sessionid','value':'bad\nvalue','domain':'.instagram.com'}]})
        self.assertEqual(status,400)

    def test_explicit_video_request_preserves_analysis_and_blocks_duplicates(self):
        app.enqueue([{'url':'https://www.instagram.com/p/deeper/'}])
        previous=json.dumps({'title':'Earlier result','summary':'Keep this summary'})
        app.update('deeper','ready',analysis=previous,analysis_mode='caption_cover')
        auth={'Authorization':'Bearer '+app.settings()['token']}
        status,result=self.request('/api/analyze-video',auth,{'id':'deeper'})
        self.assertEqual((status,result['queued']),(200,True))
        status,result=self.request('/api/analyze-video',auth,{'id':'deeper'})
        self.assertFalse(result['queued'])
        with app.connect() as db:row=db.execute("SELECT * FROM reels WHERE id='deeper'").fetchone()
        self.assertEqual(row['analysis'],previous);self.assertEqual(row['force_video'],1)

    def test_video_approval_is_per_reel_and_clears_pending_notice(self):
        app.enqueue([{'url':'https://www.instagram.com/p/permission/'},{'url':'https://www.instagram.com/p/other/'}])
        with app.connect() as db:row=dict(db.execute("SELECT * FROM reels WHERE id='permission'").fetchone())
        app.request_video_approval(row,{'reason':'Speech is needed.'})
        auth={'Authorization':'Bearer '+app.settings()['token']}
        status,result=self.request('/api/analyze-video',auth,{'id':'permission'})
        self.assertEqual((status,result['queued']),(200,True))
        with app.connect() as db:
            approved=db.execute("SELECT * FROM reels WHERE id='permission'").fetchone()
            self.assertEqual(approved['force_video'],1)
            self.assertFalse(json.loads(approved['analysis'])['video_approval_required'])
            self.assertEqual(db.execute("SELECT force_video FROM reels WHERE id='other'").fetchone()[0],0)
            self.assertEqual(db.execute("SELECT dismissed FROM notifications WHERE kind='video_approval'").fetchone()[0],1)

    def test_analysis_mode_filter_excludes_unresolved_quick_results(self):
        app.enqueue([{'url':'https://www.instagram.com/p/quick/'},{'url':'https://www.instagram.com/p/unclear/'}])
        for rid,status in [('quick','ready'),('unclear','review')]:
            app.update(rid,status,analysis=json.dumps({'summary':'A topic'}),analysis_mode='caption_cover')
        status,result=self.request('/api/reels?mode=caption_cover',{'Authorization':'Bearer '+app.settings()['token']})
        self.assertEqual(status,200);self.assertEqual([r['id'] for r in result],['quick'])

    def test_missing_info_notifications_dismiss_and_explicit_retry(self):
        app.enqueue([{'url':'https://www.instagram.com/p/missing/'}])
        app.update('missing','ready',metadata_attempts=10,missing_info='["thumbnail"]',analysis=json.dumps({'summary':'Preserved'}))
        app.record_missing_info({'id':'missing'},['thumbnail'],10)
        auth={'Authorization':'Bearer '+app.settings()['token']}
        status,notices=self.request('/api/notifications',auth)
        self.assertEqual(status,200);self.assertEqual(len(notices),1)
        self.request('/api/notifications/dismiss',auth,{'id':notices[0]['id']})
        self.assertEqual(self.request('/api/notifications',auth)[1],[])
        status,result=self.request('/api/retry-info',auth,{'id':'missing'})
        self.assertTrue(result['queued'])
        with app.connect() as db:row=dict(db.execute("SELECT * FROM reels WHERE id='missing'").fetchone())
        self.assertEqual(row['metadata_attempts'],0);self.assertEqual(row['info_only'],'ready')
        self.assertEqual(json.loads(row['analysis'])['summary'],'Preserved')

    def test_api_reels_starts_at_the_top_of_saved(self):
        app.enqueue([{'url':'https://www.instagram.com/p/top/','scan_started':100,'saved_position':0},
                     {'url':'https://www.instagram.com/p/bottom/','scan_started':100,'saved_position':1}])
        status,rows=self.request('/api/reels',{'Authorization':'Bearer '+app.settings()['token']})
        self.assertEqual([r['id'] for r in rows],['top','bottom'])

    def test_processing_limit_defaults_to_fifty_and_requires_finished_batch(self):
        auth={'Authorization':'Bearer '+app.settings()['token']}
        status,state=self.request('/api/processing',auth)
        self.assertEqual((status,state['batch_size']),(200,50))
        status,_=self.request('/api/processing',auth,{'action':'continue'})
        self.assertEqual(status,400)

    def test_stop_resume_controls_keep_server_and_queue_available(self):
        auth={'Authorization':'Bearer '+app.settings()['token']}
        app.enqueue([{'url':'https://www.instagram.com/p/stop_test/'}])
        status,state=self.request('/api/processing',auth,{'action':'stop'})
        self.assertEqual(status,200);self.assertTrue(state['stopped'])
        self.assertIsNone(app.claim_next_reel())
        self.assertEqual(self.request('/api/reels',auth)[0],200)
        status,state=self.request('/api/processing',auth,{'action':'resume'})
        self.assertFalse(state['stopped']);self.assertEqual(app.claim_next_reel()['id'],'stop_test')
        status,state=self.request('/api/processing',auth,{'action':'configure','batch_size':25})
        self.assertEqual((status,state['batch_size']),(200,25))
        status,_=self.request('/api/processing',auth,{'action':'configure','batch_size':-1})
        self.assertEqual(status,400)

    def test_create_folder_queues_matching_without_model_dependency(self):
        auth={'Authorization':'Bearer '+app.settings()['token']}
        with patch.object(app,'embed',side_effect=AssertionError('Creation must not wait for models')):
            status,result=self.request('/api/boxes',auth,{'name':'Design','description':'Interface layout and typography'})
        self.assertEqual(status,200);self.assertEqual(result['matching'],'queued')
        status,boxes=self.request('/api/boxes',auth)
        self.assertEqual(boxes[0]['matching']['state'],'pending')
        self.assertEqual(boxes[0]['matching']['total'],0)
        status,_=self.request('/api/boxes',auth,{'name':'Design','description':'duplicate'})
        self.assertEqual(status,400)
        with app.connect() as db:self.assertEqual(db.execute('SELECT count(*) FROM folder_matches').fetchone()[0],1)

    def test_manual_multiple_folders_survive_reanalysis(self):
        auth={'Authorization':'Bearer '+app.settings()['token']}
        app.enqueue([{'url':'https://www.instagram.com/p/multi/'}])
        with app.connect() as db:
            db.executemany('INSERT INTO boxes(name,description,embedding) VALUES(?,?,?)',[('A','First','[1,0]'),('B','Second','[1,0]')])
            db.execute("UPDATE reels SET status='ready',analysis=? WHERE id='multi'",(json.dumps({'title':'Multi'}),))
        status,_=self.request('/api/reel-boxes',auth,{'id':'multi','box_ids':[1,2]})
        self.assertEqual(status,200)
        app.save_analysis('multi',{'title':'Updated'},[1,0],'caption_cover',[1],'Updated',{'route':'accept'})
        _,reel=self.request('/api/reels/multi',auth)
        self.assertEqual({b['id'] for b in reel['boxes']},{1,2})

if __name__=='__main__':unittest.main()
