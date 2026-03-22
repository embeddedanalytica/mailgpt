import unittest
from pathlib import Path

from skills.coaching_reasoning.doctrine import (
    _CACHE,
    _resolve_sport,
    build_doctrine_context,
    list_loaded_files,
)
from skills.coaching_reasoning.doctrine.manifest import (
    GENERAL_FILES,
    SPORT_ALIASES,
    SPORT_FILES,
    UNIVERSAL_FILES,
)

_DOCTRINE_DIR = Path(__file__).parent / "skills" / "coaching_reasoning" / "doctrine"


class TestManifestIntegrity(unittest.TestCase):
    """Every file referenced in the manifest must exist and be non-empty."""

    def _all_manifest_files(self):
        files = list(UNIVERSAL_FILES) + list(GENERAL_FILES)
        for sport_files in SPORT_FILES.values():
            files.extend(sport_files)
        return files

    def test_all_referenced_files_exist(self):
        for rel_path in self._all_manifest_files():
            full = _DOCTRINE_DIR / rel_path
            self.assertTrue(full.exists(), f"Missing doctrine file: {rel_path}")

    def test_all_referenced_files_non_empty(self):
        for rel_path in self._all_manifest_files():
            full = _DOCTRINE_DIR / rel_path
            content = full.read_text().strip()
            self.assertTrue(len(content) > 0, f"Empty doctrine file: {rel_path}")


class TestResolveSport(unittest.TestCase):

    def test_exact_match(self):
        self.assertEqual(_resolve_sport("running"), "running")

    def test_alias_marathon(self):
        self.assertEqual(_resolve_sport("marathon"), "running")

    def test_alias_half_marathon(self):
        self.assertEqual(_resolve_sport("half marathon"), "running")

    def test_alias_case_insensitive(self):
        self.assertEqual(_resolve_sport("Marathon"), "running")
        self.assertEqual(_resolve_sport("TRAIL RUNNING"), "running")

    def test_none_returns_none(self):
        self.assertIsNone(_resolve_sport(None))

    def test_empty_returns_none(self):
        self.assertIsNone(_resolve_sport(""))
        self.assertIsNone(_resolve_sport("   "))

    def test_unknown_sport_returns_none(self):
        self.assertIsNone(_resolve_sport("cricket"))


class TestBuildDoctrineContext(unittest.TestCase):

    def test_running_includes_running_methodology(self):
        ctx = build_doctrine_context("running")
        self.assertIn("Daniels", ctx)
        self.assertIn("easy run paradox", ctx.lower())

    def test_running_includes_universal(self):
        ctx = build_doctrine_context("running")
        self.assertIn("periodization", ctx.lower())

    def test_running_includes_general_recommendations(self):
        ctx = build_doctrine_context("running")
        self.assertIn("Outlive", ctx)

    def test_none_excludes_sport_specific(self):
        ctx = build_doctrine_context(None)
        self.assertNotIn("Daniels", ctx)
        self.assertNotIn("Pfitzinger", ctx)

    def test_none_includes_universal_and_general(self):
        ctx = build_doctrine_context(None)
        self.assertIn("periodization", ctx.lower())
        self.assertIn("Outlive", ctx)

    def test_unknown_sport_same_as_none(self):
        ctx_none = build_doctrine_context(None)
        ctx_cricket = build_doctrine_context("cricket")
        self.assertEqual(ctx_none, ctx_cricket)

    def test_no_cross_contamination(self):
        """When cycling doctrine exists, running context must not include it."""
        # Currently only running exists — verify it doesn't load nonexistent sport files
        files = list_loaded_files("running")
        for f in files:
            self.assertNotIn("cycling/", f)


class TestListLoadedFiles(unittest.TestCase):

    def test_running_includes_sport_files(self):
        files = list_loaded_files("running")
        self.assertIn("running/methodology.md", files)
        self.assertIn("running/recommendations.md", files)

    def test_running_includes_universal(self):
        files = list_loaded_files("running")
        for f in UNIVERSAL_FILES:
            self.assertIn(f, files)

    def test_running_includes_general(self):
        files = list_loaded_files("running")
        for f in GENERAL_FILES:
            self.assertIn(f, files)

    def test_alias_resolves(self):
        files_alias = list_loaded_files("half marathon")
        files_direct = list_loaded_files("running")
        self.assertEqual(files_alias, files_direct)

    def test_none_excludes_sport_files(self):
        files = list_loaded_files(None)
        self.assertNotIn("running/methodology.md", files)
        self.assertNotIn("running/recommendations.md", files)


class TestCaching(unittest.TestCase):

    def setUp(self):
        _CACHE.clear()

    def test_files_cached_after_first_load(self):
        build_doctrine_context("running")
        cached_keys = set(_CACHE.keys())
        expected_files = set(UNIVERSAL_FILES) | set(SPORT_FILES["running"]) | set(GENERAL_FILES)
        self.assertEqual(cached_keys, expected_files)

    def test_second_load_uses_cache(self):
        build_doctrine_context("running")
        first_result = build_doctrine_context("running")
        # Cache should still have same keys — no re-reads
        cached_keys_after = set(_CACHE.keys())
        expected_files = set(UNIVERSAL_FILES) | set(SPORT_FILES["running"]) | set(GENERAL_FILES)
        self.assertEqual(cached_keys_after, expected_files)
        second_result = build_doctrine_context("running")
        self.assertEqual(first_result, second_result)


if __name__ == "__main__":
    unittest.main()
