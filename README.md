ckanext-blob-storage
========================
[![Build Status](https://travis-ci.org/datopian/ckanext-blob-storage.svg?branch=master)](https://travis-ci.org/datopian/ckanext-blob-storage)
[![Coverage Status](https://coveralls.io/repos/github/datopian/ckanext-blob-storage/badge.svg?branch=master)](https://coveralls.io/github/datopian/ckanext-blob-storage?branch=master)

**Move CKAN resource storage management to an external micro-service**

`ckanext-blob-storage` replace's CKAN's default local blob storage functionality with pluggable storage layer supporting cloud and local. It supports direct to cloud file uploading following the design in https://tech.datopian.com/blob-storage/#ckan-v3

The design is pluggable so one can use all the major storage backends as well as local, cloud based (e.g. S3, Azure Blobs, GCP, etc.) or any other storage. In addition, the service allows clients (typically browsers) to upload and download files directly to storage without passing them through CKAN, which can greatly improve file access efficiency.

Authentication and authorization to the blob storage management service is done via JWT tokens provided by
[`ckanext-authz-service`](https://github.com/datopian/ckanext-authz-service).

Internally, the blob storage management service is in fact a Git LFS server
implementation, which means access via 3rd party Git based tools is also
potentially possible.

Requirements
------------
* This extension works with CKAN 2.8.x. It may work, but has not been tested,
with other CKAN versions.
* `ckanext-authz-service` must be installed and enabled
* A working and configured Git LFS server accessible to the browser. We
recommend usign [Giftless](https://github.com/datopian/giftless) but other
implementations may be configured to work as well.

Installation
------------

To install ckanext-blob-storage:

1. Activate your CKAN virtual environment, for example:
```
. /usr/lib/ckan/default/bin/activate
```

2. Install the ckanext-blob-storage Python package into your virtual environment:
```
pip install ckanext-blob-storage
```

3. Add `blob_storage` to the `ckan.plugins` setting in your CKAN
   config file (by default the config file is located at
   `/etc/ckan/default/production.ini`).

4. Restart CKAN. For example if you've deployed CKAN with Apache on Ubuntu:
```
sudo service apache2 reload
```

Configuration settings
----------------------

`ckanext.blob_storage.storage_service_url = 'https://...'`

Set the URL of the blob storage microservice (the Git LFS server). This
must be a URL accessible to browsers connecting to the service.

`ckanext.blob_storage.storage_namespace = my-ckan-instance`

Set the in-storage namespace used for this CKAN instance. This is useful if
multiple CKAN instances are using the same storage microservice instance, and
you need to seperate permission scopes between them. 

If not specified, `ckan` will be used as the default namespace.

Developer installation
----------------------

To install `ckanext-blob-storage` for development, do the following:

1. Pull the project code from Github
```
git clone https://github.com/datopian/ckanext-blob-storage.git
cd ckanext-blob-storage
```
2. Create a Python 2.7 virtual environment (The flag `-p py27` is used to ensure that you are using the right Python version when create the virtualenv).
```
virtualenv .venv27 -p py27
source .venv27/bin/activate
```

3. Run the following command to bootstrap the entire environment
```
make dev-start
```

This will pull and install CKAN and all it's dependencies into your virtual
environment, create all necessary configuration files, launch external services
using Docker Compose and start the CKAN development server.

You can create an user using the web interface at [`localhost:5000`](http://localhost:5000/) but the user will not be an _admin_ with permissions to create organizations or datasets. If you need to turn your user in an _admin_, make sure the virtual environment is still active and use this command, replacing the `<USERNAME>` with the user name you created:

```
paster --plugin=ckan sysadmin -c ckan/development.ini add <USERNAME>
```

You can repeat the last command at any time to start developing again.

Type `make help` to get a like of user commands useful to managing the local
environment.

Update DataPub (resource editor) app
------------------------------------

1. Init submodule for the resource editor app
```
git submodule init
git submodule update
```

2. Build the resource editor app
```
cd datapub
yarn
yarn build
```

3. Replace bundles in `fanstatic` directory
```
rm ckanext/blob_storage/fanstatic/js/*
cp datapub/build/static/js/*.js ckanext/blob_storage/fanstatic/js/
```

If you also want to re-use stylesheets:

```
rm ckanext/blob_storage/fanstatic/css/*
cp datapub/build/static/css/*.css ckanext/blob_storage/fanstatic/css/
```

4. Now, make sure to update the resources in `templates/blob_storage/snippets/upload_module.html`

```
{% resource 'blob-storage/css/main.{hash}.chunk.css' %}

{% resource 'blob-storage/js/runtime-main.{hash}.js' %}
{% resource 'blob-storage/js/2.{hash}.chunk.js' %}
{% resource 'blob-storage/js/main.{hash}.chunk.js' %}
```

Installing with Docker
----------------------

Unlike other CKAN extensions, blob storage needs node modules to be installed
and build in order to work properly. You will need to install node and npm.
Below is how your Dockerfile might look like

```
RUN apt-get -q -y install \
        python-pip \
        curl \
        git-core

RUN curl -sL https://deb.nodesource.com/setup_14.x | bash - && apt-get install nodejs && npm version

# Install ckanext-blob-storage
RUN git clone --branch ${CKANEXT_BLOB_STORAGE_VERSION} https://github.com/datopian/ckanext-blob-storage
RUN pip install --no-cache-dir -r "ckanext-blob-storage/requirements.py2.txt"
RUN pip install -e ckanext-blob-storage

# Install other extensions
...
```

__NOTE:__ We assume that you have Giftless server running with configuration as
in [giftless.yaml][giftless] and nginx is configured as in [nginx.conf][nginx]



### Working with `requirements.txt` files

#### tl;dr

* You *do not* touch `*requirements.*.txt` files directly. We use
[`pip-tools`][1] and custom `make` targets to manage these files.
* Use `make develop` to install the right development time requirements into your
current virtual environment
* Use `make install` to install the right runtime requirements into your current
virtual environment
* To add requirements, edit `requirements.in` or `dev-requirements.in` and run
`make requirements`. This will recompile the requirements file(s) **for your
current Python version**. You may need to do this for the other Python version
by switching to a different Python virtual environment before committing your
changes.

#### More background
This project manages requirements in a relatively complex way, in order to
seamlessly support Python 2.7 and 3.x.

For this reason, you will see 4 requirements files in the project root:

* `requirements.py2.txt` - Python 2 runtime requirements
* `requirements.py3.txt` - Python 3 runtime requirements
* `dev-requirements.py2.txt` - Python 2 development requirements
* `dev-requirements.py3.txt` - Python 3 development requirements

These are generated using the `pip-compile` command (a part of `pip-tools`)
from the corresponding `requirements.in` and `dev-requirements.in` files.

To understand why `pip-compile` is used, read the `pip-tools` manual. In
short, this allows us to pin dependencies of dependencies, thus resolving
potential deployment conflicts, without the headache of managing the specific
version of each Nth-level dependency.

In order to support both Python 2.7 and 3.x, which tend to require slightly
different dependencies, we use `requirements.in` files to generate
major-version specific requirements files. These, in turn, should be used
when installing the package.

In order to simplify things, the `make` targets specified above will automate
the process *for the current Python version*.

#### Adding Requirements

Requirements are managed in `.in` files - these are the only files that
should be edited directly.

Take care to specify a version for each requirement, to the level required
to maintain future compatibility, but not to specify an *exact* version
unless necessary.

For example, the following are good `requirements.in` lines:

    pyjwt[crypto]==1.7.*
    pyyaml==5.*
    pytz

This allows these packages to be upgraded to a minor version, without the risk
of breaking compatibility.

Note that `pytz` is specified with no version on purpose, as we want it updated
to the latest possible version on each new rebuild.

Developers wanting to add new requirements (runtime or development time),
should take special care to update the `requirements.txt` files for all
supported Python versions by running `make requirements` on different
virtual environment, after updating the relevant `.in` file.

#### Applying Patch-level upgrades to requirements

You can delete `*requirements.*.txt` and run `make requirements`.

TODO: we can probably do this in a better way - create a `make` target
for this.  


Tests
-----

To run the tests, do:

    make test

To run the tests and produce a coverage report, first make sure you have
coverage installed in your virtualenv (``pip install coverage``) then run:

    make coverage

Releasing a new version of ckanext-blob-storage
------------------------------------------------

ckanext-blob-storage should be available on PyPI as https://pypi.org/project/ckanext-blob-storage.
To publish a new version to PyPI follow these steps:

1. Update the version number in the `setup.py` file.
   See [PEP 440](http://legacy.python.org/dev/peps/pep-0440/#public-version-identifiers)
   for how to choose version numbers.

2. Make sure you have the latest version of necessary packages:
```
    pip install --upgrade setuptools wheel twine
```

3. Create a source and binary distributions of the new version:
```
    python setup.py sdist bdist_wheel && twine check dist/*
```

   Fix any errors you get.

4. Upload the source distribution to PyPI:
```
    twine upload dist/*
```

5. Commit any outstanding changes:
```
    git commit -a
```

6. Tag the new release of the project on GitHub with the version number from
   the ``setup.py`` file. For example if the version number in ``setup.py`` is
   0.0.1 then do:
```
    git tag 0.0.1
    git push --tags
```


[1]: https://pypi.org/project/pip-tools/
[giftless]: docker/giftless.yaml
[nginx]: docker/nginx.conf