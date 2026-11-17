import re

from qtpy import QtCore as QC
from qtpy import QtGui as QG
from qtpy import QtWidgets as QW

from hydrus.client import ClientGlobals as CG

# notes are markdown. you write them on an 'edit' tab and see them on a 'view' tab, and the media viewer shows them rendered
# a note written before this, as plain text, still looks the same: a line break is a line break, rather than markdown's usual joining of lines into one paragraph

FENCE_RE = re.compile( r'^\s*(```|~~~)' )

def RenderNotesAsMarkdown() -> bool:
    
    return CG.client_controller.new_options.GetBoolean( 'render_notes_as_markdown' )
    

def ConvertNoteToMarkdown( note: str ) -> str:
    
    # every line break is kept, as a markdown hard break, except in a fenced code block, which keeps its own
    lines = note.replace( '\r\n', '\n' ).split( '\n' )
    
    in_fence = False
    
    out_lines = []
    
    for ( i, line ) in enumerate( lines ):
        
        is_fence_line = FENCE_RE.match( line ) is not None
        
        if is_fence_line:
            
            in_fence = not in_fence
            
        
        next_line = lines[ i + 1 ] if i + 1 < len( lines ) else None
        
        hard_break = not in_fence and not is_fence_line and line.strip() != '' and next_line is not None and next_line.strip() != '' and FENCE_RE.match( next_line ) is None
        
        if hard_break and not line.endswith( '  ' ):
            
            line = line + '  '
            
        
        out_lines.append( line )
        
    
    return '\n'.join( out_lines )
    

def ConvertNoteToHTML( note: str ) -> str:
    
    document = QG.QTextDocument()
    
    document.setMarkdown( ConvertNoteToMarkdown( note ) )
    
    return document.toHtml()
    

def DrawNoteMarkdown( painter: QG.QPainter, x: int, y: int, width: int, note: str, colour: QG.QColor ) -> int:
    
    # draws the note rendered, in the painter's font and the colour, and returns how tall it was
    document = QG.QTextDocument()
    
    document.setDefaultFont( painter.font() )
    document.setDocumentMargin( 0 )
    document.setMarkdown( ConvertNoteToMarkdown( note ) )
    document.setTextWidth( width )
    
    context = QG.QAbstractTextDocumentLayout.PaintContext()
    
    context.palette.setColor( QG.QPalette.ColorRole.Text, colour )
    
    painter.save()
    
    try:
        
        painter.translate( x, y )
        
        document.documentLayout().draw( painter, context )
        
    finally:
        
        painter.restore()
        
    
    return int( document.size().height() )
    

class MarkdownNoteEditor( QW.QTabWidget ):
    
    # a note, with an 'edit' tab to write it in markdown and a 'view' tab that shows it rendered
    
    EDIT_TAB = 0
    VIEW_TAB = 1
    
    def __init__( self, parent: QW.QWidget, note: str = '' ):
        
        super().__init__( parent )
        
        # the note names are the tabs along the top of the dialog, so these go along the bottom
        self.setTabPosition( QW.QTabWidget.TabPosition.South )
        
        self._editor = QW.QPlainTextEdit( self )
        
        self._viewer = QW.QTextBrowser( self )
        
        self._viewer.setOpenExternalLinks( True )
        
        self.addTab( self._editor, 'edit' )
        self.addTab( self._viewer, 'view' )
        
        self.setFocusProxy( self._editor )
        
        self.setPlainText( note )
        
        self.currentChanged.connect( self._TabChanged )
        
    
    def _TabChanged( self, index: int ):
        
        if index == self.VIEW_TAB:
            
            self._UpdateView()
            
        else:
            
            self._editor.setFocus( QC.Qt.FocusReason.OtherFocusReason )
            
        
    
    def _UpdateView( self ):
        
        self._viewer.setMarkdown( ConvertNoteToMarkdown( self._editor.toPlainText() ) )
        
    
    def GetEditor( self ) -> QW.QPlainTextEdit:
        
        return self._editor
        
    
    def GetViewHTML( self ) -> str:
        
        self._UpdateView()
        
        return self._viewer.toHtml()
        
    
    def IsShowingView( self ) -> bool:
        
        return self.currentIndex() == self.VIEW_TAB
        
    
    def moveCursor( self, operation: QG.QTextCursor.MoveOperation ):
        
        self._editor.moveCursor( operation )
        
    
    def setPlainText( self, note: str ):
        
        self._editor.setPlainText( note )
        
        if self.IsShowingView():
            
            self._UpdateView()
            
        
    
    def ShowEdit( self ):
        
        self.setCurrentIndex( self.EDIT_TAB )
        
    
    def ShowView( self ):
        
        self.setCurrentIndex( self.VIEW_TAB )
        
        self._UpdateView()
        
    
    def toPlainText( self ) -> str:
        
        return self._editor.toPlainText()
        
        
        
