sameIDRegex = /difflib_same_same(\d+)_(\d+)_(\d+)/; // table, block, line
savedRows = {};
SHOW_HIDE_HREF = "showHideRows( this ); return false;";

// can either be from the left or right a element
function getTR( a ) {
    return a.parentNode.parentNode;
}

// gets the overall HTML table with the given link
function getTableBody( a ) {
    return getTR( a ).parentNode;
}

function realTD( a ) {
    var p = a.parentNode;
    if ( p.id !== undefined && p.id.match( sameIDRegex ) ) {
	return p;
    } else {
	var childNodes = p.parentNode.childNodes;
	for (var childID = 0; childID < childNodes.length; childID++) {
	    var child = childNodes[childID];
	    if ( child.id !== undefined && child.id.match( sameIDRegex ) ) {
		return child;
	    }
	}
	return null;
    }
}

// takes a td element with a definite block id
// returns:
// -the table number
// -the block number
function tableBlockNum( td ) {
    var match = sameIDRegex.exec( td.id );
    var retval = new Array( 2 );
    retval[ 0 ] = match[ 1 ];
    retval[ 1 ] = match[ 2 ];
    return retval;
}

// gets all the tr elements for a given same block id
function sameBlockTR( tbody, tableNum, blockNum ) {
    var retval = new Array();
    var a = null;
    var lineNum = 1;
    var getA = function( lineNum ) {
	var id = 'difflib_same_same' + tableNum + '_' + blockNum + '_' + lineNum;
	return document.getElementById( id );
    };
    while ( ( a = getA( lineNum ) ) ) {
	retval.push( a.parentNode );
	lineNum++;
    }
    return retval;
}

// returns:
// 0-left a element for showing/hiding rows
// 1-left td holding line number
// 2-left content TD
// 3-right a element for showing/hiding rows
// 4-right td holding line number
// 5-right content TD
function neededRowElems( row ) {
    var retval = new Array( 6 );
    var all = row.getElementsByTagName( "td" );
    retval[ 0 ] = all[ 0 ].getElementsByTagName( "a" )[ 0 ];
    retval[ 1 ] = all[ 1 ];
    retval[ 2 ] = all[ 2 ];

    retval[ 3 ] = all[ 3 ].getElementsByTagName( "a" )[ 0 ];
    retval[ 4 ] = all[ 4 ];
    retval[ 5 ] = all[ 5 ];

    return retval;
}

function getRowID( row ) {
    return row.getElementsByTagName( "td" )[ 0 ].id;
}

// saves in an array of:
// -left line number
// -left content
// -right line number
// -right content
function saveRow( id, elems ) {
    var toSave = new Array( 4 );
    toSave[ 0 ] = elems[ 1 ].innerHTML;
    toSave[ 1 ] = elems[ 2 ].innerHTML;
    toSave[ 2 ] = elems[ 4 ].innerHTML;
    toSave[ 3 ] = elems[ 5 ].innerHTML;
    savedRows[ id ] = toSave;
}

function restoreRow( id, elems ) {
    var saved = savedRows[ id ];
    elems[ 1 ].innerHTML = saved[ 0 ];
    elems[ 2 ].innerHTML = saved[ 1 ];
    elems[ 4 ].innerHTML = saved[ 2 ];
    elems[ 5 ].innerHTML = saved[ 3 ];
    delete savedRows[ id ];
}

function lineNumber( row, index ) {
    return row.getElementsByTagName( "td" )[ index ].innerHTML;
}

function hiddenLineSpan( block, lineIndex ) {
    return lineNumber( block[ 2 ], lineIndex ) + "-" + lineNumber( block[ block.length - 3 ], lineIndex );
}

function hideBlock( block ) {
    // save contents for restoration if we show later
    var elems = neededRowElems( block[ 2 ] );
    saveRow( getRowID( block[ 2 ] ), elems );

    // update the links so that we will show now
    elems[ 0 ].innerHTML = 's';
    elems[ 3 ].innerHTML = 's';

    // update the line numbers of the rows
    elems[ 1 ].innerHTML = hiddenLineSpan( block, 1 );
    elems[ 4 ].innerHTML = hiddenLineSpan( block, 4 );

    // update the content of the rows
    var newContent = '&lt;&lt;SAME CONTENT HIDDEN&gt;&gt;';
    elems[ 2 ].innerHTML = newContent;
    elems[ 5 ].innerHTML = newContent;

    // hide the remaining rows
    var x = 3;
    while ( x < block.length - 2 ) {
	block[ x ].style.display = 'none';
	x++;
    }
}

function showBlock( block ) {
    // restore content
    var savedElems = savedRows[ getRowID( block[ 2 ] ) ];
    var elems = neededRowElems( block[ 2 ] );
    restoreRow( getRowID( block[ 2 ] ), elems );

    // restore links
    elems[ 0 ].innerHTML = 'h';
    elems[ 3 ].innerHTML = 'h';

    // display remaining rows
    var x = 3;
    while ( x < block.length - 2 ) {
	block[ x ].style.display = '';
	x++;
    }
}

function showHideRows( a ) {
    var tableBlockID = tableBlockNum( realTD( a ) );
    var block = sameBlockTR( getTableBody( a ),
			     tableBlockID[ 0 ],
			     tableBlockID[ 1 ] );
    if ( savedRows.hasOwnProperty( getRowID( block[ 2 ] ) ) ) {
	showBlock( block );
    } else {
	hideBlock( block );
    }
}

// hides all the rows it can find
function pageLoaded() {
    toggleShowHide( 'h', document );
}

function toggleShowHide( initialStatus, source ) {
    var elems = source.getElementsByTagName( 'a' );
    for (var aID = 0; aID < elems.length; aID++) {
	var a = elems[aID];
	if ( a.innerHTML == initialStatus ) {
	    showHideRows( a );
	}
    }
}

function showAll( tableID ) {
    toggleShowHide( 's', document.getElementById( tableID ) );
}

function hideAll( tableID ) {
    toggleShowHide( 'h', document.getElementById( tableID ) );
}
