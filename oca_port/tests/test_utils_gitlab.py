import unittest

from oca_port.utils import gitlab


class TestGitLab(unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.gl = gitlab.GitLab(token="test")

    def test_token(self):
        assert self.gl.token == "test"

    def test_addon_in_text(self):
        res = self.gl._addon_in_text("a_b", "[16.0][MIG] a_b: migration to 16.0")
        assert res
        res = self.gl._addon_in_text("a_b", "[16.0][MIG] a_b_c: migration to 16.0")
        assert not res
