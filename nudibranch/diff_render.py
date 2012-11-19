import difflib

_file_template = """
<div id="diff_table_div">
%(summary)s
<hr>
%(legend)s
<hr>
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


def limit_revealed_lines_to(diffs, limit):
    num_reveals = 0
    retval = []
    for fromdata, todata, flag in diffs:
        if flag and ('\0-' in fromdata[1] or '\0^' in fromdata[1]):
            num_reveals += 1
        if num_reveals > MAX_NUM_REVEALS:
            trun = ('...', '<<OUTPUT TRUNCATED>>')
            retval.append((trun, trun, False))
            break
        retval.append((fromdata, todata, flag))
    return retval


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
    SHOW_HIDE_INSTRUMENTATION = """
<p><a href="#" onclick="showAll('difflib_chg_{0}_top');">Show All</a>
    <a href="#" onclick="hideAll('difflib_chg_{0}_top');">Hide All</a></p>"""
    FAILING_TEST_BLOCK = '<h3 id="{0}" style="color:red">{1}</h3>\n{2}'
    TENTATIVE_SCORE_BLOCK = '<ul><li>Tentative total score: {0}</li>\
<li>Tentative percentage score: {1}</li></ul>\n'
    NEXT_ID_CHANGE = ' id="difflib_chg_{0}_{1}"'
    NEXT_HREF = '<a href="#difflib_chg_{0}_{1}">n</a>'
    NEXT_HREF_TOP = '<a href="#difflib_chg_{0}_top">t</a>'
    NEXT_ID_SAME = ' id="difflib_same_{0}{1}_{2}"'
    SHOW_HIDE_ROWS = \
        '<a href="javascript:void(0)" onclick="showHideRows(this);">h</a>'
    NO_DIFFERENCES = '<td></td><td>&nbsp;No Differences Found&nbsp;</td>'
    EMPTY_FILE = '<td></td><td>&nbsp;Empty File&nbsp;</td>'
    MAX_SAME_LINES_BEFORE_SHOW_HIDE = 5  # must be >= 4

    def __init__(self, diffs=[]):
        super(HTMLDiff, self).__init__(wrapcolumn=50)
        self._legend = _legend
        self._table_template = _table_template
        self._file_template = _file_template
        self._last_collapsed = False
        self._diff_html = {}  # maps a diff to html
        for d in diffs:
            self.add_diff(d)

    def add_diff(self, diff):
        html = self._make_table_for_diff(diff)
        if html:
            self._diff_table[diff] = html

    def _make_html_for_diff(self, diff):
        table = self._make_table_for_diff()
        wrong_things = diff.wrong_things_html_list()
        if not table and not wrong_things:  # all correct
            return None
        else:
            return table + wrong_things

    def make_table(self, diff):
        """Makes unique anchor prefixes so that multiple tables may exist
        on the same page without conflict."""
        self._make_prefix()
        diffs = diff.diff

        # set up iterator to wrap lines that exceed desired width
        if self._wrapcolumn:
            diffs = self._line_wrapper(diffs)

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
        """Returns one of the table, the diff, or None"""
        if not diff.outputs_match():
            self._last_collapsed = False
            table = self.make_table(diff)
            if self._last_collapsed:
                show_hide = self.SHOW_HIDE_INSTRUMENTATION
                table = '{0}{1}{0}'.format(show_hide, table)
            return self.FAILING_TEST_BLOCK.format(diff.name_id(),
                                                  diff.escaped_name(),
                                                  table)

    def _ordered_diffs(self, should_include):
        return sorted([diff for diff in self._diff_html.keys()
                       if should_include(diff)])

    def _make_some_summary(self, should_include):
        """Returns html and the number of rows in the table"""

        retval = '<table border="1">\n  <tr>\
<th>Test Number</th><th>Test Name</th><th>Value</th></tr>'
        num_rows = 0
        for diff in self._ordered_diffs(should_include):
            retval += diff.html_header_row()
            num_rows += 1
        retval += '</table>'
        return (retval, num_rows)

    def _make_header_summary(self, header, should_include):
        (html, num_rows) = self._make_some_summary(should_include)
        if num_rows > 0:
            return header + html
        else:
            return ''

    def _has_diff(self, diff):
        return diff in self._diff_table

    def _make_failed_summary(self):
        return self._make_header_summary(
            '<h3 style="color:red">Failed Tests</h3>',
            lambda diff: self._has_diff(diff))

    def _make_success_summary(self):
        return self._make_header_summary(
            '<h3 style="color:green">Passed Tests</h3>',
            lambda diff: not self._has_diff(diff))

    def tentative_score(self):
        """Returns total score and score as a percentage"""
        total_points = sum([t.test_points for t in self._diff_units])
        acquired_points = sum([t.test_points for t in self._diff_units
                               if t.is_correct()])
        percentage = float(acquired_points) / total_points * 100 \
            if total_points != 0 else 100
        return (acquired_points, percentage)

    def make_summary(self):
        (total, percentage) = self.tentative_score()
        retval = self._make_failed_summary() + self._make_success_summary()
        retval += self.TENTATIVE_SCORE_BLOCK.format(total, "%.2f" % percentage)
        return retval

    def make_whole_file(self):
        tables = [self._diff_table[diff]
                  for diff in self._diff_units
                  if self._has_diff(diff)]
        return self._file_template % dict(
            summary=self.make_summary(),
            legend=self._legend,
            table='<hr>\n'.join(tables))

    def _line_wrapper(self, diffs):
        return super(HTMLDiff, self)._line_wrapper(
            limit_revealed_lines_to(diffs, MAX_NUM_REVEALS))

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
