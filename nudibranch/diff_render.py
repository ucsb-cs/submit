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
  pageLoaded( 'diff_table_div' );
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

def limitRevealedLinesTo( diffs, limit ):
    numReveals = 0
    retval = []
    for fromdata, todata, flag in diffs:
        if flag and ( '\0-' in fromdata[ 1 ] or '\0^' in fromdata[ 1 ] ):
            numReveals += 1
        if numReveals > MAX_NUM_REVEALS:
            trun = ( '...', '<<OUTPUT TRUNCATED>>' )
            retval.append( ( trun, trun, False ) )
            break
        retval.append( ( fromdata, todata, flag ) )
    return retval


# gets points at which changes begin
def changeSameStartingPoints( flaglist ):
    changePoints = []
    samePoints = []
    inChange = False

    if flaglist and not flaglist[ 0 ]:
        samePoints.append( 0 )

    for x, flag in enumerate( flaglist ):
        if flag and not inChange:
            changePoints.append( x )
            inChange = True
        elif not flag and inChange:
            samePoints.append( x )
            inChange = False

    return ( changePoints, samePoints )

MAX_NUM_REVEALS = 3
class HTMLDiff( difflib.HtmlDiff ):
    def __init__( self, diffs = [] ):
        super( HTMLDiff, self ).__init__( wrapcolumn = 50 )
        self._legend = _legend
        self._table_template = _table_template
        self._file_template = _file_template
        self._diff_units = []
        self._last_collapsed = False
        self._diff_table = {} # maps a diff to a table
        for d in diffs:
            self.add_diff( d )

    def add_diff( self, diff ):
        self._diff_units.append( diff )
        self._diff_table[ diff ] = self._make_table_for_diff( diff )

    def make_table( self, diff ):
        # make unique anchor prefixes so that multiple tables may exist
        # on the same page without conflict.
        self._make_prefix()
        diffs = diff.diff

        # set up iterator to wrap lines that exceed desired width
        if self._wrapcolumn:
            diffs = self._line_wrapper(diffs)

        # collect up from/to lines and flags into lists (also format the lines)
        fromlist,tolist,flaglist = self._collect_lines(diffs)

        # process change flags, generating middle column of next anchors/links
        fromlist,tolist,flaglist,next_href,next_id = self._convert_flags(
            fromlist,tolist,flaglist,False,5)

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
                s.append( fmt % (next_id[i],next_href[i],fromlist[i],
                                           next_href[i],tolist[i]))
        fromdesc = 'Correct Output'
        todesc = 'Your Output'
        header_row = '<thead><tr>%s%s%s%s</tr></thead>' % (
            '<th class="diff_next"><br /></th>',
            '<th colspan="2" class="diff_header">%s</th>' % fromdesc,
            '<th class="diff_next"><br /></th>',
            '<th colspan="2" class="diff_header">%s</th>' % todesc)

        table = self._table_template % dict(
            data_rows=''.join(s),
            header_row=header_row,
            prefix=self._prefix[1])

        return table.replace('\0+','<span class="diff_add">'). \
                     replace('\0-','<span class="diff_sub">'). \
                     replace('\0^','<span class="diff_chg">'). \
                     replace('\1','</span>'). \
                     replace('\t','&nbsp;')

    def _format_line(self,side,flag,linenum,text):
        """Returns HTML markup of "from" / "to" text lines

        side -- 0 or 1 indicating "from" or "to" text
        flag -- indicates if difference on line
        linenum -- line number (used for line number column)
        text -- line text to be marked up
        """
        try:
            linenum = '%d' % linenum
            id = ' id="%s%s"' % (self._prefix[side],linenum)
        except TypeError:
            # handle blank lines where linenum is '>' or ''
            id = ''
        # replace those things that would get confused with HTML symbols
        text=text.replace("&","&amp;").replace(">","&gt;").replace("<","&lt;")

        # make space non-breakable so they don't get compressed or line wrapped
        text = text.replace(' ','&nbsp;').rstrip()

        color = ''
        if '\0^' in text or '\0+' in text or '\0-' in text:
            color = ';background-color:{0}'
            if side == 0:
                color = color.format( '#ffe6e6' )
            else:
                color = color.format( '#e3ffe3' )
        return '<td class="diff_header"%s>%s</td><td style="white-space:nowrap%s">%s</td>' \
               % (id,linenum,color,text)

    # returns either the table for the diff, or None
    def _make_table_for_diff( self, diff ):
        if not diff.isCorrect():
            self._last_collapsed = False
            table = self.make_table( diff )
            if self._last_collapsed:
                showHide = """
<p><a href="#" onclick="showAll( 'difflib_chg_{0}_top' ); return false;">Show All</a>
    <a href="#" onclick="hideAll( 'difflib_chg_{0}_top' ); return false;">Hide All</a></p>""".format( self._prefix[ 1 ] )
                table = '{0}{1}{0}'.format( showHide, table )
            return \
                '<h3 id="{0}" style="color:red">{1}</h3>\n{2}'.format( diff.nameID(),
                                                                       diff.escapedName(),
                                                                       table )
                
    
    # returns html and the number of rows in the table
    def _make_some_summary( self, shouldInclude ):
        retval = '<table border="1">\n  <tr><th>Test Number</th><th>Test Name</th><th>Value</th></tr>'
        numRows = 0
        for diff in sorted( [ diff for diff in self._diff_units if shouldInclude( diff ) ] ):
            retval += diff.htmlRow()
            numRows += 1
        retval += '</table>'
        return ( retval, numRows )

    def _make_header_summary( self, header, shouldInclude ):
        ( html, numRows ) = self._make_some_summary( shouldInclude )
        if numRows > 0:
            return header + html
        else:
            return ''

    def _has_diff( self, diff ):
        return diff in self._diff_table and self._diff_table[ diff ] is not None

    def _make_failed_summary( self ):
        return self._make_header_summary( '<h3 style="color:red">Failed Tests</h3>',
                                          lambda diff: self._has_diff( diff ) )

    def _make_success_summary( self ):
        return self._make_header_summary( '<h3 style="color:green">Passed Tests</h3>',
                                          lambda diff: not self._has_diff( diff ) )

    # returns
    # -total score
    # -total score as a percentage
    def tentative_score( self ):
        totalPoints = sum( [ t.testPoints for t in self._diff_units ] )
        acquiredPoints = sum( [ t.testPoints for t in self._diff_units
                                if t.isCorrect() ] )
        return ( acquiredPoints,
                 float( acquiredPoints ) / totalPoints * 100 if totalPoints != 0 else 100 )

    def make_summary( self ):
        ( total, percentage ) = self.tentative_score()
        retval = self._make_failed_summary() + self._make_success_summary()
        retval += '<li><ul>Tentative total score: {0}</ul><ul>Tentative percentage score: {1}</ul></li>\n'.format( total, "%.2f" % percentage )
        return retval

    def make_whole_file( self ):
        tables = [ self._diff_table[ diff ]
                   for diff in self._diff_units
                   if self._has_diff( diff ) ]
        return self._file_template % dict(
            summary = self.make_summary(),
            legend = self._legend,
            table = '<hr>\n'.join( tables ) )

    def _line_wrapper( self, diffs ):
        return super( HTMLDiff, self )._line_wrapper( limitRevealedLinesTo( diffs, MAX_NUM_REVEALS ) )

    def _make_prefix( self ):
        sameprefix = "same{0}_".format( HTMLDiff._default_prefix )
        super( HTMLDiff, self )._make_prefix()
        self._prefix.append( sameprefix )

    def _convert_flags( self, fromlist, tolist, flaglist, context, numlines ):
        """Handles making inline links in the document."""

        # all anchor names will be generated using the unique "to" prefix
        toprefix = self._prefix[ 1 ]
        sameprefix = self._prefix[ 2 ]

        # process change flags, generating middle column of next anchors/links
        next_id = ['']*len(flaglist)
        next_href = ['']*len(flaglist)
        ( changePositions, samePositions ) = changeSameStartingPoints( flaglist )
        changePositionsSet = set( changePositions )

        for numChange, changePos in enumerate( changePositions[ : -1 ] ):
            next_id[ changePos ] = ' id="difflib_chg_{0}_{1}"'.format( toprefix, numChange )
            next_href[ changePos ] = '<a href="#difflib_chg_{0}_{1}">n</a>'.format( toprefix, numChange + 1 )

        for sameBlock, sameStartPos in enumerate( samePositions ):
            samePos = sameStartPos
            while samePos < len( flaglist ) and samePos not in changePositionsSet:
                next_id[ samePos ] = ' id="difflib_same_{0}{1}_{2}"'.format( sameprefix,
                                                                             sameBlock, 
                                                                             samePos - sameStartPos + 1 )
                samePos += 1
            if samePos - sameStartPos > 4:
                next_href[ sameStartPos + 2 ] = '<a href="#" onclick="showHideRows( this ); return false;">h</a>'
                self._last_collapsed = True

        # check for cases where there is no content to avoid exceptions
        if not flaglist:
            flaglist = [False]
            next_id = ['']
            next_href = ['']
            last = 0
            if context:
                fromlist = ['<td></td><td>&nbsp;No Differences Found&nbsp;</td>']
                tolist = fromlist
            else:
                fromlist = tolist = ['<td></td><td>&nbsp;Empty File&nbsp;</td>']

        # redo the last link to link to the top
        if changePositions:
            pos = changePositions[ -1 ]
            next_id[ pos ] = ' id="difflib_chg_{0}_{1}"'.format( toprefix, len( changePositions ) - 1 )
            next_href[ pos ] = '<a href="#difflib_chg_{0}_top">t</a>'.format( toprefix )

        return fromlist,tolist,flaglist,next_href,next_id

