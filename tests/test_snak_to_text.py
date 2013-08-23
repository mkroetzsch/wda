import unittest
from includes.rpkb import snaktotext


class TestSnakToText(unittest.TestCase):

    def test_passes(self):
        snak = [
            'somevalue',
            42
        ]

        snakText = snaktotext(snak)

        self.assertIsInstance(snakText, str)
        self.assertEqual(snakText, 'P42 +')