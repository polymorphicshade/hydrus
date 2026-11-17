import unittest

from unittest import mock

from qtpy import QtCore as QC
from qtpy import QtGui as QG
from qtpy import QtWidgets as QW

from hydrus.client import ClientGlobals as CG
from hydrus.client.gui import ClientGUINotesMarkdown
from hydrus.client.gui.canvas import ClientGUICanvasHoverFrames
from hydrus.client.gui.panels import ClientGUIScrolledPanelsEdit

class TestNotesMarkdown( unittest.TestCase ):
    
    def _SetOption( self, name, value ):
        
        new_options = CG.client_controller.new_options
        
        original_value = new_options.GetBoolean( name )
        
        self.addCleanup( new_options.SetBoolean, name, original_value )
        
        new_options.SetBoolean( name, value )
        
    
    def test_line_breaks( self ):
        
        # a plain text note keeps its line breaks
        self.assertEqual( ClientGUINotesMarkdown.ConvertNoteToMarkdown( 'one\ntwo\nthree' ), 'one  \ntwo  \nthree' )
        
        # paragraphs stay paragraphs, and a line that already breaks is left alone
        self.assertEqual( ClientGUINotesMarkdown.ConvertNoteToMarkdown( 'one\n\ntwo  \nthree' ), 'one\n\ntwo  \nthree' )
        
        # code keeps its own
        self.assertEqual( ClientGUINotesMarkdown.ConvertNoteToMarkdown( 'look:\n```\na\nb\n```\nafter' ), 'look:\n```\na\nb\n```\nafter' )
        
        self.assertEqual( ClientGUINotesMarkdown.ConvertNoteToMarkdown( '' ), '' )
        
    
    def test_html( self ):
        
        html = ClientGUINotesMarkdown.ConvertNoteToHTML( '**big** day\nline two\n\n- a\n- b' )
        
        self.assertIn( 'big', html )
        self.assertNotIn( '**', html )
        self.assertIn( '<li', html )
        
        document = QG.QTextDocument()
        
        document.setHtml( html )
        
        # the line break stayed a line break
        self.assertIn( 'big day\nline two', document.toPlainText() )
        
    
    def test_drawing( self ):
        
        image = QG.QImage( 400, 400, QG.QImage.Format.Format_ARGB32 )
        
        image.fill( QG.QColor( 255, 255, 255 ) )
        
        painter = QG.QPainter( image )
        
        try:
            
            one_line_height = ClientGUINotesMarkdown.DrawNoteMarkdown( painter, 10, 10, 300, 'one', QG.QColor( 0, 0, 0 ) )
            three_line_height = ClientGUINotesMarkdown.DrawNoteMarkdown( painter, 10, 100, 300, 'one\ntwo\nthree', QG.QColor( 0, 0, 0 ) )
            
        finally:
            
            painter.end()
            
        
        self.assertGreater( one_line_height, 0 )
        self.assertGreater( three_line_height, one_line_height * 2 )
        
        # it drew something
        self.assertNotEqual( len( { image.pixel( x, y ) for x in range( 10, 100 ) for y in range( 10, 10 + one_line_height ) } ), 1 )
        
    
    def test_editor( self ):
        
        editor = ClientGUINotesMarkdown.MarkdownNoteEditor( None, '**big** day' )
        
        try:
            
            self.assertEqual( editor.count(), 2 )
            self.assertEqual( ( editor.tabText( 0 ), editor.tabText( 1 ) ), ( 'edit', 'view' ) )
            self.assertFalse( editor.IsShowingView() )
            self.assertIs( editor.focusProxy(), editor.GetEditor() )
            
            self.assertEqual( editor.toPlainText(), '**big** day' )
            
            # the view shows it rendered
            editor.ShowView()
            
            self.assertTrue( editor.IsShowingView() )
            self.assertEqual( editor._viewer.toPlainText(), 'big day' )
            
            # and keeps up while it is showing
            editor.setPlainText( '# title' )
            
            self.assertEqual( editor._viewer.toPlainText(), 'title' )
            self.assertEqual( editor.toPlainText(), '# title' )
            
            editor.ShowEdit()
            
            self.assertFalse( editor.IsShowingView() )
            
            editor.moveCursor( QG.QTextCursor.MoveOperation.End )
            
            self.assertEqual( editor.GetEditor().textCursor().position(), len( '# title' ) )
            
        finally:
            
            editor.deleteLater()
            
        
    
    def test_notes_dialog( self ):
        
        self._SetOption( 'notes_start_on_view_tab', True )
        
        panel = ClientGUIScrolledPanelsEdit.EditFileNotesPanel( None, { 'a note' : '**hi**', 'b note' : 'second' }, 'a note' )
        
        try:
            
            first = panel._notebook.widget( 0 )
            
            self.assertIsInstance( first, ClientGUINotesMarkdown.MarkdownNoteEditor )
            
            # a note with something in it starts on the view
            self.assertTrue( first.IsShowingView() )
            
            first.setPlainText( 'changed' )
            
            ( names_to_notes, deletee_names ) = panel.GetValue()
            
            self.assertEqual( names_to_notes, { 'a note' : 'changed', 'b note' : 'second' } )
            
            # an empty one starts on edit
            panel._AddNotePanel( 'new', '' )
            
            self.assertFalse( panel._notebook.currentWidget().IsShowingView() )
            
        finally:
            
            panel.deleteLater()
            
        
        self._SetOption( 'notes_start_on_view_tab', False )
        
        panel = ClientGUIScrolledPanelsEdit.EditFileNotesPanel( None, { 'a note' : '**hi**' }, 'a note' )
        
        try:
            
            self.assertFalse( panel._notebook.widget( 0 ).IsShowingView() )
            
        finally:
            
            panel.deleteLater()
            
        
    
    def test_media_viewer_hover( self ):
        
        parent = QW.QWidget()
        
        try:
            
            self._SetOption( 'render_notes_as_markdown', True )
            
            note_panel = ClientGUICanvasHoverFrames.NotePanel( parent, 'name', '**hi**\nthere', True )
            
            self.assertEqual( note_panel._note_text.textFormat(), QC.Qt.TextFormat.MarkdownText )
            self.assertEqual( note_panel._note_text.text(), '**hi**  \nthere' )
            
            self._SetOption( 'render_notes_as_markdown', False )
            
            note_panel = ClientGUICanvasHoverFrames.NotePanel( parent, 'name', '**hi**\nthere', True )
            
            self.assertEqual( note_panel._note_text.textFormat(), QC.Qt.TextFormat.PlainText )
            self.assertEqual( note_panel._note_text.text(), '**hi**\nthere' )
            
        finally:
            
            parent.deleteLater()
            
            
            
            
