import xml.sax.saxutils
from diff_match_patch import diff_match_patch as DMP
from .helpers import alphanum_key



def dmp_to_mdiff(diffs):
    """Convert from diff_match_patch format to _mdiff format.

    This is sadly necessary to use the HtmlDiff module.

    """
    def yield_buffer(lineno_left, lineno_right):
        while left_buffer or right_buffer:
            if left_buffer:
                left = lineno_left, '\0-{0}\1'.format(left_buffer.pop(0))
                lineno_left += 1
            else:
                left = '', '\n'
            if right_buffer:
                right = lineno_right, '\0+{0}\1'.format(right_buffer.pop(0))
                lineno_right += 1
            else:
                right = '', '\n'
            yield (left, right, True), lineno_left, lineno_right

    lineno_left = lineno_right = 1
    left_buffer = []
    right_buffer = []

    for op, data in diffs:
        for line in data.splitlines(True):
            if op == DMP.DIFF_EQUAL:
                for item, lleft, llright in yield_buffer(lineno_left,
                                                         lineno_right):
                    lineno_left = lleft
                    lineno_right = llright
                    yield item
                yield (lineno_left, line), (lineno_right, line), False
                lineno_left += 1
                lineno_right += 1
            elif op == DMP.DIFF_DELETE:
                left_buffer.append(line)
            elif op == DMP.DIFF_INSERT:
                right_buffer.append(line)

    for item, _, _ in yield_buffer(lineno_left, lineno_right):
        yield item


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
        # TODO: renable exit status checking
        #elif self._status == 'success' and self._extra != 0:
        #    return ['Your program terminated with exit code {0}'
        #            .format(self._extra)]
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

    def extra_display(self):
        return ''

    def escaped_group(self):
        return escape(self.test_group)

    def escaped_name(self):
        return escape(self.test_name)

    def __cmp__(self, other):
        groups = cmp(alphanum_key(self.test_group),
                     alphanum_key(other.test_group))
        if groups == 0:
            names = cmp(alphanum_key(self.test_name),
                        alphanum_key(other.test_name))
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


class DiffWithMetadata(DiffRenderable):
    '''Wraps around a Diff to impart additional functionality.
    Not intended to be stored.'''

    def __init__(self, diff, test_num, test_group, test_name,
                 test_points, extra_info):
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


class ImageOutput(DiffRenderable):
    """Show output image if available."""
    def __init__(self, test_num, test_group, test_name, test_points,
                 extra_info, image_url):
        super(ImageOutput, self).__init__(test_num, test_group, test_name,
                                          test_points)
        self.extra_info = extra_info
        self.image_url = image_url

    def extra_display(self):
        return '<img class="result_image" src="{0}" />'.format(self.image_url)

    def is_correct(self):
        return False

    def should_show_table(self):
        return False

    def wrong_things(self):
        return self.extra_info.wrong_things()


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
        """Return the intermediate representation of the diff."""
        dmp = DMP()
        dmp.Diff_Timeout = 0
        text1, text2, array = dmp.diff_linesToChars(correct, given)
        diffs = dmp.diff_main(text1, text2)
        dmp.diff_cleanupSemantic(diffs)
        dmp.diff_charsToLines(diffs, array)
        return list(dmp_to_mdiff(diffs))


def escape(string):
    return xml.sax.saxutils.escape(string, {'"': "&quot;",
                                            "'": "&apos;"})
