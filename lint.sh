#!/bin/bash

dir=$(dirname $0)

# flake8 (runs pep8 and pyflakes)
flake8 $dir/submit
if [ $? -ne 0 ]; then
    echo "Exiting due to flake8 errors. Fix and re-run to finish tests."
    exit $?
fi

# ignore pylint for now
exit 0

# pylint
output=$(pylint --rcfile=$dir/.pylintrc $dir/submit 2> /dev/null)
if [ -n "$output" ]; then
    echo "---pylint---"
    echo -e "$output"
    exit $?
fi
