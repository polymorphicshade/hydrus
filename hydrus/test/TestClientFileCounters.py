import unittest

from qtpy import QtWidgets as QW

from hydrus.core import HydrusExceptions
from hydrus.core import HydrusSerialisable

from hydrus.client import ClientConstants as CC
from hydrus.client.gui.media import ClientGUIMediaCounters
from hydrus.client.gui.metadata import ClientGUITagsToCounters

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
        
    
    def test_tags_to_counters_filter( self ):
        
        for ( text, result ) in [
            ( 'items:72', ( 'items', '72' ) ),
            ( 'items:*', ( 'items', '*' ) ),
            ( 'items', ( 'items', '*' ) ),
            ( 'items:', ( 'items', '*' ) ),
            ( ' Items : 7* ', ( 'items', '7*' ) ),
            ( '*:*', ( '*', '*' ) ),
            ( 'series:part:3', None ),
            ( 'items:many', None ),
            ( ':72', None ),
            ( '', None )
        ]:
            
            if result is None:
                
                with self.assertRaises( HydrusExceptions.VetoException, msg = text ):
                    
                    ClientGUITagsToCounters.ParseTagsToCountersFilter( text )
                    
                
            else:
                
                self.assertEqual( ClientGUITagsToCounters.ParseTagsToCountersFilter( text ), result, text )
                
            
        
        dialog = QW.QDialog()
        
        panel = ClientGUITagsToCounters.EditTagsToCountersPanel( dialog, CC.DEFAULT_LOCAL_TAG_SERVICE_KEY )
        
        with self.assertRaises( HydrusExceptions.VetoException ):
            
            panel.CheckValid()
            
        
        panel._tag_filter.setText( 'items:*' )
        
        self.assertEqual( panel.GetValue(), ( CC.DEFAULT_LOCAL_TAG_SERVICE_KEY, 'items', '*' ) )
        
        dialog.deleteLater()
        
    
