"""Test the package."""

__all__: list[str] = ["main", "run"]

import sys
import unittest


def main() -> int:
    return 1 - run().wasSuccessful()


def run() -> unittest.TextTestResult:
    loader: unittest.TestLoader
    runner: unittest.TextTestRunner
    suite: unittest.TestSuite
    loader = unittest.TestLoader()
    suite = loader.discover("tests")
    runner = unittest.TextTestRunner(verbosity=2)
    return runner.run(suite)


if __name__ == "__main__":
    sys.exit(main())
