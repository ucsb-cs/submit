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

# pylint
#output=$(pylint --rcfile=$dir/.pylintrc $dir/nudibranch 2> /dev/null)
output=""
if [ -n "$output" ]; then
    echo "---pylint---"
    echo -e "$output"
    failure=1
fi

# pyflakes
output=$(find $dir/nudibranch -name [A-Za-z_]\*.py -exec pyflakes {} \;)
if [ -n "$output" ]; then
    echo "---pyflakes---"
    echo -e "$output"
    failure=1
fi

exit $failure
