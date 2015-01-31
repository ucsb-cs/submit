# Contributing Guidelines

## Commiting code

Before commiting any code, the `lint.sh` tool should be run. Code should only
be committed when `lint.sh` reports no errors (has no output).


## Generating Migrations

   alembic -c INI_PATH revision --autogenerate -m "MSG"


## Development Installation Prerequisites

Developing and running this project requires the following utilities to be
independently installed. All other requirements will be installed as part of
the development process:

 * git
 * pip
 * python2.6+ (not python3 yet)
 * virtualenv

Install these packages however you prefer for your operating system. Make sure
that you can create python virtual environments with a python2.6+ binary.

## Check out the project and run in development mode

0. Check out the source

        git clone git@github.com:ucsb-cs/submit.git

0. Create the virtual environment

    These examples use `~/.venv` as the virtual environment location,
    however, feel free to use whatever you prefer.

        virtualenv ~/.venv/submit

        # If python2 is not the default for your virtualenv you will want to
        # add -p /path/to/python/2/bin

0. Load the virtual environment (Note: you will need to run this every time you
open a new terminal to run the project's commands)

        source ~/.venv/submit/bin/activate

0. Install the package and its dependencies in development mode

        cd submit
        pip install -e .[dev]

0. Run the project in development

        # From the `first submit` directory (contains development.ini)
        pserve development.ini --reload

    At this point you can connect to the service with your web browser at:
    [http://localhost:6543](http://localhost:6543)

    Any changes you make to the app should automatically be reflected.


## Configuring the worker machines

Each worker should be configured to run in its own account in order to provide
the best possible data isolation between submissions from various students.

Below are the instructions for setting up a worker account. Note that you can
use whatever naming schema you want. The following are just an example.


0. Create a ssh keypair for all the workers (this need only be done once)

        ssh-keygen -C "submit worker" -N "" -f worker_rsa
        # Save worker_rsa in a secure location (you'll need its path for the
        # ini file).

0. Create a user account

        sudo adduser --disabled-password worker0

0. Set umask 077 (700 permissisions) for the new account

        echo umask 077 | sudo -u worker0 -i tee -a .profile

0. Configure passwordless ssh access to the account using the ssh key

        sudo -u worker0 -i mkdir .ssh
        cat worker_rsa.pub | sudo -u worker0 -i tee -a .ssh/authorized_keys

0. Test passwordless ssh access

        ssh -i worker_rsa worker0@localhost
