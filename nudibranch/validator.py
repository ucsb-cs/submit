from functools import wraps
from pyramid.httpexceptions import HTTPBadRequest
from .helpers import http_bad_request

# Inspirted by reddit's validator code


def validated_form(*simple_vals, **param_vals):
    MISSING_ERROR = 'Missing parameter: {0}'

    def initial_wrap(function):
        @wraps(function)
        def wrapped(request):
            # Ensure the request body is json
            try:
                data = request.json_body
            except ValueError:
                return http_bad_request(request, 'Request body must be JSON.')
            # Validate each of the named parameters
            error_messages = []
            validated_params = {}
            for param, validator in param_vals.items():
                if param in data:
                    validator_errors = []
                    result = validator(data[param], validator_errors)
                    if validator_errors:
                        error_messages.extend(validator_errors)
                    else:
                        validated_params[param] = result
                else:
                    error_messages.append(MISSING_ERROR.format(param))
            if error_messages:
                return http_bad_request(request, error_messages)
            return function(request, **validated_params)
        return wrapped
    return initial_wrap


class Validator(object):
    def __init__(self, param):
        self.param = param

    def __call__(self, value, *args):
        return self.run(value, *args)

    def add_error(self, errors, message):
        errors.append('Validation error on param {0!r}: {1}'
                      .format(self.param, message))


class VWSString(Validator):
    '''A validator for a generic string that allows whitespace on both ends.'''
    def __init__(self, *args, min_length=0, max_length=None):
        super(VWSString, self).__init__(*args)
        self.min_length = min_length
        self.max_length = max_length

    def run(self, value, errors):
        if not isinstance(value, str):
            self.add_error(errors, 'must be a string')
        elif self.min_length and len(value) < self.min_length:
            self.add_error(errors,
                           'must be >= {0} characters'.format(self.min_length))
        elif self.max_length and len(value) > self.max_length:
            self.add_error(errors,
                           'must be <= {0} characters'.format(self.max_length))
        return value


class VString(VWSString):
    '''A validator that removes whitespace on both ends.'''
    def run(self, value, *args):
        return super(VString, self).run(value.strip(), *args)
