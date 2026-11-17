from qtpy import QtWidgets as QW

from hydrus.client import ClientConstants as CC
from hydrus.client.gui import ClientGUIFunctions
from hydrus.client.gui import QtPorting as QP
from hydrus.client.gui.panels.options import ClientGUIOptionsPanelBase
from hydrus.client.gui.widgets import ClientGUICommon

class NotesPanel( ClientGUIOptionsPanelBase.OptionsPagePanel ):
    
    def __init__( self, parent, new_options ):
        
        super().__init__( parent )
        
        self._new_options = new_options
        
        self._start_note_editing_at_end = QW.QCheckBox( self )
        self._start_note_editing_at_end.setToolTip( ClientGUIFunctions.WrapToolTip( 'Otherwise, start the text cursor at the start of the document.' ) )
        
        self._copy_notes_quick_click_only_copies_text = QW.QCheckBox( self )
        self._copy_notes_quick_click_only_copies_text.setToolTip( ClientGUIFunctions.WrapToolTip( 'Otherwise, copy title and text.' ) )
        
        self._render_notes_as_markdown = QW.QCheckBox( self )
        self._render_notes_as_markdown.setToolTip( ClientGUIFunctions.WrapToolTip( 'Notes are markdown, like **bold**, # headings, - lists, and [links](https://example.com). The media viewer shows them rendered. A line break is always a line break, so notes written as plain text look the same. Otherwise, the media viewer shows notes as they are written.' ) )
        
        self._notes_start_on_view_tab = QW.QCheckBox( self )
        self._notes_start_on_view_tab.setToolTip( ClientGUIFunctions.WrapToolTip( 'In the notes dialog, each note has an \'edit\' tab and a \'view\' tab, which shows it rendered. Otherwise, notes start on \'edit\'. An empty note always starts on \'edit\'.' ) )
        
        #
        
        self._start_note_editing_at_end.setChecked( self._new_options.GetBoolean( 'start_note_editing_at_end' ) )
        self._copy_notes_quick_click_only_copies_text.setChecked( self._new_options.GetBoolean( 'copy_notes_quick_click_only_copies_text' ) )
        self._render_notes_as_markdown.setChecked( self._new_options.GetBoolean( 'render_notes_as_markdown' ) )
        self._notes_start_on_view_tab.setChecked( self._new_options.GetBoolean( 'notes_start_on_view_tab' ) )
        
        #
        
        vbox = QP.VBoxLayout()
        
        rows = []
        
        rows.append( ( 'Start editing notes with the text cursor at the end of the document: ', self._start_note_editing_at_end ) )
        rows.append( ( 'When middle-clicking a note hover, only copy the text: ', self._copy_notes_quick_click_only_copies_text ) )
        rows.append( ( 'Show notes as rendered markdown in the media viewer: ', self._render_notes_as_markdown ) )
        rows.append( ( 'In the notes dialog, start notes on the \'view\' tab: ', self._notes_start_on_view_tab ) )
        
        gridbox = ClientGUICommon.WrapInGrid( self, rows )
        
        QP.AddToLayout( vbox, gridbox, CC.FLAGS_EXPAND_SIZER_PERPENDICULAR )
        vbox.addStretch( 0 )
        
        self.setLayout( vbox )
        
    
    def UpdateOptions( self ):
        
        self._new_options.SetBoolean( 'start_note_editing_at_end', self._start_note_editing_at_end.isChecked() )
        self._new_options.SetBoolean( 'copy_notes_quick_click_only_copies_text', self._copy_notes_quick_click_only_copies_text.isChecked() )
        self._new_options.SetBoolean( 'render_notes_as_markdown', self._render_notes_as_markdown.isChecked() )
        self._new_options.SetBoolean( 'notes_start_on_view_tab', self._notes_start_on_view_tab.isChecked() )
        
    
