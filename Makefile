# udi-poly-notification — XML validation and PG3 release artifacts.
#
# PG3 release flow (clean tree; not detached HEAD):
#   1. Bump nodes/__init__.py NSVERSION (and any PG3 metadata you manage separately); commit.
#   2. `make release`     — tag v<NSVERSION> and push current branch + tag.
#   3. `make beta`        — push HEAD to the `beta` branch and build $(NAME)-beta-<NSVERSION>.zip.
#   4. `make production`  — push HEAD to the `production` branch and build $(NAME)-production-<NSVERSION>.zip.
# The track-specific zip files are the actual deliverables uploaded to PG3.

PYTHON ?= python3
NAME = Notification
GIT_REMOTE ?= origin
BRANCH_BETA ?= beta
BRANCH_PRODUCTION ?= production
XML_FILES = profile/*/*.xml
VERSION_FILE = nodes/__init__.py
VERSION_KEY = NSVERSION

# apt: sudo apt-get install libxml2-utils libxml2-dev
check: xml-check

xml-check:
	xmllint --noout $(XML_FILES)

help:
	@echo "Quality"
	@echo "  make check / xml-check   Validate profile XML"
	@echo ""
	@echo "PG3 release (clean tree; not detached HEAD)"
	@echo "  make release             Tag v\$$NSVERSION and push current branch + tag"
	@echo "  make beta                Push HEAD -> $(GIT_REMOTE)/$(BRANCH_BETA) and build $(NAME)-$(BRANCH_BETA)-\$$NSVERSION.zip"
	@echo "  make production          Push HEAD -> $(GIT_REMOTE)/$(BRANCH_PRODUCTION) and build $(NAME)-$(BRANCH_PRODUCTION)-\$$NSVERSION.zip"
	@echo "  make zip                 Ad-hoc local $(NAME).zip (no version suffix)"
	@echo "  make zip_free            Ad-hoc local $(NAME)_free.zip (no version suffix)"
	@echo ""
	@echo "Variables: PYTHON GIT_REMOTE BRANCH_BETA BRANCH_PRODUCTION"

clean:
	$(PYTHON) -c "import pathlib, shutil; r = pathlib.Path('.'); [shutil.rmtree(p, ignore_errors=True) for p in r.rglob('__pycache__') if p.is_dir()]; shutil.rmtree('.pytest_cache', ignore_errors=True)"
	rm -f $(NAME)*.zip zip_exclude_free_full.lst __init__.py

# Ad-hoc local archive (no version suffix). For PG3 uploads, prefer `make beta` / `make production`.
zip:
	rm -f $(NAME).zip
	zip -x@zip_exclude.lst -r $(NAME).zip *

zip_free:
	rm -f zip_exclude_free_full.lst $(NAME)_free.zip __init__.py
	cat zip_exclude.lst zip_exclude_free.lst > zip_exclude_free_full.lst
	cp nodes/__init__.py .
	egrep 'NSVERSION|UDMobile|Controller' __init__.py > nodes/__init__.py
	zip -x@zip_exclude_free_full.lst -r $(NAME)_free.zip *
	mv __init__.py nodes/

# Push current HEAD to $(GIT_REMOTE)/$(BRANCH_BETA) and build $(NAME)-$(BRANCH_BETA)-<NSVERSION>.zip
# for upload to PG3. Requires clean tree; not detached HEAD.
beta:
	@set -e; \
	ROOT=$$(pwd); \
	NSVERSION=$$(sed -n 's/^$(VERSION_KEY) = "\([^"]*\)"$$/\1/p' "$$ROOT/$(VERSION_FILE)"); \
	test -n "$$NSVERSION" || { echo "Could not parse $(VERSION_KEY) from $$ROOT/$(VERSION_FILE)"; exit 1; }; \
	test -z "$$(git -C "$$ROOT" status --porcelain)" || { \
		echo "Working tree is not clean. Commit or stash before make beta."; \
		git -C "$$ROOT" status --short; \
		exit 1; \
	}; \
	BRANCH=$$(git -C "$$ROOT" rev-parse --abbrev-ref HEAD); \
	if [ "$$BRANCH" = "HEAD" ]; then \
		echo "ERROR: detached HEAD. Checkout a branch, then run make beta."; \
		exit 1; \
	fi; \
	REPO=$$(git -C "$$ROOT" rev-parse --show-toplevel); \
	git -C "$$ROOT" push "$(GIT_REMOTE)" HEAD:"$(BRANCH_BETA)"; \
	echo "Repository: $$REPO"; \
	echo "Branch: $(BRANCH_BETA)"; \
	echo "Pushed $$(git -C "$$ROOT" rev-parse --short HEAD) to $(GIT_REMOTE)/$(BRANCH_BETA)."; \
	ZIPFILE="$(NAME)-$(BRANCH_BETA)-$$NSVERSION.zip"; \
	rm -f "$$ZIPFILE"; \
	zip -x@zip_exclude.lst -r "$$ZIPFILE" * >/dev/null; \
	echo "Built $$ROOT/$$ZIPFILE for upload to PG3."

# Push current HEAD to $(GIT_REMOTE)/$(BRANCH_PRODUCTION) and build $(NAME)-$(BRANCH_PRODUCTION)-<NSVERSION>.zip
# for upload to PG3. Requires clean tree; not detached HEAD.
production:
	@set -e; \
	ROOT=$$(pwd); \
	NSVERSION=$$(sed -n 's/^$(VERSION_KEY) = "\([^"]*\)"$$/\1/p' "$$ROOT/$(VERSION_FILE)"); \
	test -n "$$NSVERSION" || { echo "Could not parse $(VERSION_KEY) from $$ROOT/$(VERSION_FILE)"; exit 1; }; \
	test -z "$$(git -C "$$ROOT" status --porcelain)" || { \
		echo "Working tree is not clean. Commit or stash before make production."; \
		git -C "$$ROOT" status --short; \
		exit 1; \
	}; \
	BRANCH=$$(git -C "$$ROOT" rev-parse --abbrev-ref HEAD); \
	if [ "$$BRANCH" = "HEAD" ]; then \
		echo "ERROR: detached HEAD. Checkout a branch, then run make production."; \
		exit 1; \
	fi; \
	REPO=$$(git -C "$$ROOT" rev-parse --show-toplevel); \
	git -C "$$ROOT" push "$(GIT_REMOTE)" HEAD:"$(BRANCH_PRODUCTION)"; \
	echo "Repository: $$REPO"; \
	echo "Branch: $(BRANCH_PRODUCTION)"; \
	echo "Pushed $$(git -C "$$ROOT" rev-parse --short HEAD) to $(GIT_REMOTE)/$(BRANCH_PRODUCTION)."; \
	ZIPFILE="$(NAME)-$(BRANCH_PRODUCTION)-$$NSVERSION.zip"; \
	rm -f "$$ZIPFILE"; \
	zip -x@zip_exclude.lst -r "$$ZIPFILE" * >/dev/null; \
	echo "Built $$ROOT/$$ZIPFILE for upload to PG3."

# Tag the current HEAD as v<NSVERSION> and push the current branch + tag to $(GIT_REMOTE).
# NSVERSION = nodes/__init__.py NSVERSION (canonical). Track-specific zips are built by `make beta` / `make production`.
# Requires clean git working tree and a checked-out branch (not detached HEAD).
release:
	@set -e; \
	ROOT=$$(pwd); \
	NSVERSION=$$(sed -n 's/^$(VERSION_KEY) = "\([^"]*\)"$$/\1/p' "$$ROOT/$(VERSION_FILE)"); \
	test -n "$$NSVERSION" || { echo "Could not parse $(VERSION_KEY) from $$ROOT/$(VERSION_FILE)"; exit 1; }; \
	test -z "$$(git -C "$$ROOT" status --porcelain)" || { \
		echo "Working tree is not clean. Commit or stash before make release."; \
		git -C "$$ROOT" status --short; \
		exit 1; \
	}; \
	BRANCH=$$(git -C "$$ROOT" rev-parse --abbrev-ref HEAD); \
	if [ "$$BRANCH" = "HEAD" ]; then \
		echo "ERROR: detached HEAD. Checkout your release branch, then run make release."; \
		exit 1; \
	fi; \
	if git -C "$$ROOT" rev-parse -q --verify "refs/tags/v$$NSVERSION" >/dev/null 2>&1; then \
		echo "Tag v$$NSVERSION already exists. Delete: git -C \"$$ROOT\" tag -d v$$NSVERSION"; \
		exit 1; \
	fi; \
	git -C "$$ROOT" tag -a "v$$NSVERSION" -m "Release $$NSVERSION"; \
	echo "Created annotated tag v$$NSVERSION."; \
	git -C "$$ROOT" push "$(GIT_REMOTE)" "$$BRANCH" "v$$NSVERSION"; \
	echo "Pushed $$BRANCH and v$$NSVERSION to $(GIT_REMOTE)."

.PHONY: check xml-check help clean zip zip_free beta production release
