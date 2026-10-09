import sqlite3

from hydrus.core import HydrusConstants as HC
from hydrus.core import HydrusDBBase

from hydrus.client.db import ClientDBDefinitionsCache
from hydrus.client.db import ClientDBModule

class ClientDBFilesPlaybackFreezes( ClientDBModule.ClientDBModule ):
    
    def __init__(
        self,
        cursor: sqlite3.Cursor,
        modules_hashes_local_cache: ClientDBDefinitionsCache.ClientDBCacheLocalHashes
    ):
        
        self.modules_hashes_local_cache = modules_hashes_local_cache
        
        super().__init__( 'client files playback freezes', cursor )
        
    
    def _GetInitialTableGenerationDict( self ) -> dict:
        
        # when playback gets to timestamp_ms, it holds that frame for duration_ms. a point has one freeze
        return {
            'main.file_playback_freezes' : ( 'CREATE TABLE IF NOT EXISTS {} ( hash_id INTEGER, timestamp_ms INTEGER, duration_ms INTEGER, PRIMARY KEY ( hash_id, timestamp_ms ) );', 688 )
        }
        
    
    def GetPlaybackFreezes( self, hash: bytes ) -> list[ tuple[ int, int ] ]:
        
        hash_id = self.modules_hashes_local_cache.GetHashId( hash )
        
        return self._Execute( 'SELECT timestamp_ms, duration_ms FROM file_playback_freezes WHERE hash_id = ? ORDER BY timestamp_ms;', ( hash_id, ) ).fetchall()
        
    
    def GetTablesAndColumnsThatUseDefinitions( self, content_type: int ) -> list[ tuple[ str, str ] ]:
        
        tables_and_columns = []
        
        if content_type == HC.CONTENT_TYPE_HASH:
            
            tables_and_columns.append( ( 'file_playback_freezes', 'hash_id' ) )
            
        
        return tables_and_columns
        
    
    def Repair( self, current_db_version, cursor_transaction_wrapper: HydrusDBBase.DBCursorTransactionWrapper ):
        
        # this table is not from an official db update, so a db from before it existed would otherwise get a scary 'missing tables' warning. we just quietly make it
        self.CreateInitialTables()
        
        cursor_transaction_wrapper.CommitAndBegin()
        
        super().Repair( current_db_version, cursor_transaction_wrapper )
        
    
    def SetPlaybackFreezes( self, hash: bytes, freezes: list[ tuple[ int, int ] ] ):
        
        hash_id = self.modules_hashes_local_cache.GetHashId( hash )
        
        self._Execute( 'DELETE FROM file_playback_freezes WHERE hash_id = ?;', ( hash_id, ) )
        
        self._ExecuteMany( 'INSERT OR REPLACE INTO file_playback_freezes ( hash_id, timestamp_ms, duration_ms ) VALUES ( ?, ?, ? );', ( ( hash_id, timestamp_ms, duration_ms ) for ( timestamp_ms, duration_ms ) in freezes ) )
        
