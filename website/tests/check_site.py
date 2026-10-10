#!/usr/bin/env python3
"""Dependency-free source checks, not a substitute for browser QA."""
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
    channels = [c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4 for c in channels]
    return sum(c * w for c, w in zip(channels, (.2126, .7152, .0722)))


def contrast(a, b):
    values = sorted((luminance(a), luminance(b)))
    return (values[1] + .05) / (values[0] + .05)


class SiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / 'index.html').read_text()
        cls.css = (ROOT / 'styles.css').read_text()
        cls.js = (ROOT / 'script.js').read_text()
        cls.doc = Document(cls.html)

    def test_landmarks_and_headings(self):
        tags = [tag for tag, _ in self.doc.elements]
        self.assertEqual(tags.count('main'), 1)
        self.assertEqual(tags.count('header'), 1)
        self.assertEqual(tags.count('footer'), 1)
        self.assertEqual(tags.count('h1'), 1)
        self.assertGreaterEqual(tags.count('h2'), 5)
        self.assertIn(('html', {'lang': 'en'}), self.doc.elements)
        previous = 0
        for tag in tags:
            if re.fullmatch('h[1-6]', tag):
                level = int(tag[1])
                self.assertLessEqual(level, previous + 1, f'Heading level skipped before {tag}')
                previous = level

    def test_unique_ids_and_all_local_targets(self):
        ids = [attrs['id'] for _, attrs in self.doc.elements if 'id' in attrs]
        self.assertEqual(len(ids), len(set(ids)))
        for tag, attrs in self.doc.elements:
            for key in ('href', 'src'):
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
            if 'aria-labelledby' in attrs:
                for target in attrs['aria-labelledby'].split():
                    self.assertIn(target, ids)

    def test_metadata(self):
        metadata = {a.get('name', a.get('property')): a.get('content') for t, a in self.doc.elements if t == 'meta'}
        for key in ['viewport', 'description', 'theme-color', 'og:title', 'og:description']:
            self.assertTrue(metadata.get(key), key)
        self.assertIn('<title>OpenRacket', self.html)

    def test_accessibility_contracts(self):
        self.assertIn('class="skip-link" href="#main"', self.html)
        self.assertIn('aria-live="polite"', self.html)
        buttons = [a for t, a in self.doc.elements if t == 'button']
        self.assertEqual(len(buttons), 2)
        for attrs in buttons:
            self.assertEqual(attrs.get('type'), 'button')
            self.assertIn(attrs.get('aria-pressed'), ['true', 'false'])
        for tag, attrs in self.doc.elements:
            self.assertNotIn('onclick', attrs)
            if tag == 'svg':
                self.assertEqual(attrs.get('aria-hidden'), 'true')
            if tag == 'nav':
                self.assertTrue(attrs.get('aria-label'))
        for fragment in [':focus-visible', 'prefers-reduced-motion:reduce', 'forced-colors:active', '@media(max-width:760px)', '@media(max-width:380px)']:
            self.assertIn(fragment, self.css)

    def test_content_is_honest_about_preview(self):
        for fragment in ['Interface design study.', 'not a running app or screenshot', 'No speed multiplier is claimed.', 'earlier Rust editor preview', 'Development preview', 'Not an official Racket or DrRacket release']:
            self.assertIn(fragment, self.html)
        for fragment in ['100x', 'Download for Mac', 'production-ready', 'download="']:
            self.assertNotIn(fragment, self.html)

    def test_no_external_runtime_or_tracking(self):
        for tag, attrs in self.doc.elements:
            if tag == 'script':
                self.assertEqual(attrs.get('src'), 'script.js')
                self.assertIn('defer', attrs)
        for word in ['fetch(', 'XMLHttpRequest', 'localStorage', 'sessionStorage', 'document.cookie', 'eval(', 'innerHTML', 'https://']:
            self.assertNotIn(word, self.js)
        self.assertNotIn('@import', self.css)
        self.assertNotIn('url(http', self.css)

    def test_css_balanced(self):
        self.assertEqual(self.css.count('{'), self.css.count('}'))
        self.assertEqual(self.css.count('('), self.css.count(')'))

    def test_text_color_contrast_pairs(self):
        pairs = {
            'body': ('#182d36', '#f4f1e9'),
            'muted copy': ('#53616a', '#f4f1e9'),
            'blue link': ('#244bca', '#f4f1e9'),
            'blue button': ('#ffffff', '#244bca'),
            'workspace note': ('#4c606b', '#e4e9ee'),
            'preview caption': ('#4f626e', '#e4e9ee'),
            'light editor muted': ('#596c78', '#fffefa'),
            'light editor chrome': ('#596c78', '#f2f2ef'),
            'light editor keyword': ('#6746a2', '#fffefa'),
            'light editor function': ('#2059b0', '#fffefa'),
            'light editor number': ('#28775d', '#fffefa'),
            'dark editor muted': ('#a3b4c2', '#172530'),
            'dark editor chrome': ('#a3b4c2', '#20313e'),
            'dark editor keyword': ('#c8acec', '#172530'),
            'dark editor function': ('#97beff', '#172530'),
            'dark editor number': ('#91cbb6', '#172530'),
            'architecture label': ('#506452', '#f5f6ef'),
            'architecture caption': ('#55624f', '#e8ebe1'),
            'closing eyebrow': ('#d0daff', '#244bca'),
            'development badge': ('#645e42', '#f4f1e9'),
        }
        for label, (fg, bg) in pairs.items():
            with self.subTest(label=label):
                self.assertGreaterEqual(contrast(fg, bg), 4.5, f'{label}: {contrast(fg, bg):.2f}:1')


if __name__ == '__main__':
    unittest.main(verbosity=2)
