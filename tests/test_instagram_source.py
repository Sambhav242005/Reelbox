import contextlib
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import app
import instagram_source as source


class Post:
    caption = 'Grow basil\nGive it sunlight.'
    owner_username = 'gardener'
    url = 'https://scontent.cdninstagram.com/cover.jpg'
    is_video = True
    video_duration = 15

    @property
    def video_url(self):
        raise AssertionError('Metadata requested video URL')


class Response:
    is_redirect = False
    headers = {'Content-Type':'video/mp4'}
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def raise_for_status(self):pass
    def iter_content(self,size):yield b'\x00\x00\x00\x18ftypisom'+b'x'*20


class SourceTests(unittest.TestCase):
    def resolve(self,post,video=False):
        with patch.object(source,'client',return_value=contextlib.nullcontext(SimpleNamespace(context=None))),patch('instaloader.Post.from_shortcode',return_value=post):
            return source.resolve('https://www.instagram.com/reel/basil/',{},lambda:None,include_video=video)

    def test_metadata_never_resolves_or_downloads_video(self):
        with patch('requests.get') as get:
            result=self.resolve(Post())
        get.assert_not_called()
        self.assertNotIn('video_url',result)
        self.assertEqual(result['title'],'Grow basil')
        self.assertEqual(result['caption'],'Grow basil\nGive it sunlight.')

    def test_explicit_video_resolves_media(self):
        post=SimpleNamespace(caption='Basil',owner_username='gardener',url=Post.url,is_video=True,video_duration=15,video_url='https://scontent.cdninstagram.com/video.mp4')
        result=self.resolve(post,True)
        self.assertEqual(result['video_url'],post.video_url)

    def test_non_video_is_rejected_without_media_fetch(self):
        post=Post();post.is_video=False
        with self.assertRaisesRegex(ValueError,'no video'):self.resolve(post,True)

    def test_overlong_video_is_rejected_before_video_url(self):
        post=Post();post.video_duration=601
        with self.assertRaisesRegex(ValueError,'10 minutes'):self.resolve(post,True)

    def test_metadata_wrapper_does_not_enable_video(self):
        with patch.object(app,'settings',return_value={}),patch.object(source,'resolve',return_value={'title':'Basil'}) as resolve:
            self.assertEqual(app.metadata('url'),{'title':'Basil'})
        self.assertNotIn('include_video',resolve.call_args.kwargs)

    def test_download_wrapper_enables_video_and_removes_signed_url(self):
        info={'title':'Basil','caption':'Grow basil','creator':'gardener','video_url':'signed-url'}
        with patch.object(app,'settings',return_value={}),patch.object(source,'resolve',return_value=info) as resolve,patch.object(source,'download_video',return_value=Path('video.mp4')):
            _,result=app.download('url',Path('.'))
        self.assertTrue(resolve.call_args.kwargs['include_video'])
        self.assertNotIn('video_url',result)
        self.assertEqual(result['description'],'Grow basil')

    def test_untrusted_media_host_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder,patch('requests.get') as get:
            with self.assertRaises(ValueError):source.download_video('https://example.com/video',folder,lambda:None)
        get.assert_not_called()

    def test_media_has_no_session_cookies(self):
        with tempfile.TemporaryDirectory() as folder,patch('requests.get',return_value=Response()) as get:
            target=source.download_video('https://scontent.cdninstagram.com/video',folder,lambda:None)
            self.assertTrue(target.exists())
        self.assertNotIn('cookies',get.call_args.kwargs)
        self.assertFalse(get.call_args.kwargs['allow_redirects'])

    def test_redirect_host_is_checked(self):
        response=Response();response.is_redirect=True;response.headers={'Location':'https://example.com/video'}
        with tempfile.TemporaryDirectory() as folder,patch('requests.get',return_value=response) as get:
            with self.assertRaises(ValueError):source.download_video('https://scontent.cdninstagram.com/video',folder,lambda:None)
        self.assertEqual(get.call_count,1)

    def test_stop_during_download_removes_partial_media(self):
        calls=0
        def checkpoint():
            nonlocal calls
            calls+=1
            if calls==3:raise app.ProcessingStopped()
        with tempfile.TemporaryDirectory() as folder,patch('requests.get',return_value=Response()):
            with self.assertRaises(app.ProcessingStopped):source.download_video('https://scontent.cdninstagram.com/video',folder,checkpoint)
            self.assertEqual(list(Path(folder).iterdir()),[])

    def test_invalid_mp4_is_removed(self):
        response=Response();response.iter_content=lambda size:iter([b'not a video'])
        with tempfile.TemporaryDirectory() as folder,patch('requests.get',return_value=response):
            with self.assertRaises(ValueError):source.download_video('https://scontent.cdninstagram.com/video',folder,lambda:None)
            self.assertEqual(list(Path(folder).iterdir()),[])


if __name__=='__main__':unittest.main()
