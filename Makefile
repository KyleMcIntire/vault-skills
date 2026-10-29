VAULT ?= vault-template
PY ?= python3
SKILLS := plugins/vault-skills/skills

.PHONY: help check check-links test test-scripts test-skills lint privacy all

help:         ## list targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | sed 's/:.*##/ -/'

check:        ## structural checks on the vault (default: vault-template), read-only
	$(PY) scripts/check_vault.py --vault "$(VAULT)"

check-links:  ## same, but unresolved links fail the run
	$(PY) scripts/check_vault.py --vault "$(VAULT)" --strict-links

test-scripts: ## unit tests for scripts/ (banner tests skip without Pillow and numpy)
	$(PY) -m unittest discover -s scripts -p 'test_*.py'

test-skills:  ## unit tests that ship inside skills
	cd $(SKILLS)/learn-preferences && $(PY) -m unittest -q test_collect

test: test-scripts test-skills ## all unit tests

lint:         ## compile every Python file and syntax-check shell and JS
	find scripts $(SKILLS) -name '*.py' -not -path '*/fixtures/*' -print0 | xargs -0 $(PY) -m py_compile
	find scripts $(SKILLS) -name '*.sh' -print0 | xargs -0 -n1 sh -n
	sh scripts/dev/check_js.sh

privacy:      ## fail if a home-directory path or a real-looking secret slipped in
	@! grep -rnI -E '/Users/[a-z]|/home/[a-z]+/|C:\\\\Users\\\\|(ghp_|github_pat_|xox[bp]-|AKIA)[A-Za-z0-9]{12}' --exclude-dir=.git --exclude=Makefile . | grep -v 'collect.py\|test_collect.py'

all: lint test check-links privacy ## everything CI should run
