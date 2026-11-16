"""Guards for the landed F008/F010/F005/F011 patches and the F013/F014 follow-ups.

Run from the repository root:

    python3 -m unittest discover -s tests -v

These files sit under tests/ so that fixture literals (home paths, RFC1918
text, and the like) are skipped by tools/verify.py's published-tree walk.
"""
import importlib.util
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]


def load_mod(name, path, env=None):
    if env:
        for k, v in env.items():
            os.environ[k] = v
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


verify = load_mod('mc_verify', REPO / 'tools/verify.py')
build = load_mod('mc_build', REPO / 'tools/build.py')
prepare = load_mod('mc_prepare', REPO / 'tools/prepare_personal.py')
_td = tempfile.mkdtemp(prefix='mc-collect-root-')
collect = load_mod('mc_collect', REPO / 'tools/offline/collect.py', env={'MARS_CACHE_COLLECTION': _td})


def write(p, text='', data=None):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    if data is not None:
        p.write_bytes(data)
    else:
        p.write_text(text, encoding='utf-8')
    return p


class TestF008Helpers(unittest.TestCase):
    def test_banned_parts_case_insensitive(self):
        for part in ('Loompanics', 'LOOMPANICS', 'Private', 'private', 'Mars-Cache-Personal', 'MARS-CACHE-PRIVATE'):
            self.assertTrue(verify.path_has_banned_part(Path('site') / part / 'x'), part)

    def test_layout_denies_private_and_unknown_library(self):
        site = Path('/tmp/not-used-site')
        self.assertFalse(verify.site_layout_allowed(site / 'private' / 'x', site))
        self.assertFalse(verify.site_layout_allowed(site / 'library' / 'secret' / 'x', site))
        self.assertTrue(verify.site_layout_allowed(site / 'library' / 'maps-and-navigation' / 'ok.pdf', site))
        self.assertTrue(verify.site_layout_allowed(site / 'index.html', site))

    def test_home_and_env_leaks(self):
        self.assertTrue(verify.private_text_leaks('path is ~/secret/file'))
        self.assertTrue(verify.private_text_leaks('uses $HOME/cache'))
        self.assertTrue(verify.private_text_leaks('uses ${HOME} as root'))
        self.assertTrue(verify.private_text_leaks('also ~user/stuff'))

    def test_restricted_ips(self):
        self.assertTrue(verify.text_has_restricted_ip('gw 192.168.0.2'))
        self.assertTrue(verify.text_has_restricted_ip('ula fd12:3456::1'))
        self.assertTrue(verify.text_has_restricted_ip('ula fc00::1'))
        self.assertTrue(verify.text_has_restricted_ip('ll fe80::1'))
        self.assertTrue(verify.text_has_restricted_ip('mapped ::ffff:192.168.0.2'))
        self.assertTrue(verify.text_has_restricted_ip('hex ::ffff:c0a8:101'))
        self.assertTrue(verify.text_has_restricted_ip('link 169.254.1.1'))
        self.assertTrue(verify.text_has_restricted_ip('ten 10.1.2.3'))
        self.assertFalse(verify.text_has_restricted_ip('public 8.8.8.8'))
        self.assertFalse(verify.text_has_restricted_ip('public 1.2.3.4'))

    def test_verify_py_does_not_self_match(self):
        text = (REPO / 'tools/verify.py').read_text(encoding='utf-8')
        self.assertFalse(verify.private_text_leaks(text))
        self.assertFalse(verify.text_has_restricted_ip(text))


class VerifyTreeTest(unittest.TestCase):
    def _mini_site(self, root):
        site = Path(root) / 'site'
        write(site / 'catalog.json', '[]')
        write(site / 'SHA256SUMS.txt', '')
        write(site / 'index.html', '<!doctype html><title>ok</title>')
        return site

    def _run(self, root):
        old_root, old_site = verify.ROOT, verify.SITE
        verify.ROOT = Path(root)
        verify.SITE = Path(root) / 'site'
        buf = io.StringIO()
        try:
            with mock.patch('sys.stdout', buf):
                rc = verify.main()
            return rc, buf.getvalue()
        finally:
            verify.ROOT, verify.SITE = old_root, old_site


class TestF008Tree(VerifyTreeTest):
    def test_clean_mini_tree_exits_0(self):
        with tempfile.TemporaryDirectory() as td:
            self._mini_site(td)
            rc, out = self._run(td)
            self.assertEqual(rc, 0, out)

    def test_fixture_banned_dirs_fail(self):
        for rel in ('site/Loompanics/x.txt', 'site/library/LOOMPANICS/x.txt', 'site/Private/x.txt'):
            with self.subTest(rel=rel):
                with tempfile.TemporaryDirectory() as td:
                    root = Path(td)
                    self._mini_site(root)
                    write(root / rel, 'ok')
                    rc, out = self._run(root)
                    self.assertEqual(rc, 1, out)

    def test_fixture_text_leaks_fail(self):
        cases = {
            'rfc1918.txt': 'router at 192.168.1.1',
            'ffff.txt': 'mapped ::ffff:c0a8:101',
            'home.txt': 'root is $HOME/cache',
        }
        for name, text in cases.items():
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory() as td:
                    root = Path(td)
                    self._mini_site(root)
                    write(root / 'site' / name, text)
                    rc, out = self._run(root)
                    self.assertEqual(rc, 1, out)

    def test_renamed_binary_in_allowed_folder_not_caught(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._mini_site(root)
            write(root / 'site/library/maps-and-navigation/secret-renamed.bin', data=b'\x00secret')
            rc, out = self._run(root)
            self.assertEqual(rc, 0, out)


class TestF013ReservedFolders(VerifyTreeTest):
    def test_helper_casefold_under_allowed_category(self):
        site = Path('/tmp/not-used-site')
        for part in ('health-and-sanitation', 'Health-And-Sanitation', 'HEALTH-AND-SANITATION',
                     'original-html', 'Original-HTML', 'ORIGINAL-HTML'):
            path = site / 'library' / 'maps-and-navigation' / part / 'x.txt'
            self.assertTrue(verify.path_has_reserved_site_part(path, site), part)

    def test_mixed_case_nests_fail_verify(self):
        cases = (
            'site/library/maps-and-navigation/Health-And-Sanitation/x.txt',
            'site/library/maps-and-navigation/Original-HTML/x.txt',
            'site/library/maps-and-navigation/health-and-sanitation/x.txt',
            'site/library/maps-and-navigation/original-html/x.txt',
        )
        for rel in cases:
            with self.subTest(rel=rel):
                with tempfile.TemporaryDirectory() as td:
                    root = Path(td)
                    self._mini_site(root)
                    write(root / rel, 'ok')
                    rc, out = self._run(root)
                    self.assertEqual(rc, 1, out)
                    self.assertIn('Private/publisher-restricted folder exported', out)

    def test_first_level_mixed_case_still_refused(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._mini_site(root)
            write(root / 'site/Health-And-Sanitation/x.txt', 'ok')
            rc, out = self._run(root)
            self.assertEqual(rc, 1, out)


class TestF014SiteSymlinks(VerifyTreeTest):
    def test_unlisted_symlink_pdf_outside_tree_fails(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            site = self._mini_site(root)
            outside = write(Path(td) / 'outside.pdf', data=b'%PDF-1.4 outside')
            link = site / 'library' / 'maps-and-navigation' / 'leak.pdf'
            link.parent.mkdir(parents=True, exist_ok=True)
            link.symlink_to(outside)
            rc, out = self._run(root)
            self.assertEqual(rc, 1, out)
            self.assertIn('Refusing symlink in published site/', out)

    def test_symlink_txt_without_text_leak_fails_on_symlink_rule(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            site = self._mini_site(root)
            outside = write(Path(td) / 'plain.txt', 'just a note')
            link = site / 'alias.txt'
            link.symlink_to(outside)
            rc, out = self._run(root)
            self.assertEqual(rc, 1, out)
            self.assertIn('Refusing symlink in published site/', out)
            self.assertNotIn('Potential private export', out)

    def test_symlinked_parent_directory_under_site_fails(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            site = self._mini_site(root)
            realdir = Path(td) / 'realdir'
            realdir.mkdir()
            write(realdir / 'child.txt', 'ok')
            dest = site / 'library' / 'maps-and-navigation' / 'via'
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.symlink_to(realdir)
            rc, out = self._run(root)
            self.assertEqual(rc, 1, out)
            self.assertIn('Refusing symlink in published site/', out)

    def test_regular_file_and_hardlink_still_allowed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            site = self._mini_site(root)
            real = write(site / 'library' / 'maps-and-navigation' / 'ok.bin', data=b'\x00ok')
            hard = site / 'library' / 'maps-and-navigation' / 'ok-hard.bin'
            os.link(real, hard)
            rc, out = self._run(root)
            self.assertEqual(rc, 0, out)


class TestF010BuildPaths(unittest.TestCase):
    def test_refuses_parent_escape(self):
        with tempfile.TemporaryDirectory() as td:
            collection = Path(td) / 'col'
            site = Path(td) / 'site'
            collection.mkdir(); site.mkdir()
            write(Path(td) / 'outside.pdf', data=b'%PDF-1.4')
            with self.assertRaises(ValueError) as ctx:
                build.public_export_paths(collection, site, '../outside.pdf')
            self.assertIn('outside', str(ctx.exception).lower())

    def test_refuses_in_tree_symlink_file(self):
        with tempfile.TemporaryDirectory() as td:
            collection = Path(td) / 'col'
            site = Path(td) / 'site'
            collection.mkdir(); site.mkdir()
            real = write(collection / 'real.pdf', data=b'%PDF-1.4')
            link = collection / 'link.pdf'
            link.symlink_to(real)
            with self.assertRaises(ValueError) as ctx:
                build.public_export_paths(collection, site, 'link.pdf')
            self.assertIn('symlink', str(ctx.exception).lower())

    def test_refuses_symlink_to_file_outside_collection(self):
        with tempfile.TemporaryDirectory() as td:
            collection = Path(td) / 'col'
            site = Path(td) / 'site'
            collection.mkdir(); site.mkdir()
            outside = write(Path(td) / 'outside.pdf', data=b'%PDF-1.4')
            link = collection / 'inside.pdf'
            link.symlink_to(outside)
            with self.assertRaises(ValueError) as ctx:
                build.public_export_paths(collection, site, 'inside.pdf')
            self.assertIn('symlink', str(ctx.exception).lower())

    def test_refuses_symlinked_parent_directory(self):
        with tempfile.TemporaryDirectory() as td:
            collection = Path(td) / 'col'
            site = Path(td) / 'site'
            realdir = Path(td) / 'realdir'
            collection.mkdir(); site.mkdir(); realdir.mkdir()
            write(realdir / 'child.pdf', data=b'%PDF-1.4')
            (collection / 'via').symlink_to(realdir)
            with self.assertRaises(ValueError) as ctx:
                build.public_export_paths(collection, site, 'via/child.pdf')
            self.assertIn('symlink', str(ctx.exception).lower())

    def test_accepts_normal_in_collection_file(self):
        with tempfile.TemporaryDirectory() as td:
            collection = Path(td) / 'col'
            site = Path(td) / 'site'
            collection.mkdir(); site.mkdir()
            write(collection / 'ok.pdf', data=b'%PDF-1.4')
            src, dst = build.public_export_paths(collection, site, 'ok.pdf')
            self.assertTrue(src.is_relative_to(collection.resolve()))
            self.assertTrue(dst.is_relative_to(site.resolve()))


class TestF005Allowlist(unittest.TestCase):
    def test_accepts_usgs_and_hesperian(self):
        self.assertTrue(prepare.source_host_allowed('https://prd-tnm.s3.amazonaws.com/file.pdf'))
        self.assertTrue(prepare.source_host_allowed('https://hesperian.org/file.pdf'))

    def test_rejects_suffix_bypass_and_http(self):
        self.assertFalse(prepare.source_host_allowed('https://evil.amazonaws.com/x'))
        self.assertFalse(prepare.source_host_allowed('https://evil.hesperian.org/x'))
        self.assertFalse(prepare.source_host_allowed('http://hesperian.org/x'))
        self.assertFalse(prepare.source_host_allowed('http://www.cdc.gov/x'))

    def test_collect_allowlist_matches_prepare(self):
        self.assertEqual(prepare.ALLOWED_HOSTS, collect.ALLOWED_HOSTS)

    def test_all_plan_urls_allowed(self):
        import json
        from urllib.parse import urlparse
        plan = json.loads((REPO / 'data/personal-download-plan.json').read_text(encoding='utf-8'))
        bad = []
        for x in plan:
            if not prepare.source_host_allowed(x['url']):
                bad.append(urlparse(x['url']).hostname)
        self.assertEqual(bad, [])


class FakeResp:
    def __init__(self, url, status=200, headers=None, body=b'ok'):
        self.url = url
        self.status_code = status
        self.headers = headers or {}
        self._body = body
        self.is_redirect = status in (301, 302, 303, 307, 308)
        self.is_permanent_redirect = status in (301, 308)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError('HTTP %s' % self.status_code)

    def iter_content(self, size):
        yield self._body


class TestF011Redirects(unittest.TestCase):
    def setUp(self):
        collect.downloaded = 0

    def test_offlist_302_is_refused_and_not_fetched(self):
        calls = []

        def fake_get(url, headers=None, timeout=None, stream=None, allow_redirects=None):
            calls.append({'url': url, 'allow_redirects': allow_redirects})
            if url == 'https://www.cdc.gov/start.pdf':
                return FakeResp(url, status=302, headers={'Location': 'https://evil.amazonaws.com/secret.pdf'})
            raise AssertionError('off-list hop was fetched: ' + url)

        with mock.patch.object(collect.requests, 'get', side_effect=fake_get):
            with self.assertRaises(ValueError) as ctx:
                collect.request_bytes('https://www.cdc.gov/start.pdf')
        self.assertIn('Unexpected source host: evil.amazonaws.com', str(ctx.exception))
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]['url'], 'https://www.cdc.gov/start.pdf')
        self.assertIs(calls[0]['allow_redirects'], False)

    def test_direct_allowed_host_download_works(self):
        def fake_get(url, headers=None, timeout=None, stream=None, allow_redirects=None):
            self.assertEqual(url, 'https://www.cdc.gov/start.pdf')
            self.assertIs(allow_redirects, False)
            return FakeResp(url, status=200, body=b'PDFDATA')

        with mock.patch.object(collect.requests, 'get', side_effect=fake_get):
            body, final, _headers = collect.request_bytes('https://www.cdc.gov/start.pdf')
        self.assertEqual(body, b'PDFDATA')
        self.assertEqual(final, 'https://www.cdc.gov/start.pdf')

    def test_five_allowed_follows_then_body_succeeds(self):
        # Plan cap is 5 follows. A chain of 5 Locations ending in 200 must work.
        chain = ['https://www.cdc.gov/r%d' % i for i in range(6)]
        calls = []

        def fake_get(url, headers=None, timeout=None, stream=None, allow_redirects=None):
            calls.append(url)
            if url in chain[:-1]:
                nxt = chain[chain.index(url) + 1]
                return FakeResp(url, status=302, headers={'Location': nxt})
            if url == chain[-1]:
                return FakeResp(url, status=200, body=b'AFTER5')
            raise AssertionError('unexpected url ' + url)

        with mock.patch.object(collect.requests, 'get', side_effect=fake_get):
            body, final, _headers = collect.request_bytes(chain[0])
        self.assertEqual(body, b'AFTER5')
        self.assertEqual(calls, chain)

    def test_sixth_follow_is_refused_and_not_fetched(self):
        # Six Location hops must raise; the seventh URL must not be fetched.
        chain = ['https://www.cdc.gov/r%d' % i for i in range(7)]
        calls = []

        def fake_get(url, headers=None, timeout=None, stream=None, allow_redirects=None):
            calls.append(url)
            nxt = chain[chain.index(url) + 1]
            return FakeResp(url, status=302, headers={'Location': nxt})

        with mock.patch.object(collect.requests, 'get', side_effect=fake_get):
            with self.assertRaises(ValueError) as ctx:
                collect.request_bytes(chain[0])
        self.assertIn('Too many redirects', str(ctx.exception))
        self.assertEqual(calls, chain[:6])
        self.assertNotIn(chain[6], calls)


if __name__ == '__main__':
    unittest.main(verbosity=2)
