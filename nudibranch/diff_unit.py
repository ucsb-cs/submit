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


class Renderable(object):
    INCORRECT = '<a href="#{1}" style="color:red">{0}</a>'
    CORRECT = '<p style="color:green;margin:0;padding:0;">{0}</p>'
    HTML_ROW = '<tr><td>{0}</td><td>{1}</td><td>{2}</td></tr>'

    MAPPING = {
        'nonexistent_executable': ('The expected executable was not produced '
                                   'during make'),
        'output_limit_exceeded': 'Your program produced too much output',
        'signal': 'Your program terminated with signal {0}',
        'timed_out': 'Your program timed out'}

    def __init__(self, number, group, name, points, status, extra):
        self.number = number
        self.group = esc(group)
        self.name = esc(name)
        self.points = points
        self.status = status
        self.extra = extra
        self.custom_output = ''
        self.id = '{}_{}'.format(number, esc(name))

    def __cmp__(self, other):
        groups = cmp(alphanum_key(self.group),
                     alphanum_key(other.group))
        if groups != 0:
            return groups
        names = cmp(alphanum_key(self.name),
                    alphanum_key(other.name))
        if names != 0:
            return names
        return self.number - other.number

    def get_issue(self):
        if self.status in self.MAPPING:
            return esc(self.MAPPING[self.status].format(self.extra))
        return None

    def show_diff_table(self):
        return False

    def html_header_row(self):
        tmp = self.CORRECT if self.get_issue() is None else self.INCORRECT
        return self.HTML_ROW.format(self.group, tmp.format(self.name, self.id),
                                    self.points)


class DiffWithMetadata(Renderable):
    def __init__(self, diff, **kwargs):
        """Diff is None when the outputs match."""
        super(DiffWithMetadata, self).__init__(**kwargs)
        self.diff = diff

    def show_diff_table(self):
        return self.status != 'nonexistent_executable' and \
            self.diff is not None and self.diff.show_diff_table()

    def get_issue(self):
        issue = super(DiffWithMetadata, self).get_issue()
        return issue if issue else (esc(self.diff.get_issue()) if self.diff
                                    else None)


class ImageOutput(Renderable):
    """Show output image if available."""
    def __init__(self, url, **kwargs):
        super(ImageOutput, self).__init__(**kwargs)
        if url:
            self.custom_output = ('<img class="result_image" src="{}" />'
                                  .format(url))


class TextOutput(Renderable):
    """Show text output if available."""
    def __init__(self, content, **kwargs):
        super(TextOutput, self).__init__(**kwargs)
        if content:
            self.custom_output = '<pre><code>{}</code></pre>'.format(content)


class Diff(object):
    """Represents a saved diff file.  Can be pickled safely."""

    def __init__(self, correct, given):
        self._tabsize = 8
        self._correct_empty = correct == ""
        self._given_empty = given == ""
        self._correct_newline = correct.endswith('\n')
        self._given_newline = given.endswith('\n')
        self._diff = self._make_diff(correct, given) \
            if correct != given else None

    @property
    def correct_empty(self):
        return self._correct_empty

    @property
    def correct_newline(self):
        if hasattr(self, '_correct_newline'):
            return self._correct_newline
        if not self._diff:
            return False
        try:
            last_data = None
            for (line, data), _, differs in self._diff:
                if line:
                    last_data = data, differs
            data, differs = last_data
            if differs:
                assert data.endswith('\x01')
                return data.endswith('\n\x01')
            else:
                return data.endswith('\n')
        except:
            print('correct Invalid data format')
            import pprint
            pprint.pprint(self._diff)
            return None

    @property
    def given_empty(self):
        return self._given_empty

    @property
    def given_newline(self):
        if hasattr(self, '_given_newline'):
            return self._given_newline
        if not self._diff:
            return False
        try:
            last_data = None
            for _, (line, data), differs in self._diff:
                if line:
                    last_data = data, differs
            data, differs = last_data
            if differs:
                assert data.endswith('\x01')
                return data.endswith('\n\x01')
            else:
                return data.endswith('\n')
        except:
            print('given Invalid data format')
            import pprint
            pprint.pprint(self._diff)
            return None

    def outputs_match(self):
        return self._diff is None

    def show_diff_table(self):
        """Show the table when outputs differ and the student has output.

        Do not show student output when the expected output is empty.

        """
        return not self.outputs_match() and not \
            (self.given_empty and not self.correct_empty)

    def get_issue(self):
        if self.correct_empty and not self.given_empty:
            return 'Your program should not have produced output.'
        elif self.given_empty and not self.correct_empty:
            return 'Your program should have produced output.'
        elif self.correct_newline and self.given_newline is False:
            return 'Your program\'s output should end with a newline.'
        elif self.correct_newline is False and self.given_newline:
            return 'Your program\'s output should not end with a newline.'
        elif not self.outputs_match():
            return 'Your program\'s output did not match the expected.'
        return None

    def _make_diff(self, correct, given):
        """Return the intermediate representation of the diff."""
        dmp = DMP()
        dmp.Diff_Timeout = 0
        text1, text2, array = dmp.diff_linesToChars(correct, given)
        diffs = dmp.diff_main(text1, text2)
        dmp.diff_cleanupSemantic(diffs)
        dmp.diff_charsToLines(diffs, array)
        return list(dmp_to_mdiff(diffs))


def esc(string):
    return xml.sax.saxutils.escape(string, {'"': "&quot;", "'": "&apos;"})
