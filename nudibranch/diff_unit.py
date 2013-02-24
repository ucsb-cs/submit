import difflib
from .helpers import escape


class DiffExtraInfo(object):
    '''TestCaseResult can either have a signal thrown or have a normal
    exit status.  This abstracts that away.'''

    def __init__(self, status, extra):
        self._status = status
        self._extra = extra

    def should_show_table(self):
        return self._status != 'nonexistent_executable'

    def wrong_things(self):
        """Returns a list of strings describing the error."""
        if self._status == 'nonexistent_executable':
            return ['The expected executable was not produced during make']
        elif self._status == 'output_limit_exceeded':
            return ['Your program produced too much output']
        elif self._status == 'signal':
            return ['Your program terminated with signal {0}'
                    .format(self._extra)]
        elif self._status == 'timed_out':
            return ['Your program timed out']
        elif self._status == 'success' and self._extra != 0:
            return ['Your program terminated with exit code {0}'
                    .format(self._extra)]
        else:
            return []


class DiffRenderable(object):
    '''Something that can be rendered with HTMLDiff.
    This is intended to be abstract'''

    INCORRECT_HTML_TEST_NAME = '<a href="#{0}" style="color:red">{1}</a>'
    CORRECT_HTML_TEST_NAME = \
        '<p style="color:green;margin:0;padding:0;">{0}</p>'
    HTML_ROW = '<tr><td>{0}</td><td>{1}</td><td>{2}</td></tr>'

    def __init__(self, test_num, test_group, test_name, test_points):
        self.test_num = test_num
        self.test_group = test_group
        self.test_name = test_name
        self.test_points = test_points

    def is_correct(self):
        raise NotImplemented

    def should_show_table(self):
        '''Whether or not we should show the diff table with diff results'''
        raise NotImplemented

    def wrong_things(self):
        '''Returns a list of strings describing everything that's wrong'''
        raise NotImplemented

    def wrong_things_html_list(self):
        '''Returns all the things that were wrong in an html list, or None if
        nothing was wrong'''
        things = self.wrong_things()
        if things:
            list_items = ["<li>{0}</li>".format(escape(thing))
                          for thing in things]
            return "<ul>{0}</ul>".format("\n".join(list_items))
        else:
            return None

    def escaped_group(self):
        return escape(self.test_group)

    def escaped_name(self):
        return escape(self.test_name)

    def __cmp__(self, other):
        groups = cmp(self.test_group, other.test_group)
        if groups == 0:
            names = cmp(self.test_name, other.test_name)
            if names == 0:
                return self.test_num - other.test_num
            else:
                return names
        else:
            return groups

    def name_id(self):
        return "{0}_{1}".format(int(self.test_num),
                                self.escaped_name())

    def html_test_name(self):
        if not self.is_correct():
            return self.INCORRECT_HTML_TEST_NAME.format(self.name_id(),
                                                        self.escaped_name())
        else:
            return self.CORRECT_HTML_TEST_NAME.format(self.escaped_name())

    def html_header_row(self):
        return self.HTML_ROW.format(self.escaped_group(),
                                    self.html_test_name(),
                                    self.test_points)


class NonDiffErrors(DiffRenderable):
    '''Used to encode errors that exist external to a diff, as when
    files are missing so there isn't even a diff to show'''

    def __init__(self, test_num, test_group,
                 test_name, test_points, error_list):
        super(NonDiffErrors, self).__init__(
            test_num, test_group, test_name, test_points)
        self.error_list = error_list

    def is_correct(self):
        return False

    def should_show_table(self):
        return False

    def wrong_things(self):
        return self.error_list


class DiffWithMetadata(DiffRenderable):
    '''Wraps around a Diff to impart additional functionality.
    Not intended to be stored.'''

    def __init__(self, diff, test_num, test_group,
                 test_name, test_points, extra_info):
        super(DiffWithMetadata, self).__init__(
            test_num, test_group, test_name, test_points)
        self._diff = diff
        self.extra_info = extra_info

    def is_correct(self):
        return len(self.wrong_things()) == 0

    def outputs_match(self):
        return self._diff.outputs_match()

    def should_show_table(self):
        return self._diff.should_show_table() and \
            self.extra_info.should_show_table()

    def wrong_things(self):
        '''Returns a list of strings describing everything that's wrong'''
        return self._diff.wrong_things() + self.extra_info.wrong_things()


class Diff(object):
    '''Represents a saved diff file.  Can be pickled safely.'''

    def __init__(self, correct, given):
        self._tabsize = 8
        self._correct_empty = correct == ""
        self._given_empty = given == ""
        self._diff = self._make_diff(correct, given) \
            if correct != given else None

    def is_correct_empty(self):
        return self._correct_empty

    def is_given_empty(self):
        return self._given_empty

    def outputs_match(self):
        return self._diff is None

    def should_show_table(self):
        '''Determines whether or not an HTML table showing this result
        should be made.  This is whenever the results didn't match and
        the student at least attempted to produce output'''
        return not self.outputs_match() and not \
            (self.is_given_empty() and not self.is_correct_empty())

    def wrong_things(self):
        retval = []
        if self.is_correct_empty() and not self.is_given_empty():
            retval.append('Your program should not have produced output')
        elif self.is_given_empty() and not self.is_correct_empty():
            retval.append('Your program should have produced output')
        if not self.outputs_match():
            retval.append('Your program\'s output did not match the expected.')
        return retval

    def _make_diff(self, correct, given):
        '''Only to be called when there is a difference'''
        fromlines, tolines = self._tab_newline_replace(correct,
                                                       given)
        return [d for d in difflib._mdiff(fromlines, tolines)]

    def _tab_newline_replace(self, fromlines, tolines):
        """Returns from/to line lists with tabs expanded
        and newlines removed.

        Instead of tab characters being replaced by the number of spaces
        needed to fill in to the next tab stop, this function will fill
        the space with tab characters.  This is done so that the difference
        algorithms can identify changes in a file when tabs are replaced by
        spaces and vice versa.  At the end of the HTML generation, the tab
        characters will be replaced with a nonbreakable space.
        """
        def expand_tabs(line):
            # hide real spaces
            line = line.replace(' ', '\0')
            # expand tabs into spaces
            line = line.expandtabs(self._tabsize)
            # replace spaces from expanded tabs back into tab characters
            # (we'll replace them with markup after we do differencing)
            line = line.replace(' ', '\t')
            return line.replace('\0', ' ').rstrip('\n')
        fromlines = [expand_tabs(line) for line in fromlines]
        tolines = [expand_tabs(line) for line in tolines]
        return fromlines, tolines
