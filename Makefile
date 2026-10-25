.ONESHELL:
.PHONY: all add amend beautiful beautiful-other beautiful-py beautiful-toml black build canonicalize clean commit commit-version dist echo isort jacobus jacobus-other jacobus-py jacobus-toml make_style_checker out py311 py312 py313 py314 py315 pypi pyproject-fmt rebase reset ruff test toml-sorted upload version
SHELL := /bin/zsh

all: beautiful commit-version

add:
	git add -A;

amend: add
	git commit --amend --no-edit;

beautiful: beautiful-other beautiful-py beautiful-toml

beautiful-other: jacobus-other

beautiful-py: jacobus-py ruff

beautiful-toml: canonicalize toml-sorted pyproject-fmt

black: make_style_checker
	conda run -n make_style_checker pip install 'black>=24.5,<26' >/dev/null;
	conda run -n make_style_checker black --line-length=79 . ;

build: beautiful make_style_checker
	conda run -n make_style_checker pip install 'build>=1.3,<2' >/dev/null;
	conda run -n make_style_checker python -m build;

canonicalize: make_style_checker
	conda run -n make_style_checker pip install -e make/canonicalize;
	conda run -n make_style_checker python -m canonicalize -- .;

clean:
	rm -fr 'dist/';
	rm -fr 'out/';

commit: add
	git commit --allow-empty $(PARAMS);

commit-version: add make_style_checker
	conda run -n make_style_checker pip install 'toml-get<2,>=1.1' >/dev/null;
	git commit --allow-empty "$$(conda run -n make_style_checker python -m toml_get @make/toml_get.txt)";

dist: clean build

echo:
	echo $(PARAMS);

isort: make_style_checker
	conda run -n make_style_checker pip install 'isort<7,>=6.0' >/dev/null;
	conda run -n make_style_checker isort . ;

jacobus: jacobus-other jacobus-py jacobus-toml make_style_checker

jacobus-other: make_style_checker
	conda run -n make_style_checker pip install 'jacobus>=2.5,<3' >/dev/null;
	conda run -n make_style_checker python -m jacobus @make/jacobus_empty.txt;
	cat make/manifest.txt >> MANIFEST.in;
	conda run -n make_style_checker python -m jacobus @make/jacobus_sort.txt;
	conda run -n make_style_checker python -m jacobus @make/jacobus_other_indent.txt;

jacobus-py: make_style_checker
	conda run -n make_style_checker pip install 'jacobus>=2.5,<3' >/dev/null;
	conda run -n make_style_checker python -m jacobus @make/jacobus_py_indent.txt;
	conda run -n make_style_checker python -m jacobus @make/jacobus_py_examples.txt;

jacobus-toml: make_style_checker
	conda run -n make_style_checker pip install 'jacobus>=2.5,<3' >/dev/null;
	conda run -n make_style_checker python -m jacobus @make/jacobus_toml.txt;

make_style_checker:
	conda run -n base python make/env.py --python=3.11 -- make_style_checker;

out:
	mkdir -p dist/out/;

py311:
	conda run -n base python make/env.py --python=3.11 -- py311;

py312:
	conda run -n base python make/env.py --python=3.12 -- py312;

py313:
	conda run -n base python make/env.py --python=3.13 -- py313;

py314:
	conda run -n base python make/env.py --python=3.14 -- py314;

py315:
	conda run -n base python make/env.py --python=3.15 -- py315;

pypi: dist upload

pyproject-fmt: make_style_checker
	conda run -n make_style_checker pip install "pyproject-fmt<3,>=2.30";
	conda run -n make_style_checker pyproject-fmt pyproject.toml >/dev/null 2>/dev/null || conda run -n make_style_checker pyproject-fmt --check pyproject.toml;

rebase:
	git rebase --empty=drop --interactive $(PARAMS);

reset:
	git reset HEAD~1;

ruff: make_style_checker out
	conda run -n make_style_checker python -m pip install "ruff>=0.14,<1";
	conda run -n make_style_checker ruff check --fix . ;
	conda run -n make_style_checker ruff format . ;

test: dist make_style_checker out
	conda run -n make_style_checker pip install "style-checker<0.2,>=0.1.13";
	conda run -n make_style_checker python -m style_checker --exclude "tests/examples/**/*.py" -- "**/*.py" > dist/out/style_checker_out.txt 2> dist/out/style_checker_err.txt || true;
	conda run -n base python make/env.py --python=3.11 --recreate test_style_checker_mypy >/dev/null;
	conda run -n test_style_checker_mypy pip install dist/*.tar.gz >/dev/null;
	conda run -n test_style_checker_mypy python run_introspection.py > dist/out/introspection_out.txt 2> dist/out/introspection_err.txt || true;
	conda run -n test_style_checker_mypy pip install "mypy<3,>=2.4" >/dev/null;
	conda run -n test_style_checker_mypy python -m mypy --strict -p style_checker > dist/out/mypy_pkg_out.txt 2> dist/out/mypy_pkg_err.txt || true;
	conda run -n make_style_checker pip install "mypy<3,>=2.4" >/dev/null;
	conda run -n make_style_checker python -m mypy --exclude build --exclude dist --exclude make --exclude tests/examples --strict . > dist/out/mypy_dir_out.txt 2> dist/out/mypy_dir_err.txt || true;
	conda run -n make_style_checker pip install "mypy<3,>=2.4";
	conda run -n make_style_checker python -m mypy --strict make > dist/out/mypy_make_out.txt 2> dist/out/mypy_make_err.txt || true;
	conda run -n base python make/env.py --python=3.11 --recreate test_style_checker_tests >/dev/null;
	conda run -n test_style_checker_tests pip install dist/*.tar.gz >/dev/null;
	conda run -n test_style_checker_tests python run_tests.py > dist/out/tests_out.txt 2> dist/out/tests_err.txt || true;
	conda run -n base python make/env.py --python=3.11 --recreate test_style_checker_self >/dev/null;
	conda run -n test_style_checker_self pip install -e .;
	conda run -n test_style_checker_self python -m style_checker --exclude "tests/examples/**/*.py" -- "**/*.py" > dist/out/self_out.txt 2> dist/out/self_err.txt || true;
	zip -r dist/out.zip dist/out;

toml-sorted: make_style_checker
	conda run -n make_style_checker pip install 'toml-sorted>=2.2,<3' >/dev/null;
	conda run -n make_style_checker python -m toml_sorted '**/*.toml';
	conda run -n make_style_checker python -m toml_sorted @make/toml_sorted_pyproject.txt;
	conda run -n make_style_checker python -m toml_sorted @make/toml_sorted_testdata.txt;

upload: make_style_checker
	conda run -n make_style_checker pip install 'twine>=5.2,<7' >/dev/null;
	conda run -n make_style_checker twine upload 'dist/*';

version: all pypi
