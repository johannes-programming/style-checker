.ONESHELL:
.PHONY: all add amend beautiful beautiful-other beautiful-py beautiful-toml black build canonicalize clean commit commit-version dist echo isort jacobus jacobus-other jacobus-py jacobus-toml make-style-checker out py311 py312 py313 py314 py315 pypi pyproject-fmt rebase reset ruff test toml-sorted upload version
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

black: make-style-checker
	conda run -n make-style-checker pip install 'black<26,>=24.5' >/dev/null;
	conda run -n make-style-checker black --line-length=79 . ;

build: beautiful make-style-checker
	conda run -n make-style-checker pip install 'build<2,>=1.3' >/dev/null;
	conda run -n make-style-checker python -m build;

canonicalize: make-style-checker
	conda run -n make-style-checker pip install -e make/canonicalize;
	conda run -n make-style-checker python -m canonicalize -- .;

clean:
	rm -fr 'dist/';
	rm -fr 'out/';

commit: add
	git commit --allow-empty $(PARAMS);

commit-version: add make-style-checker
	conda run -n make-style-checker pip install 'toml-get<2,>=1.1' >/dev/null;
	git commit --allow-empty "$$(conda run -n make-style-checker python -m toml_get @make/toml-get.txt)";

dist: clean build

echo:
	echo $(PARAMS);

isort: make-style-checker
	conda run -n make-style-checker pip install 'isort<7,>=6.0' >/dev/null;
	conda run -n make-style-checker isort . ;

jacobus: jacobus-other jacobus-py jacobus-toml

jacobus-other: make-style-checker
	conda run -n make-style-checker pip install 'jacobus<3,>=2.5' >/dev/null;
	conda run -n make-style-checker python -m jacobus @make/jacobus-empty.txt;
	cat make/manifest.txt >> MANIFEST.in;
	conda run -n make-style-checker python -m jacobus @make/jacobus-sort.txt;
	conda run -n make-style-checker python -m jacobus @make/jacobus-other-indent.txt;

jacobus-py: make-style-checker
	conda run -n make-style-checker pip install 'jacobus<3,>=2.5' >/dev/null;
	conda run -n make-style-checker python -m jacobus @make/jacobus-py-indent.txt;
	conda run -n make-style-checker python -m jacobus @make/jacobus-py-examples.txt;

jacobus-toml: make-style-checker
	conda run -n make-style-checker pip install 'jacobus<3,>=2.5' >/dev/null;
	conda run -n make-style-checker python -m jacobus @make/jacobus-toml.txt;

make-style-checker:
	conda run -n base python make/env.py --python=3.11 -- make-style-checker;

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

pyproject-fmt: make-style-checker
	conda run -n make-style-checker pip install "pyproject-fmt<3,>=2.30";
	conda run -n make-style-checker pyproject-fmt pyproject.toml >/dev/null 2>/dev/null || conda run -n make-style-checker pyproject-fmt --check pyproject.toml;
	conda run -n make-style-checker pyproject-fmt make/canonicalize/pyproject.toml >/dev/null 2>/dev/null || conda run -n make-style-checker pyproject-fmt --check pyproject.toml;

rebase:
	git rebase --empty=drop --interactive $(PARAMS);

reset:
	git reset HEAD~1;

ruff: make-style-checker out
	conda run -n make-style-checker python -m pip install "ruff<1,>=0.14";
	conda run -n make-style-checker ruff check --fix . ;
	conda run -n make-style-checker ruff format . ;

test: dist make-style-checker out
	conda run -n make-style-checker pip install "style-checker<0.3,>=0.2.20";
	conda run -n make-style-checker python -m style_checker --exclude 'tests/examples/**/*.py' -- "**/*.py" > dist/out/style-out.txt 2> dist/out/style-err.txt || true;
	conda run -n base python make/env.py --python=3.11 --recreate -- mypy-style-checker >/dev/null;
	conda run -n mypy-style-checker pip install dist/*.tar.gz >/dev/null;
	conda run -n mypy-style-checker python run_introspection.py > dist/out/introspection-out.txt 2> dist/out/introspection-err.txt || true;
	conda run -n mypy-style-checker pip install "mypy<3,>=2.4" >/dev/null;
	conda run -n mypy-style-checker python -m mypy --strict -p style_checker > dist/out/mypy-pkg-out.txt 2> dist/out/mypy-pkg-err.txt || true;
	conda run -n mypy-style-checker python -m mypy --exclude build --exclude dist --exclude make --exclude tests/examples --strict . > dist/out/mypy-dir-out.txt 2> dist/out/mypy-dir-err.txt || true;
	conda run -n make-style-checker pip install "mypy<3,>=2.4" >/dev/null;
	conda run -n make-style-checker python -m mypy --strict -- make > dist/out/mypy-make-out.txt 2> dist/out/mypy-make-err.txt || true;
	conda run -n base python make/env.py --python=3.11 --recreate tests-style-checker >/dev/null;
	conda run -n tests-style-checker pip install dist/*.tar.gz >/dev/null;
	conda run -n tests-style-checker python run_tests.py > dist/out/tests-out.txt 2> dist/out/tests-err.txt || true;
	conda run -n base python make/env.py --python=3.11 --recreate self-style-checker >/dev/null;
	conda run -n self-style-checker pip install -e .;
	conda run -n self-style-checker python -m style_checker --exclude "tests/examples/**/*.py" -- "**/*.py" > dist/out/self-out.txt 2> dist/out/self-err.txt || true;
	zip -r dist/out.zip dist/out;

toml-sorted: make-style-checker
	conda run -n make-style-checker pip install 'toml-sorted<3,>=2.2' >/dev/null;
	conda run -n make-style-checker python -m toml_sorted -- '**/*.toml';
	conda run -n make-style-checker python -m toml_sorted @make/toml-sorted-pyproject.txt;
	conda run -n make-style-checker python -m toml_sorted @make/toml-sorted-testdata.txt;

upload: make-style-checker
	conda run -n make-style-checker pip install 'twine<7,>=5.2' >/dev/null;
	conda run -n make-style-checker twine upload 'dist/*';

version: all pypi
