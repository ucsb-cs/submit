# submit

`submit` is a web service that is intented to be used for online submission of
programming assignments. When configured, submitted projects can be
automatically assessed.

Note: This web service was written to work on UCSB's network. A number of
manual modifications are necessary to get working elsewhere.


## Releasing

In order to make a release bump the version number in
`submit/__init__.py`. Please follow [semantic versioning](http://semver.org/).

Make a pull request as normal, and once merged to master complete the
following.

From your development machine run (replace `X.X.X` with the version string).

    python setup.py bdist_wheel
    python setup.py sdist upload
    VERSION=X.X.X git tag -m "v$VERSION" "v$VERSION"
    git push --tags

From submit.cs run:

    ./update_app.sh --update
