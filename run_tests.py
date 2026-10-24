"""Test the package."""

__all__: list[str] = ["main", "run"]

import sys
import unittest
from typing import Never


def main() -> Never:
    sys.exit(not run().wasSuccessful())


def run() -> unittest.TextTestResult:
    loader: unittest.TestLoader
    suite: unittest.TestSuite
    runner: unittest.TextTestRunner
    loader = unittest.TestLoader()
    suite = loader.discover("tests")
    runner = unittest.TextTestRunner(verbosity=2)
    return runner.run(suite)


if __name__ == "__main__":
    main()
