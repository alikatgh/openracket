#!/usr/bin/env python3
"""Dependency-free checks for the plain project-information page."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Document(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.elements = []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


def luminance(value):
    channels = [int(value[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4 for c in channels]
    return sum(c * w for c, w in zip(linear, (.2126, .7152, .0722)))


def contrast(a, b):
    lo, hi = sorted((luminance(a), luminance(b)))
    return (hi + .05) / (lo + .05)


class SiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / 'index.html').read_text()
        cls.css = (ROOT / 'styles.css').read_text()
        cls.doc = Document(cls.html)

    def test_landmarks_and_heading_order(self):
        tags = [tag for tag, _ in self.doc.elements]
        for tag in ['main', 'header', 'footer', 'h1']:
            self.assertEqual(tags.count(tag), 1)
        self.assertEqual(tags.count('h2'), 5)
        self.assertIn(('html', {'lang': 'en'}), self.doc.elements)
        previous = 0
        for tag in tags:
            if re.fullmatch('h[1-6]', tag):
                level = int(tag[1])
                self.assertLessEqual(level, previous + 1)
                previous = level

    def test_unique_ids_and_link_targets(self):
        ids = [attrs['id'] for _, attrs in self.doc.elements if 'id' in attrs]
        self.assertEqual(len(ids), len(set(ids)))
        for tag, attrs in self.doc.elements:
            for key in ['href', 'src']:
                if key not in attrs:
                    continue
                url = urlsplit(attrs[key])
                if url.scheme:
                    self.assertEqual(url.scheme, 'https')
                    self.assertIn(url.netloc, ['github.com', 'docs.racket-lang.org'])
                elif url.path:
                    self.assertFalse(url.path.startswith('/'))
                    self.assertTrue((ROOT / url.path).is_file(), attrs[key])
                if url.fragment and not url.path and not url.scheme:
                    self.assertIn(url.fragment, ids)
            for target in attrs.get('aria-labelledby', '').split():
                self.assertIn(target, ids)

    def test_metadata(self):
        metadata = {a.get('name'): a.get('content') for t, a in self.doc.elements if t == 'meta'}
        self.assertTrue(metadata.get('description'))
        self.assertTrue(metadata.get('viewport'))
        self.assertEqual(metadata['color-scheme'], 'light dark')
        self.assertIn('<title>OpenRacket — Project information</title>', self.html)

    def test_plain_static_page(self):
        tags = {tag for tag, _ in self.doc.elements}
        self.assertFalse(tags & {'script', 'img', 'svg', 'button', 'iframe', 'canvas'})
        self.assertNotIn('@import', self.css)
        self.assertNotIn('url(', self.css)
        self.assertNotIn('animation:', self.css)
        self.assertNotIn('transition:', self.css)
        for tag, attrs in self.doc.elements:
            self.assertNotIn('onclick', attrs)

    def test_keyboard_and_responsive_support(self):
        self.assertIn('class="skip-link" href="#main"', self.html)
        self.assertIn('id="main" tabindex="-1"', self.html)
        self.assertIn(':focus-visible', self.css)
        self.assertIn('max-width: 600px', self.css)
        self.assertIn('prefers-color-scheme: dark', self.css)
        self.assertIn('forced-colors: active', self.css)
        for tag, attrs in self.doc.elements:
            if tag == 'nav':
                self.assertTrue(attrs.get('aria-label'))

    def test_factual_project_content(self):
        for text in ['development preview', 'prototype/retained-drracket', 'Earlier Rust editor preview', 'Full equivalence with stock DrRacket has not been established', 'No speed multiplier is claimed.', 'not a security sandbox']:
            self.assertIn(text, self.html)
        for text in ['Fresh perspective', 'Familiar ground', 'Come look under', 'Explore the source', '100x', 'Download for Mac', 'production-ready']:
            self.assertNotIn(text, self.html)

    def test_all_project_pages(self):
        for name in ['index.html', 'changelog.html', 'blog.html']:
            with self.subTest(page=name):
                source = (ROOT / name).read_text()
                doc = Document(source)
                tags = [tag for tag, _ in doc.elements]
                for tag in ['main', 'header', 'footer', 'h1']:
                    self.assertEqual(tags.count(tag), 1)
                self.assertFalse(set(tags) & {'script', 'img', 'svg', 'iframe', 'canvas'})
                self.assertIn('class="skip-link" href="#main"', source)
                ids = [a['id'] for _, a in doc.elements if 'id' in a]
                self.assertEqual(len(ids), len(set(ids)))
                previous = 0
                for tag, attrs in doc.elements:
                    if re.fullmatch('h[1-6]', tag):
                        level = int(tag[1])
                        self.assertLessEqual(level, previous + 1)
                        previous = level
                    if tag == 'nav':
                        self.assertTrue(attrs.get('aria-label'))
                    for target in attrs.get('aria-labelledby', '').split():
                        self.assertIn(target, ids)
                    for key in ['href', 'src']:
                        if key not in attrs:
                            continue
                        url = urlsplit(attrs[key])
                        if url.scheme:
                            self.assertEqual(url.scheme, 'https')
                            self.assertIn(url.netloc, ['github.com', 'docs.racket-lang.org'])
                        else:
                            target = ROOT / (url.path or name)
                            self.assertTrue(target.is_file(), attrs[key])
                            if url.fragment:
                                target_ids = [a['id'] for _, a in Document(target.read_text()).elements if 'id' in a]
                                self.assertIn(url.fragment, target_ids)

    def test_measurement_scope(self):
        for name in ['changelog.html', 'blog.html']:
            source = (ROOT / name).read_text()
            for value in ['266.735', '172.400', '35.4%', '38061486888', '38064415026']:
                self.assertIn(value, source)
            self.assertIn('retimed', source)
            self.assertIn('Windows', source)
        blog = (ROOT / 'blog.html').read_text()
        for value in ['24.6%', 'three pairs', '34.373–39.619', 'statistical significance', '163–216']:
            self.assertIn(value, blog)

    def test_capacity_scope(self):
        for name in ['index.html', 'changelog.html', 'blog.html']:
            source = (ROOT / name).read_text()
            for text in ['256 MiB', '128 MiB', 'capacity']:
                self.assertIn(text, source)
        for name in ['changelog.html', 'blog.html']:
            source = (ROOT / name).read_text()
            for text in ['38114573816', '38107957744', '1.487–1.543', '33.222–39.155']:
                self.assertIn(text, source)

    def test_native_app_milestone_scope(self):
        for name in ['index.html', 'changelog.html', 'blog.html']:
            source = (ROOT / name).read_text()
            for text in ['114 app checks', '38127332821', 'tethered', 'unsigned',
                         'not notarized', 'Script Editor', 'Gatekeeper',
                         'overall', 'red', 'unset']:
                self.assertIn(text, source)
            self.assertIn('dae4b69d34a793404f1e8ddf35a65948d33ae980', source)
        blog = (ROOT / 'blog.html').read_text()
        for text in ['CFBundleDocumentTypes', '26,838', 'Normal Quit',
                     'not a self-contained binary download', 'Six Debugger']:
            self.assertIn(text, blog)
        readme = (ROOT.parent / 'README.md').read_text()
        for text in ['114 app checks', '38127332821', 'unsigned',
                     'initially unset handler was not tested', 'overall CI run is red']:
            self.assertIn(text, readme)

    def test_css_delimiters(self):
        self.assertEqual(self.css.count('{'), self.css.count('}'))
        self.assertEqual(self.css.count('('), self.css.count(')'))

    def test_text_contrast(self):
        for foreground, background in [
            ('#202124', '#ffffff'), ('#50545a', '#ffffff'), ('#1854a3', '#ffffff'),
            ('#202124', '#f0f2f4'), ('#e6e8eb', '#191b1e'), ('#b4bac3', '#191b1e'),
            ('#9bc5ff', '#191b1e'), ('#e6e8eb', '#2b2f35')
        ]:
            self.assertGreaterEqual(contrast(foreground, background), 4.5)


if __name__ == '__main__':
    unittest.main(verbosity=2)
