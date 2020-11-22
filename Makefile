# Makefile for ckanext-blob-storage

PACKAGE_DIR := ckanext/blob_storage
PACKAGE_NAME := ckanext.blob_storage

SHELL := bash
PYTHON := python
PIP := pip
PIP_COMPILE := pip-compile
PYTEST := pytest
PASTER := paster
DOCKER_COMPOSE := docker-compose
PSQL := psql
GIT := git

# Find GNU sed in path (on OS X gsed should be preferred)
SED := $(shell which gsed sed | head -n1)

# The `ckan` command line only exists in newer versions of CKAN
CKAN_CLI := $(shell which ckan | head -n1)

TEST_INI_PATH := ./test.ini
SENTINELS := .make-status

PYTHON_VERSION := $(shell $(PYTHON) -c 'import sys; print(sys.version_info[0])')

PACKAGE_TAG_PREFIX := "v"
PACKAGE_TAG_SUFFIX := ""
PACKAGE_VERSION := $(shell $(PYTHON) -c 'import $(PACKAGE_NAME) as p; print(p.__version__)')

# CKAN environment variables
CKAN_PATH := ckan
CKAN_REPO_URL := https://github.com/ckan/ckan.git
CKAN_VERSION := ckan-2.8.3
CKAN_CONFIG_FILE := $(CKAN_PATH)/development.ini
CKAN_SITE_URL := http://localhost:5000
POSTGRES_USER := ckan
POSTGRES_PASSWORD := ckan
POSTGRES_DB := ckan
POSTGRES_HOST := 127.0.0.1
CKAN_SOLR_PASSWORD := ckan
DATASTORE_DB_NAME := datastore
DATASTORE_DB_RO_USER := datastore_ro
DATASTORE_DB_RO_PASSWORD := datastore_ro
CKAN_LOAD_PLUGINS := stats text_view image_view recline_view datastore authz_service blob_storage

CKAN_CONFIG_VALUES := \
		ckan.site_url=$(CKAN_SITE_URL) \
		sqlalchemy.url=postgresql://$(POSTGRES_USER):$(POSTGRES_PASSWORD)@$(POSTGRES_HOST)/$(POSTGRES_DB) \
		ckan.datastore.write_url=postgresql://$(POSTGRES_USER):$(POSTGRES_PASSWORD)@$(POSTGRES_HOST)/$(DATASTORE_DB_NAME) \
		ckan.datastore.read_url=postgresql://$(DATASTORE_DB_RO_USER):$(DATASTORE_DB_RO_PASSWORD)@$(POSTGRES_HOST)/$(DATASTORE_DB_NAME) \
		ckan.plugins='$(CKAN_LOAD_PLUGINS)' \
		ckan.storage_path='%(here)s/storage' \
		solr_url=http://127.0.0.1:8983/solr/ckan \
		ckanext.blob_storage.storage_service_url=http://localhost:9419 \
		ckanext.external_storage.storage_namespace=my-ckan-ns \
		ckanext.authz_service.jwt_algorithm=HS256 \
		ckanext.authz_service.jwt_private_key=this-is-a-test-only-key \
		ckanext.authz_service.jwt_include_user_email=true

CKAN_TEST_CONFIG_VALUES := \
		sqlalchemy.url=postgresql://$(POSTGRES_USER):$(POSTGRES_PASSWORD)@$(POSTGRES_HOST)/$(POSTGRES_DB)_test \
		ckan.datastore.write_url=postgresql://$(POSTGRES_USER):$(POSTGRES_PASSWORD)@$(POSTGRES_HOST)/$(DATASTORE_DB_NAME)_test \
		ckan.datastore.read_url=postgresql://$(DATASTORE_DB_RO_USER):$(DATASTORE_DB_RO_PASSWORD)@$(POSTGRES_HOST)/$(DATASTORE_DB_NAME)_test

ifdef WITH_COVERAGE
  COVERAGE_ARG := --cov=$(PACKAGE_NAME)
else
  COVERAGE_ARG :=
endif


dev-requirements.%.txt: dev-requirements.in
	$(PIP_COMPILE) --no-index dev-requirements.in -o $@

requirements.%.txt: requirements.in
	$(PIP_COMPILE) --no-index requirements.in -o $@

## Update requirements files for the current Python version
requirements: $(SENTINELS)/requirements
.PHONEY: requirements

## Install this extension to the current Python environment
install: $(SENTINELS)/install
.PHONY: install

## Set up the extension for development in the current Python environment
develop: $(SENTINELS)/develop
.PHONEY: develop

## Run all tests
test: $(SENTINELS)/tests-passed
.PHONY: test

## Install the right version of CKAN into the virtual environment
ckan-install: $(SENTINELS)/ckan-installed
	@echo "Current CKAN version: $(shell cat $(SENTINELS)/ckan-version)"
.PHONY: ckan-install

## Run CKAN in the local virtual environment
ckan-start: $(SENTINELS)/ckan-installed $(SENTINELS)/install-dev $(CKAN_CONFIG_FILE) | _check_virtualenv
ifdef CKAN_CLI
	$(CKAN_CLI) -c $(CKAN_CONFIG_FILE) db init
	$(CKAN_CLI) -c $(CKAN_CONFIG_FILE) server -r
else
	$(PASTER) --plugin=ckan db init -c $(CKAN_CONFIG_FILE)
	$(PASTER) --plugin=ckan serve --reload --monitor-restart $(CKAN_CONFIG_FILE)
endif
.PHONY: ckan-start

## Create a version tag
version-tag:
	@echo "Creating tag: $(PACKAGE_TAG_PREFIX)$(PACKAGE_VERSION)$(PACKAGE_TAG_SUFFIX)"
	$(GIT) tag "$(PACKAGE_TAG_PREFIX)$(PACKAGE_VERSION)$(PACKAGE_TAG_SUFFIX)"
	$(GIT) push --tags
.PHONY: version-tag

$(CKAN_PATH):
	$(GIT) clone $(CKAN_REPO_URL) $@

$(CKAN_CONFIG_FILE): $(SENTINELS)/ckan-installed $(SENTINELS)/develop | _check_virtualenv
	$(PASTER) make-config --no-interactive ckan $(CKAN_CONFIG_FILE)
ifdef CKAN_CLI
	$(CKAN_CLI) config-tool $(CKAN_CONFIG_FILE) -s DEFAULT debug=true
	$(CKAN_CLI) config-tool $(CKAN_CONFIG_FILE) $(CKAN_CONFIG_VALUES)
else
	$(PASTER) --plugin=ckan config-tool $(CKAN_CONFIG_FILE) -s DEFAULT debug=true
	$(PASTER) --plugin=ckan config-tool $(CKAN_CONFIG_FILE) $(CKAN_CONFIG_VALUES)
endif

.env:
	@___POSTGRES_USER=$(POSTGRES_USER) \
	___POSTGRES_PASSWORD=$(POSTGRES_PASSWORD) \
	___POSTGRES_DB=$(POSTGRES_DB) \
	___CKAN_SOLR_PASSWORD=$(CKAN_SOLR_PASSWORD) \
	___DATASTORE_DB_NAME=$(DATASTORE_DB_NAME) \
	___DATASTORE_DB_USER=$(POSTGRES_USER) \
	___DATASTORE_DB_RO_USER=$(DATASTORE_DB_RO_USER) \
	___DATASTORE_DB_RO_PASSWORD=$(DATASTORE_DB_RO_PASSWORD) \
	env | grep ^___ | $(SED) 's/^___//' > .env
	@cat .env

## Create the database for test running
create-test-db:
	@echo " \
    	CREATE ROLE $(DATASTORE_DB_RO_USER) NOSUPERUSER NOCREATEDB NOCREATEROLE LOGIN PASSWORD '$(DATASTORE_DB_RO_PASSWORD)'; \
    	CREATE DATABASE $(DATASTORE_DB_NAME)_test OWNER $(POSTGRES_USER) ENCODING 'utf-8'; \
    	CREATE DATABASE $(POSTGRES_DB)_test OWNER $(POSTGRES_USER) ENCODING 'utf-8'; \
    	GRANT ALL PRIVILEGES ON DATABASE $(DATASTORE_DB_NAME)_test TO $(POSTGRES_USER);  \
    	GRANT ALL PRIVILEGES ON DATABASE $(POSTGRES_DB)_test TO $(POSTGRES_USER);  \
    " | PGPASSWORD=$(POSTGRES_PASSWORD) $(PSQL) -h $(POSTGRES_HOST) --username "$(POSTGRES_USER)"
.PHONY: create-test-db

## Start all Docker services
docker-up: .env
	$(DOCKER_COMPOSE) up -d
	@until $(DOCKER_COMPOSE) exec db pg_isready -U $(POSTGRES_USER); do sleep 1; done
	@sleep 2
	@echo " \
    	CREATE ROLE $(DATASTORE_DB_RO_USER) NOSUPERUSER NOCREATEDB NOCREATEROLE LOGIN PASSWORD '$(DATASTORE_DB_RO_PASSWORD)'; \
    	CREATE DATABASE $(DATASTORE_DB_NAME) OWNER $(POSTGRES_USER) ENCODING 'utf-8'; \
    	CREATE DATABASE $(DATASTORE_DB_NAME)_test OWNER $(POSTGRES_USER) ENCODING 'utf-8'; \
    	CREATE DATABASE $(POSTGRES_DB)_test OWNER $(POSTGRES_USER) ENCODING 'utf-8'; \
    	GRANT ALL PRIVILEGES ON DATABASE $(DATASTORE_DB_NAME) TO $(POSTGRES_USER);  \
    	GRANT ALL PRIVILEGES ON DATABASE $(DATASTORE_DB_NAME)_test TO $(POSTGRES_USER);  \
    	GRANT ALL PRIVILEGES ON DATABASE $(POSTGRES_DB)_test TO $(POSTGRES_USER);  \
    " | $(DOCKER_COMPOSE) exec -T db psql --username "$(POSTGRES_USER)"
.PHONY: docker-up

## Stop all Docker services
docker-down: .env
	$(DOCKER_COMPOSE) down
.PHONY: docker-down

## Initialize the development environment
dev-setup: _check_virtualenv $(SENTINELS)/ckan-installed $(CKAN_PATH)/who.ini $(CKAN_CONFIG_FILE) $(SENTINELS)/develop
.PHONY: setup

## Start a full development environment
dev-start: dev-setup docker-up ckan-start
.PHONY: start-dev

# Private targets

_check_virtualenv:
	@if [ -z "$(VIRTUAL_ENV)" ]; then \
	  echo "You are not in a virtual environment - activate your virtual environment first"; \
	  exit 1; \
	fi
.PHONY: _check_virtualenv

$(SENTINELS):
	mkdir -p $@

$(SENTINELS)/ckan-version: $(CKAN_PATH) | _check_virtualenv $(SENTINELS)
	$(GIT) -C $(CKAN_PATH) remote update
	$(GIT) -C $(CKAN_PATH) checkout $(CKAN_VERSION)
	if [ -e $(CKAN_PATH)/requirement-setuptools.txt ]; then $(PIP) install -r $(CKAN_PATH)/requirement-setuptools.txt; fi
	if [[ "$(PYTHON_VERSION)" == "2" && -e $(CKAN_PATH)/requirements-py2.txt ]]; then \
	  $(PIP) install -r $(CKAN_PATH)/requirements-py2.txt; \
	else \
	  $(PIP) install -r $(CKAN_PATH)/requirements.txt; \
	fi
	$(PIP) install -r $(CKAN_PATH)/dev-requirements.txt
	$(PIP) install -e $(CKAN_PATH)
	echo "$(CKAN_VERSION)" > $@

$(SENTINELS)/ckan-installed: $(SENTINELS)/ckan-version | $(SENTINELS)
	@if [ "$(shell cat $(SENTINELS)/ckan-version)" != "$(CKAN_VERSION)" ]; then \
	  echo "Switching to CKAN $(CKAN_VERSION)"; \
	  rm $(SENTINELS)/ckan-version; \
	  $(MAKE) $(SENTINELS)/ckan-version; \
	fi
	@touch $@

$(SENTINELS)/test.ini: $(TEST_INI_PATH) $(CKAN_PATH) $(CKAN_PATH)/test-core.ini | $(SENTINELS)
	$(SED) "s@use = config:.*@use = config:$(CKAN_PATH)/test-core.ini@" -i $(TEST_INI_PATH)
ifdef CKAN_CLI
	$(CKAN_CLI) config-tool $(CKAN_PATH)/test-core.ini $(CKAN_CONFIG_VALUES) $(CKAN_TEST_CONFIG_VALUES)
else
	$(PASTER) --plugin=ckan config-tool $(CKAN_PATH)/test-core.ini $(CKAN_CONFIG_VALUES) $(CKAN_TEST_CONFIG_VALUES)
endif
	@touch $@

$(SENTINELS)/requirements: requirements.py$(PYTHON_VERSION).txt dev-requirements.py$(PYTHON_VERSION).txt | $(SENTINELS)
	@touch $@

$(SENTINELS)/install: requirements.py$(PYTHON_VERSION).txt | $(SENTINELS)
	$(PIP) install -r requirements.py$(PYTHON_VERSION).txt
	@touch $@

$(SENTINELS)/install-dev: requirements.py$(PYTHON_VERSION).txt | $(SENTINELS)
	$(PIP) install -r dev-requirements.py$(PYTHON_VERSION).txt
	$(PIP) install -e .
	@touch $@

$(SENTINELS)/develop: $(SENTINELS)/requirements $(SENTINELS)/install $(SENTINELS)/install-dev setup.py | $(SENTINELS)
	@touch $@

$(SENTINELS)/test-setup: $(SENTINELS)/develop $(SENTINELS)/test.ini
ifdef CKAN_CLI
	$(CKAN_CLI) -c $(TEST_INI_PATH) db init
else
	$(PASTER) --plugin=ckan db init -c $(TEST_INI_PATH)
endif
	@touch $@

$(SENTINELS)/tests-passed: $(SENTINELS)/test-setup $(shell find $(PACKAGE_DIR) -type f) .flake8 .isort.cfg | $(SENTINELS)
	$(PYTEST) $(COVERAGE_ARG) \
		--flake8 \
		--isort \
		--ckan-ini=$(TEST_INI_PATH) \
		--doctest-modules \
		--ignore $(PACKAGE_DIR)/cli.py  \
		$(PACKAGE_DIR)
	@touch $@

# Help related variables and targets

GREEN  := $(shell tput -Txterm setaf 2)
YELLOW := $(shell tput -Txterm setaf 3)
WHITE  := $(shell tput -Txterm setaf 7)
RESET  := $(shell tput -Txterm sgr0)
TARGET_MAX_CHAR_NUM := 15

## Show help
help:
	@echo ''
	@echo 'Usage:'
	@echo '  ${YELLOW}make${RESET} ${GREEN}<target>${RESET}'
	@echo ''
	@echo 'Targets:'
	@awk '/^[a-zA-Z\-\_0-9]+:/ { \
	  helpMessage = match(lastLine, /^## (.*)/); \
	  if (helpMessage) { \
	    helpCommand = substr($$1, 0, index($$1, ":")-1); \
	    helpMessage = substr(lastLine, RSTART + 3, RLENGTH); \
	    printf "  ${YELLOW}%-$(TARGET_MAX_CHAR_NUM)s${RESET} ${GREEN}%s${RESET}\n", helpCommand, helpMessage; \
	  } \
	} \
	{ lastLine = $$0 }' $(MAKEFILE_LIST)
