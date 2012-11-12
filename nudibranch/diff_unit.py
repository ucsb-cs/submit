import difflib
import xml.sax.saxutils

class DiffUnit( object ):
    '''Represents a single diff.
    Can be pickled safely.'''

    def __init__( self, correct, given, testNum, testName, testPoints ):
        self._tabsize = 8
        self.correct = correct
        self.given = given
        self.testNum = testNum
        self.testName = testName
        self.testPoints = testPoints
        self.diff = self._makeDiff()

    @staticmethod
    def escape( string ):
        return xml.sax.saxutils.escape( string, { '"': "&quot",
                                                  "'": "&apos;" } );

    def _makeDiff( self ):
        if not self.isCorrect():
            fromlines, tolines = self._tab_newline_replace( self.correct, self.given )
            return [ d for d in difflib._mdiff( fromlines, tolines ) ]
        
    def isCorrect( self ):
        return self.correct == self.given

    def __cmp__( self, other ):
        return self.testNum - other.testNum

    def escapedName( self ):
        return DiffUnit.escape( self.testName )

    def nameID( self ):
        return "{0}_{1}".format( int( self.testNum ),
                                 self.escapedName() )
    def htmlTestName( self ):
        if not self.isCorrect():
            return '<a href="#{0}" style="color:red">{1}</a>'.format( self.nameID(), 
                                                                      self.escapedName() )
        else:
            return '<pre style="color:green">{0}</pre>'.format( self.escapedName() )

    def htmlRow( self ):
        return '<tr><td>{0}</td><td>{1}</td><td>{2}</td></tr>'.format( self.testNum,
                                                                       self.htmlTestName(),
                                                                       self.testPoints )
    def _tab_newline_replace(self,fromlines,tolines):
        """Returns from/to line lists with tabs expanded and newlines removed.

        Instead of tab characters being replaced by the number of spaces
        needed to fill in to the next tab stop, this function will fill
        the space with tab characters.  This is done so that the difference
        algorithms can identify changes in a file when tabs are replaced by
        spaces and vice versa.  At the end of the HTML generation, the tab
        characters will be replaced with a nonbreakable space.
        """
        def expand_tabs(line):
            # hide real spaces
            line = line.replace(' ','\0')
            # expand tabs into spaces
            line = line.expandtabs(self._tabsize)
            # replace spaces from expanded tabs back into tab characters
            # (we'll replace them with markup after we do differencing)
            line = line.replace(' ','\t')
            return line.replace('\0',' ').rstrip('\n')
        fromlines = [expand_tabs(line) for line in fromlines]
        tolines = [expand_tabs(line) for line in tolines]
        return fromlines,tolines
