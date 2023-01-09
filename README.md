## Testcases structure

Tests written with PyTest Framework are located under `pytest_tests/testsuites` directory.

These tests rely on resources and utility modules that have been originally developed for Robot Framework:

`robot/resources/files` - static files that are used in tests' commands.

`robot/resources/lib/` - common Python libraries that provide utility functions used as building blocks in tests.

`robot/variables/` - constants and configuration variables for tests.

## Testcases execution

### Initial preparation

1. Install frostfs-cli
    - `git clone git@github.com:nspcc-dev/frostfs-node.git`
    - `cd frostfs-node`
    - `make`
    - `sudo cp bin/frostfs-cli /usr/local/bin/frostfs-cli`

2. Install frostfs-authmate
    - `git clone git@github.com:nspcc-dev/frostfs-s3-gw.git`
    - `cd frostfs-s3-gw`
    - `make`
    - `sudo cp bin/frostfs-authmate /usr/local/bin/frostfs-authmate`

3. Install neo-go
    - `git clone git@github.com:nspcc-dev/neo-go.git`
    - `cd neo-go`
    - `git checkout v0.92.0` (or the current version in the frostfs-dev-env)
    - `make`
    - `sudo cp bin/neo-go /usr/local/bin/neo-go`
    or download binary from releases: https://github.com/nspcc-dev/neo-go/releases

4. Clone frostfs-dev-env
`git clone git@github.com:nspcc-dev/frostfs-dev-env.git`

Note that we expect frostfs-dev-env to be located under
the `<testcases_root_dir>/../frostfs-dev-env` directory. If you put this repo in any other place,
manually set the full path to frostfs-dev-env in the environment variable `DEVENV_PATH` at this step.

5. Make sure you have installed all of the following prerequisites on your machine

```
make
python3.9
python3.9-dev
libssl-dev
```
As we use frostfs-dev-env, you'll also need to install
[prerequisites](https://github.com/nspcc-dev/frostfs-dev-env#prerequisites) of this repository.

6. Prepare virtualenv

```shell
$ make venv.local-pytest
$ . venv.local-pytest/bin/activate
```

7. Setup pre-commit hooks to run code formatters on staged files before you run a `git commit` command:

```shell
$ pre-commit install
```

Optionally you might want to integrate code formatters with your code editor to apply formatters to code files as you go:
* isort is supported by [PyCharm](https://plugins.jetbrains.com/plugin/15434-isortconnect), [VS Code](https://cereblanco.medium.com/setup-black-and-isort-in-vscode-514804590bf9). Plugins exist for other IDEs/editors as well.
* black can be integrated with multiple editors, please, instructions are available [here](https://black.readthedocs.io/en/stable/integrations/editors.html).

8. Install Allure CLI

Allure CLI installation is not an easy task, so a better option might be to run allure from
docker container (please, refer to p.2 of the next section for instructions).

To install Allure CLI you may take one of the following ways:

- Follow the [instruction](https://docs.qameta.io/allure/#_linux) from the official website
- Consult [the thread](https://github.com/allure-framework/allure2/issues/989)
- Download release from the Github
```shell
$ wget https://github.com/allure-framework/allure2/releases/download/2.18.1/allure_2.18.1-1_all.deb
$ sudo apt install ./allure_2.18.1-1_all.deb
```
You also need the `default-jre` package installed.

If none of the options worked for you, please complete the instruction with your approach.

### Run and get report

1. Run tests

Make sure that the virtualenv is activated, then execute the following command to run a singular test suite or all the suites in the directory
```shell
$ pytest --alluredir my-allure-123 pytest_tests/testsuites/object/test_object_api.py
$ pytest --alluredir my-allure-123 pytest_tests/testsuites/
```

2. Generate report

If you opted to install Allure CLI, you can generate a report using the command `allure generate`. The web representation of the report will be under `allure-report` directory:
```shell
$ allure generate my-allure-123
$ ls allure-report/
app.js  data  export  favicon.ico  history  index.html  plugins  styles.css  widgets
```

To inspect the report in a browser, run
```shell
$ allure serve my-allure-123
```

If you prefer to run allure from Docker, you can use the following command:
```shell
$ mkdir -p $PWD/allure-reports 
$ docker run -p 5050:5050 -e CHECK_RESULTS_EVERY_SECONDS=30 -e KEEP_HISTORY=1 \
    -v $PWD/my-allure-123:/app/allure-results \
    -v $PWD/allure-reports:/app/default-reports \
    frankescobar/allure-docker-service
```

Then, you can check the allure report in your browser [by this link](http://localhost:5050/allure-docker-service/projects/default/reports/latest/index.html?redirect=false)

NOTE: feel free to select a different location for `allure-reports` directory, there is no requirement to have it inside `frostfs-testcases`. For example, you can place it under `/tmp` path.

# Contributing

Feel free to contribute to this project after reading the [contributing
guidelines](CONTRIBUTING.md).

Before starting to work on a certain topic, create a new issue first, describing
the feature/topic you are going to implement.


# License

- [GNU General Public License v3.0](LICENSE)

## Pytest marks

Custom pytest marks used in tests:
* `sanity` - Tests must be runs in sanity testruns.
* `smoke` - Tests must be runs in smoke testruns.
