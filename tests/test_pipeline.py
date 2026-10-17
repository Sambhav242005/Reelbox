import copy
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app
import model_client


def analysis(confidence=1):
    return {'title':'Growing basil','summary':'Grow basil in a pot with sunlight and water.',
            'key_ideas':['Give the plant sunlight.'],'tags':['basil'],'topic':'Gardening',
            'topic_description':'Growing and caring for plants','confidence':confidence,'uncertainties':[]}


def decision(route='accept', ids=None, new=None):
    return {'route':route,'reason':'Evidence supports the topic.','confidence':.95,
            'box_ids':ids if ids is not None else [1],'new_box':new,'missing_evidence':[]}


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.retry_patch=patch.object(app,'retry_wait',return_value=False)
        self.retry_patch.start();self.addCleanup(self.retry_patch.stop)
        self.temp=tempfile.TemporaryDirectory()
        self.old=app.DATA;app.DATA=Path(self.temp.name);app.initialize()
        with app.connect() as db:
            db.execute('INSERT INTO boxes(name,description,embedding) VALUES(?,?,?)',('Gardening','Growing plants','[1,0]'))
        app.enqueue([{'url':'https://www.instagram.com/p/basil/','caption':'Grow basil in a pot','title':'Basil','creator':'gardener'}])
        (app.DATA/'thumbnails'/'basil.jpg').write_bytes(b'cached cover')

    def tearDown(self):
        app.DATA=self.old;self.temp.cleanup()

    def row(self):
        with app.connect() as db:
            return dict(db.execute('SELECT * FROM reels WHERE id="basil"').fetchone())

    def quick(self):
        with patch.object(app,'metadata',return_value={}), patch.object(app,'chat',return_value=analysis()), patch.object(app,'embed',return_value=[1,0]), patch.object(app,'decision_first',return_value=decision()), patch.object(app,'download',side_effect=AssertionError('Quick route downloaded video')), patch.object(app,'transcribe',side_effect=AssertionError('Quick route transcribed speech')):
            app.process_reel(self.row())

    def test_quick_acceptance_never_downloads_or_transcribes(self):
        self.quick();row=self.row();value=json.loads(row['analysis'])
        self.assertEqual((row['status'],row['analysis_mode']),('ready','caption_cover'))
        self.assertEqual(value['evidence_basis'],'caption_and_cover')
        self.assertEqual(value['sampled_frames'],0)
        self.assertEqual(row['source_title'],'Basil')
        self.assertEqual(value['source_title'],'Basil')
        self.assertEqual(list((app.DATA/'temp').iterdir()),[])

    def test_both_models_receive_cover_images(self):
        cover=app.DATA/'thumbnails'/'basil.jpg';cover.write_bytes(b'test cover')
        with patch.object(app,'metadata',return_value={}),patch.object(app,'chat',return_value=analysis()) as chat,patch.object(app,'embed',return_value=[1,0]),patch.object(app,'route_analysis',return_value=decision()) as route,patch.object(app,'decision_first',return_value=decision('vision_help',[])):
            app.process_reel(self.row())
        self.assertEqual(chat.call_args.args[2],[cover])
        self.assertEqual(route.call_args.args[3],[cover])
        self.assertEqual(json.loads(self.row()['analysis'])['evidence_basis'],'caption_and_cover')

    def test_failed_deeper_analysis_preserves_previous_result_and_boxes(self):
        self.quick();before=self.row()
        app.update('basil','queued',force_video=1)
        def fail(url,folder):
            (folder/'secret.mp4').write_bytes(b'private');raise RuntimeError('Ollama unavailable')
        with patch.object(app,'download',side_effect=fail):app.process_pending(self.row())
        after=self.row()
        self.assertEqual(after['analysis'],before['analysis'])
        self.assertEqual(after['analysis_mode'],'caption_cover')
        self.assertEqual(after['force_video'],1)
        self.assertEqual(after['status'],'failed')
        with app.connect() as db:self.assertEqual(db.execute('SELECT count(*) FROM reel_boxes').fetchone()[0],1)
        self.assertEqual(list((app.DATA/'temp').iterdir()),[])

    def test_low_summary_confidence_does_not_download_video(self):
        answers={'route':{'choice':'accept','probabilities':{'accept':.99}},
                 'category':{'choice':'1','probabilities':{'1':.99}},'box_1':{'noul':.99}}
        with patch.object(app,'chat',return_value=analysis(.3)),patch.object(app,'embed',return_value=[1,0]),patch.object(app,'decision_first',return_value=decision('vision_help',[])),patch.object(app,'decide',return_value=answers),patch.object(app,'download',side_effect=AssertionError('Category uncertainty must not download video')):
            app.process_reel(self.row())
        self.assertEqual(self.row()['status'],'ready')
        self.assertEqual(self.row()['analysis_mode'],'caption_cover')

    def test_approved_video_records_sampled_provenance(self):
        app.update('basil','queued',force_video=1)
        def fake_run(args,timeout=120):
            if args[0]=='ffprobe':return json.dumps({'format':{'duration':10},'streams':[]}).encode()
            Path(args[-1]).write_bytes(b'frame');return b''
        def fake_chat(prompt,schema,images=None,force=False):
            if 'Timestamps:' in prompt:
                return {'frames':[{'observations':'A basil pot','visible_text':'Basil','uncertainties':''} for _ in images]}
            return analysis()
        with patch.object(app,'metadata',return_value={}),patch.object(app,'chat',side_effect=fake_chat),patch.object(app,'embed',return_value=[1,0]),patch.object(app,'decision_first',return_value=decision('vision_help',[])),patch.object(app,'route_analysis',return_value=decision()) as route,patch.object(app,'download',return_value=(Path('synthetic.mp4'),{})) as download,patch.object(app,'transcribe',return_value=([],'unknown')),patch.object(app,'run',side_effect=fake_run):
            app.process_reel(self.row())
        self.assertEqual(download.call_count,1);self.assertEqual(route.call_count,1)
        self.assertEqual(self.row()['analysis_mode'],'video_sampled')
        self.assertEqual(json.loads(self.row()['analysis'])['sampled_frames'],4)
        self.assertEqual(list((app.DATA/'temp').iterdir()),[])

    def test_automatic_video_request_waits_for_permission_preserving_previous_result(self):
        self.quick();before=self.row()
        app.update('basil','queued')
        with patch.object(app,'embed',return_value=[1,0]),patch.object(app,'decision_first',return_value=decision('analyze_video',[])),patch.object(app,'download',side_effect=AssertionError('Unapproved video download')):
            app.process_reel(self.row())
        after=self.row();value=json.loads(after['analysis'])
        self.assertEqual(after['status'],'review');self.assertTrue(value['video_approval_required'])
        self.assertEqual(value['summary'],json.loads(before['analysis'])['summary'])
        with app.connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM reel_boxes').fetchone()[0],1)
            self.assertEqual(db.execute("SELECT count(*) FROM notifications WHERE kind='video_approval' AND dismissed=0").fetchone()[0],1)

    def test_fallback_video_request_also_waits_for_permission(self):
        with patch.object(app,'embed',return_value=[1,0]),patch.object(app,'decision_first',return_value=decision('vision_help',[])),patch.object(app,'chat',return_value=analysis()),patch.object(app,'route_analysis',return_value=decision('analyze_video',[])),patch.object(app,'download',side_effect=AssertionError('Unapproved fallback video')):
            app.process_reel(self.row())
        self.assertTrue(json.loads(self.row()['analysis'])['video_approval_required'])

    def test_primary_folder_has_no_independent_secondary_assignments(self):
        answer={'category':{'choice':'1','probabilities':{'1':.64,'new':.23,'unclear':.13}}}
        with patch.object(app,'decide',return_value=answer) as decide:
            result=app.decision_first({'caption':'Grow basil'},[1,0],'caption_cover',[Path('cover')])
        self.assertEqual(result['box_ids'],[1]);self.assertEqual(result['route'],'accept')
        self.assertEqual(set(decide.call_args.args[1]),{'category'})

    def test_close_competing_topics_are_not_accepted(self):
        answers=[{'category':{'choice':'1','probabilities':{'1':.55,'new':.44,'unclear':.01}}},
                 {'route':{'choice':'needs_review','probabilities':{'needs_review':.9,'vision_help':.1,'analyze_video':0}}}]
        with patch.object(app,'decide',side_effect=answers),patch.object(app,'discover_topic',return_value=None):
            result=app.decision_first({'caption':'Unclear'},[1,0],'caption_cover',[Path('cover')])
        self.assertEqual(result['route'],'needs_review');self.assertEqual(result['box_ids'],[])

    def test_source_evidence_overrides_generated_summary_for_category(self):
        value=analysis(0);value['source_evidence']={'caption':'Grow basil in a pot'}
        with patch.object(app,'decide',return_value={'category':{'choice':'1','probabilities':{'1':.87,'new':.1,'unclear':.03}}}) as decide:
            result=app.route_analysis(value,[1,0],'caption_cover')
        self.assertEqual(result['route'],'accept')
        self.assertEqual(decide.call_args.args[0]['source_evidence'],value['source_evidence'])

    def test_cover_observations_are_forwarded_with_original_source(self):
        value=analysis();value['source_evidence']={'caption':'A pot'}
        value['cover_observations']={'visible_text':['BASIL'],'objects':['plant'],'subject':'Gardening','caption_relation':'consistent'}
        with patch.object(app,'decide',return_value={'category':{'choice':'Gardening','probabilities':{'Gardening':.9,'new':.05,'unclear':.05}}}) as decide:
            result=app.route_analysis(value,[1,0],'caption_cover')
        evidence=decide.call_args.args[0]['source_evidence']
        self.assertEqual(evidence['original_source'],value['source_evidence'])
        self.assertEqual(evidence['visual_observations_to_verify'],value['cover_observations'])
        self.assertEqual(result['box_ids'],[1])

    def test_supported_new_subject_not_blocked_by_generic_new_score_or_self_confidence(self):
        value=analysis(0);value.update(topic='Languages',topic_description='Language learning',source_evidence={'caption':'Learn Spanish'})
        with patch.object(app,'decide',side_effect=[{'category':{'choice':'new','probabilities':{'new':.48,'unclear':.3,'1':.22}}},{'supported':{'noul':.92}},{'novelty':{'choice':'novel','probabilities':{'novel':.85,'unclear':.1,'1':.05}}}]),patch.object(app,'discover_topic',return_value=None),patch.object(app,'embed',return_value=[0,1]):
            proposed=app.route_analysis(value,[0,1],'caption_cover')
            ids,_=app.assign_boxes(value,[0,1],proposed)
        self.assertEqual(len(ids),1)
        with app.connect() as db:self.assertEqual(db.execute('SELECT name FROM boxes WHERE id=?',(ids[0],)).fetchone()[0],'Languages')

    def test_named_subject_discovery_can_focus_two_competing_labels(self):
        answers=[{'broad_topic':{'choice':'Gardening','probabilities':{'Gardening':.4,'Fitness':.35,'Other':.25}}},
                 {'primary':{'choice':'Gardening','probabilities':{'Gardening':.8,'Fitness':.1,'Neither':.1}}}]
        with patch.object(app,'decide',side_effect=answers) as decide:
            result=app.discover_topic({'caption':'A plant'},[1,0],[])
        self.assertEqual(result['box_ids'],[1])
        self.assertEqual(set(decide.call_args.args[1]['primary']['criteria']),{'Gardening','Fitness','Neither'})

    def test_low_new_choice_can_propose_but_does_not_create_or_loop_after_video(self):
        def answers(state,questions,images,force):
            return {'route':{'choice':'accept','probabilities':{'accept':.99}},'category':{'choice':'new','probabilities':{'new':.99}},'box_1':{'noul':.1}}
        with patch.object(app,'decide',side_effect=answers),patch.object(app,'discover_topic',return_value=None):
            quick=app.route_analysis(analysis(.3),[1,0],'caption_cover')
            deep=app.route_analysis(analysis(.3),[1,0],'video_sampled')
        self.assertEqual(quick['route'],'accept');self.assertEqual(deep['route'],'accept')
        self.assertIsNotNone(deep['new_box'])
        with app.connect() as db:self.assertEqual(db.execute('SELECT count(*) FROM boxes').fetchone()[0],1)

    def test_semantic_duplicate_proposal_reuses_box(self):
        d=decision(ids=[],new={'name':'Plant care','description':'Caring for plants'})
        with patch.object(app,'embed',return_value=[1,0]),patch.object(app,'decide',side_effect=[{'supported':{'noul':.96}},{'novelty':{'choice':'1','probabilities':{'1':.96}}}]):
            ids,_=app.assign_boxes(analysis(),[1,0],d)
        self.assertEqual(ids,[1])
        with app.connect() as db:self.assertEqual(db.execute('SELECT count(*) FROM boxes').fetchone()[0],1)

    def test_novel_box_requires_second_decision(self):
        d=decision(ids=[],new={'name':'Mechanical keyboards','description':'Building keyboards'})
        with patch.object(app,'embed',return_value=[0,1]),patch.object(app,'decide',side_effect=[{'supported':{'noul':.96}},{'novelty':{'choice':'novel','probabilities':{'novel':.96}}}]) as decide:
            ids,_=app.assign_boxes(analysis(),[0,1],d)
        self.assertEqual(len(ids),1);self.assertNotEqual(ids,[1]);self.assertEqual(decide.call_count,2)

    def test_unknown_box_ids_are_rejected(self):
        with self.assertRaises(ValueError):app.assign_boxes(analysis(),[1,0],decision(ids=[999]))

    def test_low_evidence_cannot_create_a_box_even_with_strong_decision(self):
        d=decision(ids=[],new={'name':'Narrow category','description':'Unclear evidence'})
        with patch.object(app,'embed',side_effect=AssertionError('Do not embed a weak proposal')),patch.object(app,'decide',return_value={'supported':{'noul':.1}}):
            ids,_=app.assign_boxes(analysis(.2),[1,0],d)
        self.assertEqual(ids,[])

    def test_cache_invalidates_with_evidence_model_version_and_force(self):
        with patch.object(model_client,'chat',return_value=analysis()) as chat:
            app.chat('caption',app.ANALYSIS_SCHEMA);app.chat('caption',app.ANALYSIS_SCHEMA)
            self.assertEqual(chat.call_count,1)
            app.chat('new caption',app.ANALYSIS_SCHEMA)
            with patch.object(model_client,'PROMPT_VERSION','next'):app.chat('caption',app.ANALYSIS_SCHEMA)
            with patch.object(app,'MODEL','different'):app.chat('caption',app.ANALYSIS_SCHEMA)
            app.chat('caption',app.ANALYSIS_SCHEMA,force=True)
            self.assertEqual(chat.call_count,5)

    def test_existing_records_migrate_without_reanalysis(self):
        self.quick()
        with app.connect() as db:db.execute("UPDATE reels SET analysis_mode='' WHERE id='basil'")
        previous=self.row()['analysis'];app.initialize();app.initialize()
        self.assertEqual(self.row()['analysis'],previous)
        self.assertEqual(self.row()['analysis_mode'],'video_sampled')

    def test_old_database_schema_migrates(self):
        with tempfile.TemporaryDirectory() as tmp:
            previous=app.DATA;app.DATA=Path(tmp)
            db=sqlite3.connect(app.DATA/'library.sqlite')
            db.execute("CREATE TABLE reels(id TEXT PRIMARY KEY,url TEXT UNIQUE NOT NULL,title TEXT DEFAULT '',creator TEXT DEFAULT '',caption TEXT DEFAULT '',status TEXT DEFAULT 'ready',error TEXT DEFAULT '',analysis TEXT,embedding TEXT,created REAL,updated REAL)")
            db.execute('INSERT INTO reels(id,url,analysis) VALUES(?,?,?)',('legacy','https://www.instagram.com/p/legacy/',json.dumps(analysis())))
            db.commit();db.close()
            try:
                app.initialize()
                with app.connect() as db:row=dict(db.execute('SELECT * FROM reels').fetchone())
                self.assertEqual(row['analysis_mode'],'video_sampled');self.assertEqual(row['id'],'legacy')
            finally:app.DATA=previous

    def test_enrichment_does_not_duplicate_or_requeue(self):
        self.quick()
        self.assertEqual(app.enqueue([{'url':'https://www.instagram.com/reel/basil/','creator':'gardener'}]),0)
        self.assertEqual(self.row()['status'],'ready');self.assertEqual(self.row()['creator'],'gardener')

    def test_missing_info_stops_at_ten_and_notifies_once_across_restarts(self):
        (app.DATA/'thumbnails'/'basil.jpg').unlink()
        app.update('basil','queued',creator='')
        with tempfile.TemporaryDirectory() as folder, patch.object(app,'metadata',return_value={}) as metadata:
            row,missing=app.acquire_source_info(self.row(),Path(folder))
            self.assertEqual(metadata.call_count,10)
            self.assertIn('thumbnail',missing);self.assertIn('creator',missing)
            self.assertEqual(self.row()['metadata_attempts'],10)
            app.initialize()
            app.acquire_source_info(self.row(),Path(folder))
            self.assertEqual(metadata.call_count,10)
        with app.connect() as db:
            notices=db.execute('SELECT * FROM notifications').fetchall()
        self.assertEqual(len(notices),1);self.assertIn('10/10',notices[0]['message'])

    def test_missing_thumbnail_gets_at_most_ten_requests(self):
        (app.DATA/'thumbnails'/'basil.jpg').unlink()
        details={'title':'Basil','caption':'Plants','creator':'Gardener','cover_url':'https://s.cdninstagram.com/cover.jpg'}
        with tempfile.TemporaryDirectory() as folder, patch.object(app,'metadata',return_value=details),patch.object(app,'acquire_cover',side_effect=RuntimeError('expired')) as cover:
            row,missing=app.acquire_source_info(self.row(),Path(folder))
        self.assertEqual(cover.call_count,10);self.assertEqual(missing,['thumbnail'])

    def test_missing_thumbnail_recovers_before_the_limit(self):
        (app.DATA/'thumbnails'/'basil.jpg').unlink()
        details={'title':'Basil','caption':'Plants','creator':'Gardener','cover_url':'https://s.cdninstagram.com/cover.jpg'}
        def fetch(url,rid,folder):
            if fetch.calls<2:
                fetch.calls+=1;raise RuntimeError('temporary error')
            target=app.DATA/'thumbnails'/f'{rid}.jpg';target.write_bytes(b'cover');return target
        fetch.calls=0
        with tempfile.TemporaryDirectory() as folder,patch.object(app,'metadata',return_value=details),patch.object(app,'acquire_cover',side_effect=fetch) as cover:
            row,missing=app.acquire_source_info(self.row(),Path(folder))
        self.assertEqual(cover.call_count,3);self.assertEqual(missing,[])
        self.assertEqual(self.row()['metadata_attempts'],3)
        with app.connect() as db:self.assertEqual(db.execute('SELECT count(*) FROM notifications').fetchone()[0],0)

    def test_old_missing_thumbnail_backfills_without_cloud_reanalysis(self):
        (app.DATA/'thumbnails'/'basil.jpg').unlink()
        previous=json.dumps(analysis());app.update('basil','ready',analysis=previous)
        app.initialize();row=self.row();self.assertEqual(row['info_only'],'ready');self.assertEqual(row['status'],'queued')
        with patch.object(app,'metadata',return_value={}),patch.object(app,'chat',side_effect=AssertionError('Metadata-only job invoked cloud model')):
            app.process_reel(row)
        self.assertEqual(self.row()['analysis'],previous);self.assertEqual(self.row()['status'],'ready')
        self.assertEqual(self.row()['metadata_attempts'],10)

    def test_scan_positions_preserve_top_first_and_first_collection_occurrence(self):
        app.enqueue([{'url':'https://www.instagram.com/p/top/','scan_started':100,'saved_position':0},
                     {'url':'https://www.instagram.com/p/bottom/','scan_started':100,'saved_position':1}])
        app.enqueue([{'url':'https://www.instagram.com/p/top/','scan_started':100,'saved_position':20}])
        with app.connect() as db:rows=list(db.execute('SELECT id FROM reels ORDER BY '+app.SAVED_ORDER))
        self.assertEqual([r['id'] for r in rows][:2],['top','bottom'])
        app.enqueue([{'url':'https://www.instagram.com/p/newest/','scan_started':200,'saved_position':0},
                     {'url':'https://www.instagram.com/p/top/','scan_started':200,'saved_position':1}])
        with app.connect() as db:rows=list(db.execute("SELECT id FROM reels WHERE status='queued' ORDER BY "+app.SAVED_ORDER))
        self.assertEqual([r['id'] for r in rows][:2],['newest','top'])


class ModelContractTests(unittest.TestCase):
    def test_schema_failure_is_not_mislabeled_as_invalid_json(self):
        value=analysis();value['confidence']=100
        with patch.object(model_client,'request',return_value={'message':{'content':json.dumps(value)}}):
            with self.assertRaisesRegex(RuntimeError,'JSON that violates the schema'):model_client.chat('Evidence',app.ANALYSIS_SCHEMA)

    def test_local_vision_chat_uses_images_schema_and_repairs_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            image=Path(tmp)/'cover.jpg';image.write_bytes(b'image')
            with patch.object(model_client,'request',side_effect=[{'message':{'content':'not json'}},{'message':{'content':json.dumps(analysis())}}]) as request:
                model_client.chat('Synthetic caption',app.ANALYSIS_SCHEMA,[image])
            self.assertEqual(request.call_count,2)
            payload=request.call_args.args[1]
            self.assertEqual(payload['format'],app.ANALYSIS_SCHEMA)
            self.assertEqual(payload['model'],'minicpm-v4.6:latest')
            self.assertFalse(payload['think'])
            self.assertEqual(payload['messages'][1]['images'],['aW1hZ2U='])

    def test_bad_chat_types_fail_after_one_repair(self):
        bad=analysis();bad['confidence']='high'
        with patch.object(model_client,'request',return_value={'message':{'content':json.dumps(bad)}}) as request:
            with self.assertRaises(RuntimeError):model_client.chat('Evidence',app.ANALYSIS_SCHEMA)
        self.assertEqual(request.call_count,2)

    def test_native_decision_endpoint_and_unknown_choice_rejection(self):
        q={'route':{'type':'choice','instructions':'Choose','criteria':{'accept':'Clear','needs_review':'Unclear'}}}
        bad={'answers':{'route':{'type':'choice','choice':'invented','probabilities':{'accept':1,'needs_review':0},'confidence':1}}}
        with patch.object(model_client,'DECISION_MODEL','d1:latest'), patch.object(model_client,'request',return_value=bad) as request:
            with self.assertRaises(RuntimeError):model_client.decisions('Evidence',q)
        self.assertEqual(request.call_count,2);self.assertEqual(request.call_args.args[0],'/v1/systemone')
        self.assertEqual(request.call_args.args[1]['model'],'d1:latest')

    def test_minicpm_decisions_use_chat_schema_and_image(self):
        q={'topic':{'type':'choice','instructions':'Choose folder','criteria':{'UI':'Design','Code':'Programming'}},
           'fit':{'type':'noul','instructions':'Is evidence clear?'}}
        result={'topic':{'choice':'UI','confidence':.75},'fit':{'noul':1}}
        with tempfile.TemporaryDirectory() as tmp:
            image=Path(tmp)/'cover.jpg';image.write_bytes(b'image')
            with patch.object(model_client,'DECISION_MODEL',model_client.VISION_MODEL), patch.object(model_client,'request',return_value={'message':{'content':json.dumps(result)}}) as request:
                value=model_client.decisions({'caption':'Interface layout'},q,[image])
            self.assertEqual(request.call_args.args[0],'/api/chat')
            self.assertEqual(request.call_args.args[1]['model'],'minicpm-v4.6:latest')
            self.assertEqual(request.call_args.args[1]['messages'][1]['images'],['aW1hZ2U='])
            self.assertEqual(value['topic']['probabilities'],{'UI':.75,'Code':.25})
            self.assertEqual(value['topic']['score_source'],'generated_estimate')
            self.assertEqual(value['fit']['noul'],1)

    def test_native_decision_images_and_probabilities(self):
        q={'fit':{'type':'noul','instructions':'Does this fit?'}}
        with tempfile.TemporaryDirectory() as tmp:
            image=Path(tmp)/'cover.jpg';image.write_bytes(b'image')
            with patch.object(model_client,'DECISION_MODEL','d1:latest'), patch.object(model_client,'request',return_value={'answers':{'fit':{'type':'noul','noul':.98}}}) as request:
                value=model_client.decisions({'caption':'Basil'},q,[image])
            self.assertEqual(value['fit']['noul'],.98);self.assertEqual(request.call_args.args[1]['images'],['aW1hZ2U='])


if __name__=='__main__':unittest.main()
