.ONESHELL:
.PHONY: all add amend beautiful black build canonicalize clean commit commit-version dist echo isort jacobus py311 py312 py313 py314 py315 pypi rebase reset test toml_sorted upload version
SHELL := /bin/zsh

all: beautiful commit-version

add:
	git add -A;

amend: add
	git commit --amend --no-edit;

beautiful: canonicalize isort black jacobus toml_sorted

black: py311
	conda run -n py311 pip install 'black>=24.5,<26' >/dev/null;
	conda run -n py311 black --line-length=79 . ;

build: beautiful py311
	conda run -n py311 pip install 'build>=1.3,<2' >/dev/null;
	conda run -n py311 python -m build;

canonicalize: py311
	conda run -n py311 pip install 'packaging<27,>=26.3';
	conda run -n py311 pip install 'tomli-w<2,>=1.2';
	conda run -n py311 python make/canonicalize.py -- . ;

clean:
	rm -fr 'dist/';
	rm -fr 'out/';

commit: add
	git commit --allow-empty $(PARAMS);

commit-version: add py311
	conda run -n py311 pip install 'toml-get<2,>=1.1' >/dev/null;
	git commit --allow-empty "$$(conda run -n py311 python -m toml_get @make/toml_get.txt)";

dist: beautiful clean build

echo:
	echo $(PARAMS);

isort: py311
	conda run -n py311 pip install 'isort<7,>=6.0' >/dev/null;
	conda run -n py311 isort . ;

jacobus: py311
	conda run -n py311 pip install 'jacobus<3,>=2.3' >/dev/null;
	conda run -n py311 python -m jacobus @make/jacobus.txt;
	conda run -n py311 python -m jacobus @make/jacobus_empty.txt;
	cat make/manifest.txt >> MANIFEST.in;
	conda run -n py311 python -m jacobus @make/jacobus_sort.txt;

py311:
	conda run -n base python make/env.py py311 --python=3.11;

py312:
	conda run -n base python make/env.py py312 --python=3.12;

py313:
	conda run -n base python make/env.py py313 --python=3.13;

py314:
	conda run -n base python make/env.py py314 --python=3.14;

py315:
	conda run -n base python make/env.py py315 --python=3.15;

pypi: dist upload

rebase:
	git rebase --empty=drop --interactive $(PARAMS);

reset:
	git reset HEAD~1

test: dist py311
	mkdir dist/out/ ;
	conda run -n py311 pip install 'style-checker<0.2,>=0.1.5';
	conda run -n py311 python -m style_checker --exclude 'tests/examples/**/*.py' -- '**/*.py' > dist/out/style_checker_out.txt 2> dist/out/style_checker_err.txt || true;
	conda run -n base python make/env.py test_style_checker_mypy --python=3.11 --recreate >/dev/null;
	conda run -n test_style_checker_mypy pip install dist/*.tar.gz >/dev/null;
	conda run -n test_style_checker_mypy python make/run_introspection.py > dist/out/introspection_out.txt 2> dist/out/introspection_err.txt || true;
	conda run -n test_style_checker_mypy pip install mypy >/dev/null;
	conda run -n test_style_checker_mypy python -m mypy --exclude build --exclude dist --exclude make --exclude tests/examples --strict . > dist/out/mypy_dir_out.txt 2> dist/out/mypy_dir_err.txt || true;
	conda run -n test_style_checker_mypy python -m mypy --strict -p style_checker > dist/out/mypy_pkg_out.txt 2> dist/out/mypy_pkg_err.txt || true;
	conda run -n py311 python -m mypy --strict make > dist/out/mypy_make_out.txt 2> dist/out/mypy_make_err.txt || true;
	conda run -n base python make/env.py test_style_checker_tests --python=3.11 --recreate >/dev/null;
	conda run -n test_style_checker_tests pip install dist/*.tar.gz >/dev/null;
	conda run -n test_style_checker_tests python run_tests.py > dist/out/tests_out.txt 2> dist/out/tests_err.txt || true;
	zip -r dist/out.zip dist/out;

toml_sorted: py311
	conda run -n py311 pip install 'toml-sorted<3,>=2.1' >/dev/null;
	conda run -n py311 python -m toml_sorted @make/toml_sorted_pyproject.txt;
	conda run -n py311 python -m toml_sorted @make/toml_sorted_testdata.txt;

upload: py311
	conda run -n py311 pip install 'twine>=5.2,<7' >/dev/null;
	conda run -n py311 twine upload 'dist/*';

version: all pypi
