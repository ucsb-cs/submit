# Installation for development

## Prerequisites

Developing and running this project requires the following utilities to be
independently installed. All other requirements will be installed as part of
the development process:

 * git
 * python3
 * virtualenv

Install these packages however you prefer for your operating system. Make sure
that you can create python virtual environments with a python3.2 binary.

## Configure and become familiar with git

Regardless of how you installed git, please follow
[these](https://help.github.com/articles/set-up-git#platform-all) instructions
beginning with the section "Set Up Git" to configure your name and email
combination. Also, if you are not familiar with git, please go through the
[try.github.com](http://try.github.com/) tutorial.

## Check out the project and run in development mode

0. Check out the source

        git clone git@github.com:ucsb-cs-education/nudibranch.git

0. Create the virtual environment

    These examples use `~/.venv` as the virtual environment location,
    however, feel free to use whatever you prefer.

        virtualenv -p /path/to/python/3/bin ~/.venv/nudibranch
        # If python3 is the default for your virtualenv you can leave off the
        # -p /path/to/python/3/bin arguments

0. Load the virtual environment (Note: you will need to run this everytime you
open a new terminal to run the project's commands)

        source ~/.venv/nudibranch/bin/activate

0. Install the package and its dependencies in development mode

        cd nudibranch
        python setup.py develop

0. Install some development and testing tools

        pip install pep8

0. Run the project in development

        # From the `first nudibranch` directory (contains development.ini)
        pserve development.ini --reload

    At this point you can connect to the service with your web browser at:
    [http://localhost:6543](http://localhost:6543)

    Any changes you make to the app should automatically be reflected.


# Working with the source

## Developing Tests

Test cases should be added to each view method in
`nudibranch/tests.py`. Multiple test cases should be written for each view to
cover every possible path through the view.

To run the tests execute `python setup.py test -q`.

## Commiting code

Before commiting any code, the `lint.sh` tool should be run. Code should only
be committed when `lint.sh` reports no errors (has no output).

The basic proceedure for code commiting is:

0. Run `lint.sh` and fix all errors before continuing

        ./lint.sh

0. Run `python setup.py test -q` and ensure all tests pass.

0. Use `git status` to review what files you modified

0. Use `git diff` to review in more detail what changes you made, and be
sure you are satisifed.  (You did test, didn't you?)

0. Use `git add` on each file you intend on committing changes for.

0. Run `git status` again and be sure __only__ the files you want to commit are
in the top "Changes to be committed" section.

0. Run `git diff --staged` to perform one last lookover of the files you are
about to commit. You have already run the tests and the lint tool right?


0. Commit the code with an appropriate update message

        git commit -m "replace with your message"

0. Push the code to the remote repository

        git push
        # The first time you push run
        # git push -u origin master

Pushing to the remote repository may result in an error when the remote
repository has new commits not reflected in your local repository. In this case
you will need to merge the changes.  Below are the simplest merge steps,
however, please note that additional complications may arise when the same file
has been edited in the commits that require merging.

__Note these may need to be updated to reflect the git process.__

0. Pull down and merge the remote commits

        git pull

0. If there were merge errors you will have to figure out how to resolve them.

Consult help if needed. __Note__: Whatever you do, do not force push to the
remote repository. Doing so will likely cause a git train wreck.

0. Finally push all outstanding commits to the remote repository

        git push
