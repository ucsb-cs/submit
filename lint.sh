#!/bin/bash

dir=$(dirname $0)

failure=0

# pep8
output=$(find $dir -name \*.py -exec pep8 {} \;)
if [ -n "$output" ]; then
    echo "---pep8----"
    echo -e "$output"
    failure=1
fi

# pyflakes does not work with python 3 yet

exit $failure
