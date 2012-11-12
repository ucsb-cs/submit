import difflib
import xml.sax.saxutils


class DiffUnit(object):
    '''Represents a single diff.
    Can be pickled safely.'''

    INCORRECT_HTML_TEST_NAME = '<a href="#{0}" style="color:red">{1}</a>'
    CORRECT_HTML_TEST_NAME = '<pre style="color:green">{0}</pre>'
    HTML_ROW = '<tr><td>{0}</td><td>{1}</td><td>{2}</td></tr>'

    def __init__(self, correct, given, test_num, test_name, test_points):
        self._tabsize = 8
        self.correct = correct
        self.given = given
        self.test_num = test_num
        self.test_name = test_name
        self.test_points = test_points
        self.diff = self._make_diff()

    @staticmethod
    def escape(string):
        return xml.sax.saxutils.escape(string, {'"': "&quot;",
                                                "'": "&apos;"})

    def make_diff(self):
        if not self.is_correct():
            fromlines, tolines = self._tab_newline_replace(self.correct,
                                                           self.given)
            return [d for d in difflib._mdiff(fromlines, tolines)]

    def is_correct(self):
        return self.correct == self.given

    def __cmp__(self, other):
        return self.test_num - other.test_num

    def escaped_name(self):
        return DiffUnit.escape(self.test_name)

    def name_id(self):
        return "{0}_{1}".format(int(self.test_num),
                                self.escaped_name())

    def html_test_name(self):
        if not self.is_correct():
            return self.INCORRECT_HTML_TEST_NAME.format(self.name_id(),
                                                        self.escaped_name())
        else:
            return self.CORRECT_HTML_TEST_NAME.format(self.escaped_name())

    def html_row(self):
        return self.HTML_ROW.format(self.test_num,
                                    self.html_test_name(),
                                    self.test_points)

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
