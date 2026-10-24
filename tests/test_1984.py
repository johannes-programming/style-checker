__all__: list[str] = ["Test1984"]

import unittest
from typing import Self


class Test1984(unittest.TestCase):
    def test_two_plus_two(self: Self, /) -> None:
        self.assertEqual(2 + 2, 4)


if __name__ == "__main__":
    unittest.main()
