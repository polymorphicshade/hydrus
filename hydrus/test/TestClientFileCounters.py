import unittest

from qtpy import QtWidgets as QW

from hydrus.core import HydrusSerialisable

from hydrus.client.gui.media import ClientGUIMediaCounters

class TestFileCounters( unittest.TestCase ):
    
    def test_manage_file_counters_panel( self ):
        
        watched = HydrusSerialisable.IdAndName( b'w' * 32, 'watched' )
        liked = HydrusSerialisable.IdAndName( b'l' * 32, 'Liked' )
        skipped = HydrusSerialisable.IdAndName( b's' * 32, 'skipped' )
        
        # skipped has no row, so it is at zero
        counter_ids_to_counts = { watched.object_id : 3, liked.object_id : 1 }
        
        dialog = QW.QDialog()
        
        panel = ClientGUIMediaCounters.ManageFileCountersPanel( dialog, [ watched, liked, skipped ], counter_ids_to_counts )
        
        # in name order, with the file's counts
        self.assertEqual( [ ( counter.name, spinbox.value() ) for ( counter, label, spinbox ) in panel._rows ], [ ( 'Liked', 1 ), ( 'skipped', 0 ), ( 'watched', 3 ) ] )
        
        # nothing changed, nothing to save
        self.assertEqual( panel.GetValue(), {} )
        
        spinboxes = { counter.name : spinbox for ( counter, label, spinbox ) in panel._rows }
        
        spinboxes[ 'watched' ].setValue( 10 )
        spinboxes[ 'skipped' ].setValue( 2 )
        spinboxes[ 'Liked' ].setValue( 1 )
        
        self.assertEqual( panel.GetValue(), { watched.object_id : 10, skipped.object_id : 2 } )
        
        spinboxes[ 'watched' ].setValue( 0 )
        
        self.assertEqual( panel.GetValue(), { watched.object_id : 0, skipped.object_id : 2 } )
        
        # no negative counts
        spinboxes[ 'skipped' ].setValue( -5 )
        
        self.assertEqual( spinboxes[ 'skipped' ].value(), 0 )
        
        # the filter hides the others
        panel._filter.setText( 'KED' )
        
        self.assertEqual( [ counter.name for ( counter, label, spinbox ) in panel._rows if not spinbox.isHidden() ], [ 'Liked' ] )
        
        panel._filter.setText( '' )
        
        self.assertEqual( len( [ counter.name for ( counter, label, spinbox ) in panel._rows if not spinbox.isHidden() ] ), 3 )
        
        dialog.deleteLater()
        
    
