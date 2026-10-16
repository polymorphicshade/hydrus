import sqlite3

from hydrus.core import HydrusConstants as HC
from hydrus.core import HydrusDBBase

from hydrus.client.db import ClientDBDefinitionsCache
from hydrus.client.db import ClientDBModule
from hydrus.client.media import ClientMediaScreenZooms

class ClientDBFilesViewerZooms( ClientDBModule.ClientDBModule ):
    
    def __init__(
        self,
        cursor: sqlite3.Cursor,
        modules_hashes_local_cache: ClientDBDefinitionsCache.ClientDBCacheLocalHashes
    ):
        
        self.modules_hashes_local_cache = modules_hashes_local_cache
        
        super().__init__( 'client files viewer zooms', cursor )
        
    
    def _GetInitialTableGenerationDict( self ) -> dict:
        
        # a file has a zoom for each screen it was zoomed or panned on. screen_name is the monitor's name, and '' is the one for any screen without its own, which every zoom was from before they were per screen
        # zoom is NULL when the file is at its normal default zoom, but has been panned
        # center_x and center_y are the point of the file in the middle of the window, as a fraction of its width and height, like zoom timestamps. NULL for both means centered
        # a screen's row with NULL for all three is the default zoom on that screen, rather than the one for any screen
        return {
            'main.file_viewer_zooms' : ( 'CREATE TABLE IF NOT EXISTS {} ( hash_id INTEGER, screen_name TEXT, zoom REAL, center_x REAL, center_y REAL, PRIMARY KEY ( hash_id, screen_name ) );', 688 )
        }
        
    
    def _MigrateToScreenZooms( self ):
        
        column_names = [ name for ( cid, name, column_type, nullability, default_value, pk ) in self._Execute( 'PRAGMA table_info( file_viewer_zooms );' ).fetchall() ]
        
        if 'screen_name' in column_names:
            
            return
            
        
        for column_name in ( 'center_x', 'center_y' ):
            
            if column_name not in column_names:
                
                # the table is from before we saved where the file was panned to. what is in it stays centered
                self._Execute( f'ALTER TABLE file_viewer_zooms ADD COLUMN {column_name} REAL;' )
                
            
        
        # the table is from before zooms were per screen. what is in it becomes the zoom for any screen, so files open like they did until they are zoomed on a screen
        self._Execute( 'ALTER TABLE file_viewer_zooms RENAME TO file_viewer_zooms_old;' )
        
        self.CreateInitialTables()
        
        self._Execute( 'INSERT INTO file_viewer_zooms ( hash_id, screen_name, zoom, center_x, center_y ) SELECT hash_id, ?, zoom, center_x, center_y FROM file_viewer_zooms_old;', ( ClientMediaScreenZooms.ANY_SCREEN, ) )
        
        self._Execute( 'DROP TABLE file_viewer_zooms_old;' )
        
    
    def ClearAllViewerZooms( self ):
        
        # every file goes back to the normal default zoom, on every screen
        self._Execute( 'DELETE FROM file_viewer_zooms;' )
        
    
    def ClearViewerZooms( self, hashes ):
        
        # just these files go back to the normal default zoom, centered, on every screen
        hash_ids = self.modules_hashes_local_cache.GetHashIds( hashes )
        
        self._ExecuteMany( 'DELETE FROM file_viewer_zooms WHERE hash_id = ?;', ( ( hash_id, ) for hash_id in hash_ids ) )
        
    
    def GetNumViewerZooms( self, hashes = None ) -> int:
        
        # how many files have a zoom or pan saved on some screen. every file's, or just these files'
        if hashes is None:
            
            ( num_zooms, ) = self._Execute( 'SELECT COUNT( DISTINCT hash_id ) FROM file_viewer_zooms WHERE zoom IS NOT NULL OR center_x IS NOT NULL;' ).fetchone()
            
            return num_zooms
            
        
        hash_ids = self.modules_hashes_local_cache.GetHashIds( hashes )
        
        with self._MakeTemporaryIntegerTable( hash_ids, 'hash_id' ) as temp_hash_ids_table_name:
            
            ( num_zooms, ) = self._Execute( f'SELECT COUNT( DISTINCT hash_id ) FROM {temp_hash_ids_table_name} CROSS JOIN file_viewer_zooms USING ( hash_id ) WHERE zoom IS NOT NULL OR center_x IS NOT NULL;' ).fetchone()
            
        
        return num_zooms
        
    
    def GetTablesAndColumnsThatUseDefinitions( self, content_type: int ) -> list[ tuple[ str, str ] ]:
        
        tables_and_columns = []
        
        if content_type == HC.CONTENT_TYPE_HASH:
            
            tables_and_columns.append( ( 'file_viewer_zooms', 'hash_id' ) )
            
        
        return tables_and_columns
        
    
    def GetViewerScreenZooms( self, hash: bytes ) -> dict[ str, ClientMediaScreenZooms.ScreenZoom ]:
        
        # screen_name -> ( zoom, center ), for each screen the file has one for, and '' for any screen
        hash_id = self.modules_hashes_local_cache.GetHashId( hash )
        
        screen_zooms = {}
        
        for ( screen_name, zoom, center_x, center_y ) in self._Execute( 'SELECT screen_name, zoom, center_x, center_y FROM file_viewer_zooms WHERE hash_id = ?;', ( hash_id, ) ):
            
            center = None if center_x is None or center_y is None else ( center_x, center_y )
            
            screen_zooms[ screen_name ] = ( zoom, center )
            
        
        return screen_zooms
        
    
    def GetViewerZoom( self, hash: bytes, screen_name: str = ClientMediaScreenZooms.ANY_SCREEN ) -> ClientMediaScreenZooms.ScreenZoom:
        
        # ( zoom, center ) on this screen, or the one for any screen if it has none of its own. ( None, None ) for a file that is at its normal default zoom, centered
        return ClientMediaScreenZooms.GetScreenZoom( self.GetViewerScreenZooms( hash ), screen_name )
        
    
    def Repair( self, current_db_version, cursor_transaction_wrapper: HydrusDBBase.DBCursorTransactionWrapper ):
        
        # this table is not from an official db update, so a db from before it existed would otherwise get a scary 'missing tables' warning. we just quietly make it
        self.CreateInitialTables()
        
        self._MigrateToScreenZooms()
        
        cursor_transaction_wrapper.CommitAndBegin()
        
        super().Repair( current_db_version, cursor_transaction_wrapper )
        
    
    def SetViewerZoom( self, hash: bytes, zoom: float | None, center: tuple[ float, float ] | None = None, screen_name: str = ClientMediaScreenZooms.ANY_SCREEN ):
        
        # a None zoom is the normal default zoom, and a None center is centered
        # both None for any screen means the file goes back to normal. for a screen, it is at the default zoom there, whatever it has for any screen
        hash_id = self.modules_hashes_local_cache.GetHashId( hash )
        
        if zoom is None and center is None and screen_name == ClientMediaScreenZooms.ANY_SCREEN:
            
            self._Execute( 'DELETE FROM file_viewer_zooms WHERE hash_id = ? AND screen_name = ?;', ( hash_id, screen_name ) )
            
        else:
            
            ( center_x, center_y ) = ( None, None ) if center is None else center
            
            self._Execute( 'INSERT OR REPLACE INTO file_viewer_zooms ( hash_id, screen_name, zoom, center_x, center_y ) VALUES ( ?, ?, ?, ?, ? );', ( hash_id, screen_name, zoom, center_x, center_y ) )
            
        
    
