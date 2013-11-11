import difflib

_file_template = """
<div id="diff_table_div">
%(summary)s
%(legend)s
%(table)s
</div>
<script type="text/javascript">
  pageLoaded('diff_table_div');
</script>"""

_table_template = """
    <table class="diff" id="difflib_chg_%(prefix)s_top"
           cellspacing="0" cellpadding="0" rules="groups">
        <colgroup></colgroup> <colgroup></colgroup> <colgroup></colgroup>
        <colgroup></colgroup> <colgroup></colgroup> <colgroup></colgroup>
        %(header_row)s
        <tbody>
%(data_rows)s        </tbody>
    </table>
"""

_legend = """
    <table class="diff" summary="Legends">
        <tr> <th colspan="2"> Legends </th> </tr>
        <tr> <td> <table border="" summary="Colors">
                      <tr><th> Colors </th> </tr>
                      <tr><td class="diff_add">Extra</td></tr>
                      <tr><td class="diff_chg">Different</td> </tr>
                      <tr><td class="diff_sub">Missing</td> </tr>
                  </table></td>
             <td> <table border="" summary="Links">
                      <tr><th colspan="2"> Links </th> </tr>
                      <tr><td>(f)irst change</td> </tr>
                      <tr><td>(n)ext change</td> </tr>
                      <tr><td>(t)op</td> </tr>
                      <tr><td>(s)how same region</td> </tr>
                      <tr><td>(h)ide same region</td> </tr>
                  </table></td> </tr>
    </table>"""

MAX_NUM_REVEALS = 3
MAX_DIFF_LINES = 512
LINE_WRAP = 64
SOFT_MAX_LINE_LENGTH = 128
HARD_MAX_LINE_LENGTH = 1024


def limit_revealed_lines_to(diffs, limit, hide_expected):
    def truncate_line(todata, expected_length):
        max_length = min(max(expected_length, SOFT_MAX_LINE_LENGTH),
                         HARD_MAX_LINE_LENGTH)
        if len(todata[1]) > max_length:
            new = todata[1][:max_length] + '...truncated'
            if todata[1].endswith('\n\x01'):
                new += '\n\x01'
            elif todata[1].endswith('\x01'):
                new += '\x01'
            return todata[0], new
        else:
            return todata

    num_reveals = 0
    different_lines = 0

    obscured = '<<Expected output obscured by instructor.>>'
    for fromdata, todata, flag in diffs:
        if flag:
            different_lines += 1
            if '\0-' in fromdata[1] or '\0^' in fromdata[1]:
                num_reveals += 1
        if different_lines > MAX_DIFF_LINES or limit and num_reveals > limit:
            trun = '...', '<<Remaining diff not shown>>'
            yield trun, trun, False
            break
        todata = truncate_line(todata, len(fromdata[1]))
        if hide_expected:
            fromdata = fromdata[0], obscured
            obscured = ''
        yield fromdata, todata, flag


def change_same_starting_points(flaglist):
    """Gets points at which changes begin"""

    change_points = []
    same_points = []
    in_change = False

    if flaglist and not flaglist[0]:
        same_points.append(0)

    for x, flag in enumerate(flaglist):
        if flag and not in_change:
            change_points.append(x)
            in_change = True
        elif not flag and in_change:
            same_points.append(x)
            in_change = False

    return (change_points, same_points)


class HTMLDiff(difflib.HtmlDiff):
    FROM_DESC = 'Correct Output'
    TO_DESC = 'Your Output'
    TD_DIFF_HEADER = '<td class="diff_header"{0}>{1}</td>\
    <td style="white-space:nowrap{2}">{3}</td>'
    SHOW_HIDE_INSTRUMENTATION = "<p>" + \
        """\t<a href="javascript:void(0)" onclick="showAll(""" + \
        """'difflib_chg_{0}_top');">Show All</a>\n""" + \
        """\t<a href="javascript:void(0)" onclick="hideAll(""" + \
        """'difflib_chg_{0}_top');">Hide All</a>\n""" + \
        "</p>"
    FAILING_TEST_BLOCK = '<h3 id="{0}" style="color:red">{1}: {2}</h3>\n{3}'
    TENTATIVE_SCORE_BLOCK = ('<p>Tentative execution score: {0} / {1} '
                             '({2:.2f}%)</p>\n')
    NEXT_ID_CHANGE = ' id="difflib_chg_{0}_{1}"'
    NEXT_HREF = '<a href="#difflib_chg_{0}_{1}">n</a>'
    NEXT_HREF_TOP = '<a href="#difflib_chg_{0}_top">t</a>'
    NEXT_ID_SAME = ' id="difflib_same_{0}{1}_{2}"'
    SHOW_HIDE_ROWS = \
        '<a href="javascript:void(0)" onclick="showHideRows(this);">h</a>'
    NO_DIFFERENCES = '<td></td><td>&nbsp;No Differences Found&nbsp;</td>'
    EMPTY_FILE = '<td></td><td>&nbsp;Empty File&nbsp;</td>'
    MAX_SAME_LINES_BEFORE_SHOW_HIDE = 5  # must be >= 4

    def __init__(self, diffs=[], points_possible=0,
                 num_reveal_limit=MAX_NUM_REVEALS):
        """Set num_reveal_limit to None to not reveal"""
        super(HTMLDiff, self).__init__(wrapcolumn=LINE_WRAP)
        self._legend = _legend
        self._table_template = _table_template
        self._file_template = _file_template
        self._last_collapsed = False
        self._diff_html = {}  # maps a diff to html
        self._num_reveal_limit = num_reveal_limit
        self._points_possible = points_possible
        for d in diffs:
            self.add_renderable(d)

    def add_renderable(self, diff):
        self._diff_html[diff] = self._make_html_for_diff(diff)

    def _make_html_for_diff(self, diff):
        table = None
        if diff.should_show_table():
            table = self._make_table_for_diff(diff)
        wrong_things = diff.wrong_things_html_list()
        inner = diff.extra_display()
        if table:
            inner += table
        if wrong_things:
            inner += wrong_things
        if inner != '':
            return self.FAILING_TEST_BLOCK.format(diff.name_id(),
                                                  diff.escaped_group(),
                                                  diff.escaped_name(),
                                                  inner)
        else:
            return None

    def make_table(self, diff):
        """Makes unique anchor prefixes so that multiple tables may exist
        on the same page without conflict."""
        self._make_prefix()
        diffs = diff._diff._diff

        # set up iterator to wrap lines that exceed desired width
        if self._wrapcolumn:
            diffs = self._line_wrapper(diffs, diff._diff.hide_expected)

        # collect up from/to lines and flags into lists (also format the lines)
        fromlist, tolist, flaglist = self._collect_lines(diffs)

        # process change flags, generating middle column of next anchors/links
        fromlist, tolist, flaglist, next_href, next_id = self._convert_flags(
            fromlist, tolist, flaglist, False, 5)

        s = []
        fmt = '            <tr><td class="diff_next"%s>%s</td>%s' + \
              '<td class="diff_next">%s</td>%s</tr>\n'
        for i in range(len(flaglist)):
            if flaglist[i] is None:
                # mdiff yields None on separator lines skip the bogus ones
                # generated for the first line
                if i > 0:
                    s.append('        </tbody>        \n        <tbody>\n')
            else:
                s.append(fmt % (next_id[i], next_href[i], fromlist[i],
                                next_href[i], tolist[i]))
        header_row = '<thead><tr>%s%s%s%s</tr></thead>' % (
            '<th class="diff_next"><br /></th>',
            '<th colspan="2" class="diff_header">%s</th>' % self.FROM_DESC,
            '<th class="diff_next"><br /></th>',
            '<th colspan="2" class="diff_header">%s</th>' % self.TO_DESC)

        table = self._table_template % dict(
            data_rows=''.join(s),
            header_row=header_row,
            prefix=self._prefix[1])

        return table.replace('\0+', '<span class="diff_add">'). \
            replace('\0-', '<span class="diff_sub">'). \
            replace('\0^', '<span class="diff_chg">'). \
            replace('\1', '</span>'). \
            replace('\t', '&nbsp;')

    def _format_line(self, side, flag, linenum, text):
        """Returns HTML markup of "from" / "to" text lines

        side -- 0 or 1 indicating "from" or "to" text
        flag -- indicates if difference on line
        linenum -- line number (used for line number column)
        text -- line text to be marked up
        """
        try:
            linenum = '%d' % linenum
            id = ' id="%s%s"' % (self._prefix[side], linenum)
        except TypeError:
            # handle blank lines where linenum is '>' or ''
            id = ''
        # replace those things that would get confused with HTML symbols
        text = text.replace("&", "&amp;"). \
            replace(">", "&gt;"). \
            replace("<", "&lt;")

        # make space non-breakable so they don't get compressed or line wrapped
        text = text.replace(' ', '&nbsp;').rstrip()

        color = ''
        if '\0^' in text or '\0+' in text or '\0-' in text:
            color = ';background-color:{0}'
            if side == 0:
                color = color.format('#ffe6e6')
            else:
                color = color.format('#e3ffe3')
        return self.TD_DIFF_HEADER.format(id, linenum, color, text)

    def _make_table_for_diff(self, diff):
        """Assumes that we should show the table for the diff"""
        self._last_collapsed = False
        table = self.make_table(diff)
        if self._last_collapsed:
            show_hide = self.SHOW_HIDE_INSTRUMENTATION.format(
                self._prefix[1])
            table = '{0}{1}{0}'.format(show_hide, table)
        return table

    def _make_test_summary(self):
        """Return html tables for failed and passed tests."""
        template = ('<h3 style="color:{2}">{0} Tests</h3>'
                    '<table border="1">\n  <tr><th>Test Group</th>'
                    '<th>Test Name</th><th>Value</th></tr>{1}</table>')
        failed = passed = ''
        for diff in sorted(self._all_diffs()):
            output = diff.html_header_row()
            if self._has_diff(diff):
                failed += output
            else:
                passed += output

        output = ''
        if failed:
            output += template.format('Failed', failed, 'red')
        if passed:
            output += template.format('Passed', passed, 'green')
        return output

    def _has_diff(self, diff):
        return self._diff_html.get(diff, None) is not None

    def _all_diffs(self):
        return self._diff_html.keys()

    def tentative_score(self):
        """Return the total, available, and percentage score."""
        diffs = self._all_diffs()
        total = sum(x.test_points for x in diffs if x.is_correct())
        if self._points_possible > 0:
            percent = total * 100. / self._points_possible
        else:
            percent = 0
        return total, self._points_possible, percent

    def make_summary(self):
        retval = self.TENTATIVE_SCORE_BLOCK.format(*self.tentative_score())
        retval += self._make_test_summary()
        return retval

    def is_legend_needed(self):
        for diff in self._all_diffs():
            if diff.should_show_table():
                return True
        return False

    def legend_html(self):
        if self.is_legend_needed():
            return "<hr>{0}<hr>".format(self._legend)
        else:
            return "<hr>"

    def make_whole_file(self):
        tables = [self._diff_html[diff] for diff in sorted(self._all_diffs())
                  if self._has_diff(diff)]
        return self._file_template % dict(
            summary=self.make_summary(),
            legend=self.legend_html(),
            table='<hr>\n'.join(tables))

    def _line_wrapper(self, diffs, hide_expected):
        diffs = limit_revealed_lines_to(diffs, self._num_reveal_limit,
                                        hide_expected)
        return super(HTMLDiff, self)._line_wrapper(diffs)

    def _make_prefix(self):
        sameprefix = "same{0}_".format(HTMLDiff._default_prefix)
        super(HTMLDiff, self)._make_prefix()
        self._prefix.append(sameprefix)

    def _convert_flags(self, fromlist, tolist, flaglist, context, numlines):
        """Handles making inline links in the document."""

        # all anchor names will be generated using the unique "to" prefix
        toprefix = self._prefix[1]
        sameprefix = self._prefix[2]

        # process change flags, generating middle column of next anchors/links
        next_id = [''] * len(flaglist)
        next_href = [''] * len(flaglist)
        (change_positions, same_positions) = \
            change_same_starting_points(flaglist)
        change_positions_set = set(change_positions)

        for numChange, changePos in enumerate(change_positions[: -1]):
            next_id[changePos] = self.NEXT_ID_CHANGE.format(
                toprefix, numChange)
            next_href[changePos] = self.NEXT_HREF.format(
                toprefix, numChange + 1)

        for same_block, same_start_pos in enumerate(same_positions):
            same_pos = same_start_pos
            while same_pos < len(flaglist) and \
                    same_pos not in change_positions_set:
                next_id[same_pos] = self.NEXT_ID_SAME.format(
                    sameprefix, same_block,
                    same_pos - same_start_pos + 1)
                same_pos += 1
            num_same_lines = same_pos - same_start_pos
            if num_same_lines > self.MAX_SAME_LINES_BEFORE_SHOW_HIDE:
                next_href[same_start_pos + 2] = self.SHOW_HIDE_ROWS
                self._last_collapsed = True

        # check for cases where there is no content to avoid exceptions
        if not flaglist:
            flaglist = [False]
            next_id = ['']
            next_href = ['']
            if context:
                fromlist = [self.NO_DIFFERENCES]
                tolist = fromlist
            else:
                fromlist = tolist = [self.EMPTY_FILE]

        # redo the last link to link to the top
        if change_positions:
            pos = change_positions[-1]
            next_id[pos] = self.NEXT_ID_CHANGE.format(
                toprefix, len(change_positions) - 1)
            next_href[pos] = self.NEXT_HREF_TOP.format(toprefix)

        return fromlist, tolist, flaglist, next_href, next_id
