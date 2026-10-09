import sqlite3

from hydrus.core import HydrusConstants as HC
from hydrus.core import HydrusDBBase

from hydrus.client.db import ClientDBDefinitionsCache
from hydrus.client.db import ClientDBModule

class ClientDBFilesZoomTimestamps( ClientDBModule.ClientDBModule ):
    
    def __init__(
        self,
        cursor: sqlite3.Cursor,
        modules_hashes_local_cache: ClientDBDefinitionsCache.ClientDBCacheLocalHashes
    ):
        
        self.modules_hashes_local_cache = modules_hashes_local_cache
        
        super().__init__( 'client files zoom timestamps', cursor )
        
    
    def _GetInitialTableGenerationDict( self ) -> dict:
        
        # zoom is relative to the zoom that fits the file in the media viewer window, so it follows the window's size
        # zoom_is_relative is 0 for rows from before that, which are the plain zoom
        # center_x and center_y are the point of the file in the middle of the window, as a fraction of the file's width and height, so they follow the window's size too. they are NULL for rows from before we saved them, which are centered
        # rotation is how the file is turned, in degrees clockwise. it is NULL for rows from before we saved it, which leave the file turned however it is
        # these are 'position timestamps' in the ui
        return {
            'main.file_zoom_timestamps' : ( 'CREATE TABLE IF NOT EXISTS {} ( hash_id INTEGER, timestamp_ms INTEGER, zoom REAL, zoom_is_relative INTEGER NOT NULL DEFAULT 0, center_x REAL, center_y REAL, rotation INTEGER, PRIMARY KEY ( hash_id, timestamp_ms ) );', 688 )
        }
        
    
    def ClearAllZoomTimestamps( self ):
        
        self._Execute( 'DELETE FROM file_zoom_timestamps;' )
        
    
    def ClearZoomTimestamps( self, hashes ):
        
        # just these files' zoom timestamps go
        hash_ids = self.modules_hashes_local_cache.GetHashIds( hashes )
        
        self._ExecuteMany( 'DELETE FROM file_zoom_timestamps WHERE hash_id = ?;', ( ( hash_id, ) for hash_id in hash_ids ) )
        
    
    def GetNumFilesWithZoomTimestamps( self, hashes = None ) -> int:
        
        # every file, or just these files
        if hashes is None:
            
            ( num_files, ) = self._Execute( 'SELECT COUNT( DISTINCT hash_id ) FROM file_zoom_timestamps;' ).fetchone()
            
            return num_files
            
        
        hash_ids = self.modules_hashes_local_cache.GetHashIds( hashes )
        
        with self._MakeTemporaryIntegerTable( hash_ids, 'hash_id' ) as temp_hash_ids_table_name:
            
            ( num_files, ) = self._Execute( f'SELECT COUNT( DISTINCT hash_id ) FROM {temp_hash_ids_table_name} CROSS JOIN file_zoom_timestamps USING ( hash_id );' ).fetchone()
            
        
        return num_files
        
    
    def GetZoomTimestamps( self, hash: bytes ) -> list[ tuple[ int, float, bool, float | None, float | None, int | None ] ]:
        
        hash_id = self.modules_hashes_local_cache.GetHashId( hash )
        
        return [ ( timestamp_ms, zoom, bool( zoom_is_relative ), center_x, center_y, rotation ) for ( timestamp_ms, zoom, zoom_is_relative, center_x, center_y, rotation ) in self._Execute( 'SELECT timestamp_ms, zoom, zoom_is_relative, center_x, center_y, rotation FROM file_zoom_timestamps WHERE hash_id = ? ORDER BY timestamp_ms;', ( hash_id, ) ) ]
        
    
    def GetTablesAndColumnsThatUseDefinitions( self, content_type: int ) -> list[ tuple[ str, str ] ]:
        
        tables_and_columns = []
        
        if content_type == HC.CONTENT_TYPE_HASH:
            
            tables_and_columns.append( ( 'file_zoom_timestamps', 'hash_id' ) )
            
        
        return tables_and_columns
        
    
    def Repair( self, current_db_version, cursor_transaction_wrapper: HydrusDBBase.DBCursorTransactionWrapper ):
        
        # this table is not from an official db update, so a db from before it existed would otherwise get a scary 'missing tables' warning. we just quietly make it
        self.CreateInitialTables()
        
        column_names = [ name for ( cid, name, column_type, nullability, default_value, pk ) in self._Execute( 'PRAGMA table_info( file_zoom_timestamps );' ).fetchall() ]
        
        if 'zoom_is_relative' not in column_names:
            
            # the table is from before zoom timestamps followed the window size. what is in it is the plain zoom, which the media viewer converts the next time it opens the file
            self._Execute( 'ALTER TABLE file_zoom_timestamps ADD COLUMN zoom_is_relative INTEGER NOT NULL DEFAULT 0;' )
            
        
        for column_name in ( 'center_x', 'center_y' ):
            
            if column_name not in column_names:
                
                # the table is from before zoom timestamps saved where the file was panned to. what is in it stays centered
                self._Execute( f'ALTER TABLE file_zoom_timestamps ADD COLUMN {column_name} REAL;' )
                
            
        
        if 'rotation' not in column_names:
            
            # the table is from before they saved how the file was turned. what is in it leaves the file turned however it is
            self._Execute( 'ALTER TABLE file_zoom_timestamps ADD COLUMN rotation INTEGER;' )
            
        
        cursor_transaction_wrapper.CommitAndBegin()
        
        super().Repair( current_db_version, cursor_transaction_wrapper )
        
    
    def SetZoomTimestamps( self, hash: bytes, zoom_timestamps: list[ tuple[ int, float, float | None, float | None, int | None ] ] ):
        
        # ( timestamp_ms, zoom, center_x, center_y, rotation ). these are always relative zooms
        hash_id = self.modules_hashes_local_cache.GetHashId( hash )
        
        self._Execute( 'DELETE FROM file_zoom_timestamps WHERE hash_id = ?;', ( hash_id, ) )
        
        self._ExecuteMany( 'INSERT OR REPLACE INTO file_zoom_timestamps ( hash_id, timestamp_ms, zoom, zoom_is_relative, center_x, center_y, rotation ) VALUES ( ?, ?, ?, ?, ?, ?, ? );', ( ( hash_id, timestamp_ms, zoom, 1, center_x, center_y, rotation ) for ( timestamp_ms, zoom, center_x, center_y, rotation ) in zoom_timestamps ) )
        
    
