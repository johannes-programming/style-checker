.ONESHELL:
.PHONY: all add amend beautiful black build clean commit commit-version dist echo isort jacobus py311 py312 pypi rebase reset test toml_sorted upload version
SHELL := /bin/zsh

all: beautiful commit-version

add:
	git add -A;

amend: add
	git commit --amend --no-edit;

beautiful: isort black jacobus toml_sorted

black: py311
	conda run -n py311 pip install 'black>=24.5,<26' >/dev/null;
	conda run -n py311 black --line-length=79 . ;

build: py311
	conda run -n py311 pip install 'build>=1.3,<2' >/dev/null;
	conda run -n py311 python -m build;

commit: add
	git commit --allow-empty $(PARAMS);

commit-version: add py311
	conda run -n py311 pip install 'toml_get>=1.0,<2' >/dev/null;
	git commit --allow-empty "$$(conda run -n py311 python -m toml_get @make/toml_get.txt)";

clean:
	rm -fr 'dist/';
	rm -fr 'out/';

dist: beautiful clean build

echo:
	echo $(PARAMS);

isort: py311
	conda run -n py311 pip install 'isort>=6.0,<7' >/dev/null;
	conda run -n py311 isort . ;

jacobus: py311
	conda run -n py311 pip install 'jacobus>=2.3,<3' >/dev/null;
	conda run -n py311 python -m jacobus @make/jacobus.txt;
	conda run -n py311 python -m jacobus @make/jacobus_empty.txt;
	cat make/manifest.txt >> MANIFEST.in;
	conda run -n py311 python -m jacobus @make/jacobus_sort.txt;

py311:
	conda run -n base python make/env.py py311 --python=3.11;

py312:
	conda run -n base python make/env.py py312 --python=3.12;

pypi: dist upload

rebase:
	git rebase --empty=drop --interactive $(PARAMS);

reset:
	git reset HEAD~1

test: dist
	mkdir dist/out/ ;
	conda run -n base python make/env.py test_style_checker --python=3.11 --recreate >/dev/null;
	conda run -n test_style_checker pip install dist/*.tar.gz >/dev/null;
	conda run -n test_style_checker python run_tests.py > dist/out/tests_out.txt 2> dist/out/tests_err.txt || true;
	conda run -n test_style_checker pip install mypy >/dev/null;
	conda run -n test_style_checker python -m mypy --exclude build --exclude dist --exclude tests/examples --strict . > dist/out/mypy_dir_out.txt 2> dist/out/mypy_dir_err.txt || true;
	conda run -n test_style_checker python -m mypy --strict -p style_checker > dist/out/mypy_pkg_out.txt 2> dist/out/mypy_pkg_err.txt || true;
	conda run -n test_style_checker python -m style_checker "--exclude=tests/examples/**/*.py" -- "**/*.py" > dist/out/style_checker_out.txt 2> dist/out/style_checker_err.txt || true;
	zip -r dist/out.zip dist/out;

toml_sorted: py311
	conda run -n py311 pip install 'toml_sorted>=2.1,<3' >/dev/null;
	conda run -n py311 python -m toml_sorted @make/toml_sorted_pyproject.txt;
	conda run -n py311 python -m toml_sorted @make/toml_sorted_testdata.txt;

upload: py311
	conda run -n py311 pip install 'twine>=5.2,<7' >/dev/null;
	conda run -n py311 twine upload 'dist/*';

version: all pypi
