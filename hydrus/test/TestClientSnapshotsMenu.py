import os
import unittest

from unittest import mock

from qtpy import QtWidgets as QW

from hydrus.client import ClientGlobals as CG
from hydrus.client import ClientLocation
from hydrus.client import ClientSnapshots
from hydrus.client.gui.media import ClientGUIMediaMenus
from hydrus.client.media import ClientMediaList
from hydrus.client.media import ClientMediaSingle

from hydrus.test import HelperFunctions as HF

class TestSnapshotsMenu( unittest.TestCase ):
    
    def test_get_snapshot_hashes( self ):
        
        hash = os.urandom( 32 )
        other_hash = os.urandom( 32 )
        snapshot_hashes = [ os.urandom( 32 ), os.urandom( 32 ) ]
        
        location_context = ClientLocation.LocationContext.STATICCreateSimple( os.urandom( 32 ) )
        
        # no snapshots domain yet means no snapshots, and no need to ask the db
        with mock.patch.object( ClientSnapshots, 'GetSnapshotsLocationContext', return_value = None ), mock.patch.object( CG.client_controller, 'Read' ) as read:
            
            self.assertEqual( ClientSnapshots.GetSnapshotHashes( hash ), [] )
            self.assertEqual( ClientSnapshots.GetSnapshotHashesForFiles( [ hash, other_hash ] ), [] )
            
            read.assert_not_called()
            
        
        with mock.patch.object( ClientSnapshots, 'GetSnapshotsLocationContext', return_value = location_context ), mock.patch.object( CG.client_controller, 'Read', return_value = snapshot_hashes ) as read:
            
            self.assertEqual( ClientSnapshots.GetSnapshotHashes( hash ), snapshot_hashes )
            
            read.assert_called_once_with( 'file_snapshots_for_files', [ hash ], location_context )
            
            read.reset_mock()
            
            # many files are one db job, in the order given
            self.assertEqual( ClientSnapshots.GetSnapshotHashesForFiles( ( other_hash, hash ) ), snapshot_hashes )
            
            read.assert_called_once_with( 'file_snapshots_for_files', [ other_hash, hash ], location_context )
            
            read.reset_mock()
            
            # and no files need no db job
            self.assertEqual( ClientSnapshots.GetSnapshotHashesForFiles( [] ), [] )
            
            read.assert_not_called()
            
        
    
    def test_menu_item( self ):
        
        window = QW.QWidget()
        
        menu = QW.QMenu( window )
        
        hash = os.urandom( 32 )
        
        focused_media = ClientMediaSingle.MediaSingle( HF.GetFakeMediaResult( hash ) )
        
        snapshot_hashes = [ os.urandom( 32 ) for i in range( 3 ) ]
        
        location_context = ClientLocation.LocationContext.STATICCreateSimple( os.urandom( 32 ) )
        
        # nothing focused, no item
        ClientGUIMediaMenus.AddSnapshotsMenuItem( menu, None )
        
        self.assertEqual( menu.actions(), [] )
        
        # a file with no snapshots gets no item either
        with mock.patch.object( ClientSnapshots, 'GetSnapshotHashesForFiles', return_value = [] ) as get_snapshot_hashes:
            
            ClientGUIMediaMenus.AddSnapshotsMenuItem( menu, focused_media, [ focused_media ] )
            
            get_snapshot_hashes.assert_called_once_with( [ hash ] )
            
        
        self.assertEqual( menu.actions(), [] )
        
        # a file with some gets one, which opens them in a new page
        with mock.patch.object( ClientSnapshots, 'GetSnapshotHashesForFiles', return_value = snapshot_hashes ), mock.patch.object( ClientSnapshots, 'GetSnapshotsLocationContext', return_value = location_context ), mock.patch.object( CG.client_controller, 'pub' ) as pub:
            
            ClientGUIMediaMenus.AddSnapshotsMenuItem( menu, focused_media, [ focused_media ] )
            
            actions = menu.actions()
            
            self.assertEqual( [ action.text() for action in actions ], [ 'snapshots (3)' ] )
            
            actions[0].trigger()
            
            pub.assert_called_once_with( 'new_page_query', location_context, initial_hashes = snapshot_hashes, page_name = 'snapshots' )
            
        
        window.deleteLater()
        
    
    def test_menu_item_many_selected( self ):
        
        window = QW.QWidget()
        
        menu = QW.QMenu( window )
        
        hashes = [ os.urandom( 32 ) for i in range( 4 ) ]
        
        medias = [ ClientMediaSingle.MediaSingle( HF.GetFakeMediaResult( hash ) ) for hash in hashes ]
        
        # a collection's files count too, in their place
        collection = ClientMediaList.MediaCollection( ClientLocation.LocationContext.STATICCreateSimple( os.urandom( 32 ) ), [ media.GetMediaResult() for media in medias[ 1 : 3 ] ] )
        
        ordered_selected_media = [ medias[3], collection, medias[0] ]
        
        expected_hashes = [ hashes[3] ] + [ media.GetHash() for media in collection.GetFlatMedia() ] + [ hashes[0] ]
        
        snapshot_hashes = [ os.urandom( 32 ) for i in range( 7 ) ]
        
        location_context = ClientLocation.LocationContext.STATICCreateSimple( os.urandom( 32 ) )
        
        # none of them have any, no item
        with mock.patch.object( ClientSnapshots, 'GetSnapshotHashesForFiles', return_value = [] ) as get_snapshot_hashes:
            
            ClientGUIMediaMenus.AddSnapshotsMenuItem( menu, medias[0], ordered_selected_media )
            
            get_snapshot_hashes.assert_called_once_with( expected_hashes )
            
        
        self.assertEqual( menu.actions(), [] )
        
        # some of them do: one item for all of them, whichever is focused, and one page with them all, file by file
        with mock.patch.object( ClientSnapshots, 'GetSnapshotHashesForFiles', return_value = snapshot_hashes ) as get_snapshot_hashes, mock.patch.object( ClientSnapshots, 'GetSnapshotsLocationContext', return_value = location_context ), mock.patch.object( CG.client_controller, 'pub' ) as pub:
            
            ClientGUIMediaMenus.AddSnapshotsMenuItem( menu, medias[0], ordered_selected_media )
            
            actions = menu.actions()
            
            self.assertEqual( [ action.text() for action in actions ], [ 'snapshots of selected (7)' ] )
            
            actions[0].trigger()
            
            self.assertEqual( get_snapshot_hashes.call_args_list, [ mock.call( expected_hashes ), mock.call( expected_hashes ) ] )
            
            pub.assert_called_once_with( 'new_page_query', location_context, initial_hashes = snapshot_hashes, page_name = 'snapshots' )
            
        
        window.deleteLater()
        
    
