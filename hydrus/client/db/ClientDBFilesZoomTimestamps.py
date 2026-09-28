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
        return {
            'main.file_zoom_timestamps' : ( 'CREATE TABLE IF NOT EXISTS {} ( hash_id INTEGER, timestamp_ms INTEGER, zoom REAL, zoom_is_relative INTEGER NOT NULL DEFAULT 0, PRIMARY KEY ( hash_id, timestamp_ms ) );', 688 )
        }
        
    
    def GetZoomTimestamps( self, hash: bytes ) -> list[ tuple[ int, float, bool ] ]:
        
        hash_id = self.modules_hashes_local_cache.GetHashId( hash )
        
        return [ ( timestamp_ms, zoom, bool( zoom_is_relative ) ) for ( timestamp_ms, zoom, zoom_is_relative ) in self._Execute( 'SELECT timestamp_ms, zoom, zoom_is_relative FROM file_zoom_timestamps WHERE hash_id = ? ORDER BY timestamp_ms;', ( hash_id, ) ) ]
        
    
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
            
        
        cursor_transaction_wrapper.CommitAndBegin()
        
        super().Repair( current_db_version, cursor_transaction_wrapper )
        
    
    def SetZoomTimestamps( self, hash: bytes, zoom_timestamps: list[ tuple[ int, float ] ] ):
        
        # these are always relative zooms
        hash_id = self.modules_hashes_local_cache.GetHashId( hash )
        
        self._Execute( 'DELETE FROM file_zoom_timestamps WHERE hash_id = ?;', ( hash_id, ) )
        
        self._ExecuteMany( 'INSERT OR REPLACE INTO file_zoom_timestamps ( hash_id, timestamp_ms, zoom, zoom_is_relative ) VALUES ( ?, ?, ?, ? );', ( ( hash_id, timestamp_ms, zoom, 1 ) for ( timestamp_ms, zoom ) in zoom_timestamps ) )
        
    
