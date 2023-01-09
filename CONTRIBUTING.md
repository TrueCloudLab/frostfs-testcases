# Contribution guide

First, thank you for contributing! We love and encourage pull requests from
everyone. Please follow the guidelines:

- Check the open [issues](https://github.com/TrueCloudLab/frostfs-testcases/issues) and
  [pull requests](https://github.com/TrueCloudLab/frostfs-testcases/pulls) for existing
  discussions.

- Open an issue first, to discuss a new feature or enhancement.

- Write tests, and make sure the test suite passes locally.

- Open a pull request, and reference the relevant issue(s).

- Make sure your commits are logically separated and have good comments
  explaining the details of your change.

- After receiving feedback, amend your commits or add new ones as appropriate.

- **Have fun!**

## Development Workflow

Start by forking the `frostfs-testcases` repository, make changes in a branch and then
send a pull request. We encourage pull requests to discuss code changes. Here
are the steps in details:

### Set up your GitHub Repository

Fork [FrosfFS testcases upstream](https://github.com/TrueCloudLab/frostfs-testcases/fork) source
repository to your own personal repository. Copy the URL of your fork and clone it:

```shell
$ git clone <url of your fork>
```

### Set up git remote as ``upstream``
```sh
$ cd frostfs-testcases
$ git remote add upstream https://github.com/TrueCloudLab/frostfs-testcases
$ git fetch upstream
```

### Set up development environment

To setup development environment for `frosfs-testcases`, please, take the following steps:
1. Prepare virtualenv

```shell
$ virtualenv --python=python3.9 venv
$ source venv/bin/activate
```

2. Install all dependencies:

```shell
$ pip install -r requirements.txt
```

3. Setup pre-commit hooks to run code formatters on staged files before you run a `git commit` command:

```shell
$ pre-commit install
```

Optionally you might want to integrate code formatters with your code editor to apply formatters to code files as you go:
* isort is supported by [PyCharm](https://plugins.jetbrains.com/plugin/15434-isortconnect), [VS Code](https://cereblanco.medium.com/setup-black-and-isort-in-vscode-514804590bf9). Plugins exist for other IDEs/editors as well.
* black can be integrated with multiple editors, please, instructions are available [here](https://black.readthedocs.io/en/stable/integrations/editors.html).

### Create your feature branch

Before making code changes, make sure you create a separate branch for these
changes. Maybe you will find it convenient to name branch in
`<type>/<issue>-<changes_topic>` format.

```shell
$ git checkout -b feature/123-something_awesome
```



### Commit changes

After verification, commit your changes. There is a [great
post](https://chris.beams.io/posts/git-commit/) on how to write useful commit
messages. Try following this template:

```
[#Issue] Summary
Description
<Macros>
<Sign-Off>
```

```shell
$ git commit -am '[#123] Add some feature'
```

### Push to the branch

Push your locally committed changes to the remote origin (your fork):
```shell
$ git push origin feature/123-something_awesome
```

### Create a Pull Request

Pull requests can be created via GitHub. Refer to [this
document](https://help.github.com/articles/creating-a-pull-request/) for
detailed steps on how to create a pull request. After a Pull Request gets peer
reviewed and approved, it will be merged.

## Code Style

The names of Python variables, functions and classes must comply with [PEP8](https://peps.python.org/pep-0008) rules, in particular:
* Name of a variable/function must be in snake_case (lowercase, with words separated by underscores as necessary to improve readability).
* Name of a global variable must be in UPPER_SNAKE_CASE, the underscore (`_`) symbol must be used as a separator between words.
* Name of a class must be in PascalCase (the first letter of each compound word in a variable name is capitalized).
* Names of other variables should not be ended with the underscore symbol.

Line length limit is set as 100 characters.

Imports should be ordered in accordance with [isort default rules](https://pycqa.github.io/isort/).

We use `black` and `isort` for code formatting. Please, refer to [Black code style](https://black.readthedocs.io/en/stable/the_black_code_style/current_style.html) for details.

Type hints are mandatory for library's code:
 - class attributes;
 - function or method's parameters;
 - function or method's return type.

The only exception is return type of test functions or methods - there's no much use in specifying `None` as return type for each test function.

Do not use relative imports. Even if the module is in the same package, use the full package name.

To format docstrings, please, use [Google Style Docstrings](https://sphinxcontrib-napoleon.readthedocs.io/en/latest/example_google.html). Type annotations should be specified in the code and not in docstrings (please, refer to [this sample](https://sphinxcontrib-napoleon.readthedocs.io/en/latest/index.html#type-annotations)).

## DCO Sign off

All authors to the project retain copyright to their work. However, to ensure
that they are only submitting work that they have rights to, we are requiring
everyone to acknowledge this by signing their work.

Any copyright notices in this repository should specify the authors as "the
contributors".

To sign your work, just add a line like this at the end of your commit message:

```
Signed-off-by: Samii Sakisaka <samii@nspcc.ru>
```

This can easily be done with the `--signoff` option to `git commit`.

By doing this you state that you can certify the following (from [The Developer
Certificate of Origin](https://developercertificate.org/)):

```
Developer Certificate of Origin
Version 1.1
Copyright (C) 2004, 2006 The Linux Foundation and its contributors.
1 Letterman Drive
Suite D4700
San Francisco, CA, 94129
Everyone is permitted to copy and distribute verbatim copies of this
license document, but changing it is not allowed.
Developer's Certificate of Origin 1.1
By making a contribution to this project, I certify that:
(a) The contribution was created in whole or in part by me and I
    have the right to submit it under the open source license
    indicated in the file; or
(b) The contribution is based upon previous work that, to the best
    of my knowledge, is covered under an appropriate open source
    license and I have the right under that license to submit that
    work with modifications, whether created in whole or in part
    by me, under the same open source license (unless I am
    permitted to submit under a different license), as indicated
    in the file; or
(c) The contribution was provided directly to me by some other
    person who certified (a), (b) or (c) and I have not modified
    it.
(d) I understand and agree that this project and the contribution
    are public and that a record of the contribution (including all
    personal information I submit with it, including my sign-off) is
    maintained indefinitely and may be redistributed consistent with
    this project or the open source license(s) involved.
```

