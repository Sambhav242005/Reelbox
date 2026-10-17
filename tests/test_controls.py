import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

import app
import model_client


def answer_options(options,choice):
    return {'type':'choice','choice':choice,'probabilities':{k:.96 if k==choice else .04/(len(options)-1) for k in options},'confidence':.9}


class ControlTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.old=app.DATA;app.DATA=Path(self.temp.name);app.initialize()
        with app.connect() as db:db.execute('INSERT INTO boxes(name,description,embedding) VALUES(?,?,?)',('Gardening','Growing plants','[1,0]'))
        app.enqueue([{'url':'https://www.instagram.com/p/first/','title':'Growing basil','caption':'Grow basil in a pot.','creator':'gardener'},
                     {'url':'https://www.instagram.com/p/second/','title':'Another pot'}])
        (app.DATA/'thumbnails'/'first.jpg').write_bytes(b'cover')

    def tearDown(self):
        app.PROCESSING_STOP.clear();app.CURRENT_JOB.active=False
        app.DATA=self.old;self.temp.cleanup()

    def row(self,rid='first'):
        with app.connect() as db:return dict(db.execute('SELECT * FROM reels WHERE id=?',(rid,)).fetchone())

    def state(self):
        with app.connect() as db:return app.processing_status(db)

    def test_offline_waits_before_claiming_and_backoff_prevents_flood(self):
        with patch.object(model_client,'request',side_effect=model_client.ProviderUnavailable('Ollama offline','Ollama')) as request:
            self.assertFalse(app.worker_step());self.assertFalse(app.worker_step())
        self.assertEqual(request.call_count,1)
        self.assertEqual(self.row()['status'],'queued');self.assertEqual(self.row('second')['status'],'queued')
        self.assertEqual(self.state()['attempted'],0);self.assertEqual(self.state()['completed'],0)
        self.assertIn('offline',self.state()['waiting_reason'])

    def test_download_in_progress_waits_without_reserving_batch_slot(self):
        def request(path,payload=None,timeout=180):
            if path=='/api/show' and payload['model']==app.DECISION_MODEL:
                raise model_client.ProviderUnavailable('Model download incomplete',app.DECISION_MODEL,404)
            return {'version':'test'}
        with patch.object(model_client,'request',side_effect=request):self.assertFalse(app.worker_step())
        self.assertEqual(self.state()['attempted'],0);self.assertEqual(self.state()['waiting_model'],app.DECISION_MODEL)

    def test_recovered_cloud_error_is_cleared_without_losing_analysis(self):
        previous=json.dumps({'summary':'Previous result'})
        app.update('first','waiting_model',error='Ollama cloud usage credits or a paid plan are required.',analysis=previous)
        app.initialize()
        self.assertEqual(self.row()['status'],'waiting_model')
        self.assertEqual(self.row()['error'],'')
        self.assertEqual(self.row()['analysis'],previous)

    def test_mid_reel_outage_keeps_same_slot_and_previous_result(self):
        previous=json.dumps({'summary':'Previous result'})
        app.update('first','queued',analysis=previous)
        row=app.claim_next_reel()
        with patch.object(app,'process_reel',side_effect=model_client.ProviderUnavailable('Model loading','d1:latest',503)):
            self.assertEqual(app.process_pending(row),'waiting')
        self.assertEqual(self.row()['status'],'waiting_model');self.assertEqual(self.row()['analysis'],previous)
        self.assertEqual(self.state()['completed'],0);self.assertEqual(self.state()['attempted'],1)
        app.configure_processing('resume')
        resumed=app.claim_next_reel();self.assertEqual(resumed['id'],'first')
        self.assertEqual(self.state()['attempted'],1)

    def test_stop_is_persistent_and_does_not_release_review_batch(self):
        app.configure_processing('stop');app.initialize()
        self.assertTrue(self.state()['stopped']);self.assertIsNone(app.claim_next_reel())
        app.configure_processing('resume')
        self.assertFalse(self.state()['stopped']);self.assertEqual(app.claim_next_reel()['id'],'first')

    def test_fresh_analysis_bypasses_cache_without_forcing_video(self):
        calls=[]
        app.cached('test',{},[],lambda:'old')
        app.update('first','queued',refresh_analysis=1)
        def process(row):
            self.assertFalse(row['force_video'])
            calls.append(app.cached('test',{},[],lambda:'fresh'))
        with patch.object(app,'process_reel',side_effect=process):app.process_pending(self.row())
        self.assertEqual(calls,['fresh']);self.assertEqual(self.row()['refresh_analysis'],0)
        self.assertFalse(app.CURRENT_JOB.refresh_analysis)

    def test_resume_does_not_bypass_completed_batch_review(self):
        app.enqueue([{'url':f'https://www.instagram.com/p/extra_{i}/'} for i in range(9)])
        app.configure_processing('configure',10)
        for _ in range(10):
            row=app.claim_next_reel();app.update(row['id'],'ready',metadata_attempts=10)
        app.configure_processing('stop');app.configure_processing('resume')
        self.assertTrue(self.state()['paused']);self.assertIsNone(app.claim_next_reel())

    def test_stop_terminates_a_local_subprocess(self):
        import sys
        checks=0
        def checkpoint():
            nonlocal checks
            checks+=1
            if checks>=3:raise app.ProcessingStopped('stop')
        with patch.object(app,'checkpoint',side_effect=checkpoint):
            with self.assertRaises(app.ProcessingStopped):
                app.run([sys.executable,'-c','import time; time.sleep(60)'],timeout=5)

    def test_stop_during_model_request_caches_result_but_does_not_save_analysis(self):
        row=app.claim_next_reel()
        def response(*args):
            app.configure_processing('stop')
            return {'status':'ready'}
        def process(_):app.chat('synthetic',app.object_schema({'status':app.STR}))
        with patch.object(app,'process_reel',side_effect=process),patch.object(model_client,'chat',side_effect=response):
            self.assertEqual(app.process_pending(row),'stopped')
        self.assertEqual(self.row()['status'],'queued');self.assertIsNone(self.row()['analysis'])
        with app.connect() as db:self.assertEqual(db.execute('SELECT count(*) FROM inference_cache').fetchone()[0],1)

    def test_cleared_wait_retries_same_reel_when_models_return(self):
        with patch.object(model_client,'request',side_effect=model_client.ProviderUnavailable('Offline')):app.worker_step()
        app.configure_processing('resume')
        def process(row):app.update(row['id'],'ready')
        with patch.object(model_client,'request',return_value={'version':'test'}),patch.object(app,'process_reel',side_effect=process):
            self.assertTrue(app.worker_step())
        self.assertEqual(self.row()['status'],'ready');self.assertEqual(self.state()['waiting_reason'],'')
        self.assertEqual(self.state()['completed'],1)

    def test_missing_thumbnail_holds_without_any_vision_or_embedding_call(self):
        (app.DATA/'thumbnails'/'first.jpg').unlink()
        with patch.object(app,'metadata',return_value={}),patch.object(app,'retry_wait',return_value=False),patch.object(app,'decide',side_effect=AssertionError('No image')),patch.object(app,'chat',side_effect=AssertionError('No image')),patch.object(app,'embed',side_effect=AssertionError('No image')):
            app.process_reel(self.row())
        self.assertEqual(self.row()['status'],'review');self.assertEqual(self.row()['metadata_attempts'],10)
        self.assertIsNone(self.row()['analysis'])

    def test_d1_fast_path_does_not_call_visual_fallback(self):
        calls=[]
        def decide(state,questions,images,force):
            calls.append('d1')
            self.assertEqual(images,[app.DATA/'thumbnails'/'first.jpg'])
            self.assertNotIn('route',questions)
            return {'category':answer_options(questions['category']['criteria'],'Gardening')}
        with patch.object(app,'decide',side_effect=decide),patch.object(app,'embed',return_value=[1,0]),patch.object(app,'chat',side_effect=AssertionError('D1 fast path invoked fallback')):
            app.process_reel(self.row())
        value=json.loads(self.row()['analysis'])
        self.assertEqual(calls,['d1']);self.assertIsNone(value['model'])
        self.assertEqual(value['summary_kind'],'caption_preview');self.assertEqual(value['decision_model'],app.DECISION_MODEL)

    def test_new_topic_requests_minicpm_after_first_decision(self):
        calls=[]
        def decide(state,questions,images,force):
            calls.append('d1')
            return {'category':answer_options(questions['category']['criteria'],'new')}
        def chat(*args,**kwargs):
            calls.append('minicpm')
            return {'title':'Basil care','summary':'Grow basil in a pot.','key_ideas':[],'tags':['basil'],
                    'topic':'Gardening','topic_description':'Growing plants','confidence':.95,'uncertainties':[]}
        decision={'route':'accept','confidence':.95,'box_ids':[1],'new_box':None,'reason':'Existing box fits.'}
        with patch.object(app,'decide',side_effect=decide),patch.object(app,'discover_topic',return_value=None),patch.object(app,'embed',return_value=[1,0]),patch.object(app,'chat',side_effect=chat),patch.object(app,'route_analysis',return_value=decision):
            app.process_reel(self.row())
        self.assertEqual(calls,['d1','minicpm','minicpm'])
        self.assertEqual(json.loads(self.row()['analysis'])['model'],'minicpm-v4.6:latest')

    def test_pause_during_source_retry_does_not_become_a_missing_info_failure(self):
        (app.DATA/'thumbnails'/'first.jpg').unlink()
        row=app.claim_next_reel()
        def metadata(url):app.configure_processing('stop');return {}
        with patch.object(app,'metadata',side_effect=metadata):self.assertEqual(app.process_pending(row),'stopped')
        self.assertEqual(self.row()['status'],'queued');self.assertEqual(self.state()['completed'],0)


class TransportFailureTests(unittest.TestCase):
    def test_network_and_unavailable_model_errors_are_waitable(self):
        errors=[urllib.error.URLError('refused')]+[urllib.error.HTTPError('http://localhost',code,'test',{},io.BytesIO()) for code in (401,402,404,429,500,503)]
        for error in errors:
            with self.subTest(error=error),patch.object(model_client.urllib.request,'urlopen',side_effect=error):
                with self.assertRaises(model_client.ProviderUnavailable):model_client.request('/v1/systemone',{'model':'d1:latest'})


if __name__=='__main__':unittest.main()
