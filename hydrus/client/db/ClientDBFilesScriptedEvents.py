import sqlite3

from hydrus.core import HydrusConstants as HC
from hydrus.core import HydrusDBBase

from hydrus.client.db import ClientDBDefinitionsCache
from hydrus.client.db import ClientDBModule

class ClientDBFilesScriptedEvents( ClientDBModule.ClientDBModule ):
    
    def __init__(
        self,
        cursor: sqlite3.Cursor,
        modules_hashes_local_cache: ClientDBDefinitionsCache.ClientDBCacheLocalHashes
    ):
        
        self.modules_hashes_local_cache = modules_hashes_local_cache
        
        super().__init__( 'client files scripted events', cursor )
        
    
    def _GetInitialTableGenerationDict( self ) -> dict:
        
        # a shell command to run when playback gets to timestamp_ms. a point can have several
        return {
            'main.file_scripted_events' : ( 'CREATE TABLE IF NOT EXISTS {} ( hash_id INTEGER, timestamp_ms INTEGER, command TEXT, PRIMARY KEY ( hash_id, timestamp_ms, command ) );', 688 )
        }
        
    
    def GetScriptedEvents( self, hash: bytes ) -> list[ tuple[ int, str ] ]:
        
        hash_id = self.modules_hashes_local_cache.GetHashId( hash )
        
        return self._Execute( 'SELECT timestamp_ms, command FROM file_scripted_events WHERE hash_id = ? ORDER BY timestamp_ms, command;', ( hash_id, ) ).fetchall()
        
    
    def GetTablesAndColumnsThatUseDefinitions( self, content_type: int ) -> list[ tuple[ str, str ] ]:
        
        tables_and_columns = []
        
        if content_type == HC.CONTENT_TYPE_HASH:
            
            tables_and_columns.append( ( 'file_scripted_events', 'hash_id' ) )
            
        
        return tables_and_columns
        
    
    def Repair( self, current_db_version, cursor_transaction_wrapper: HydrusDBBase.DBCursorTransactionWrapper ):
        
        # this table is not from an official db update, so a db from before it existed would otherwise get a scary 'missing tables' warning. we just quietly make it
        self.CreateInitialTables()
        
        cursor_transaction_wrapper.CommitAndBegin()
        
        super().Repair( current_db_version, cursor_transaction_wrapper )
        
    
    def SetScriptedEvents( self, hash: bytes, scripted_events: list[ tuple[ int, str ] ] ):
        
        hash_id = self.modules_hashes_local_cache.GetHashId( hash )
        
        self._Execute( 'DELETE FROM file_scripted_events WHERE hash_id = ?;', ( hash_id, ) )
        
        self._ExecuteMany( 'INSERT OR IGNORE INTO file_scripted_events ( hash_id, timestamp_ms, command ) VALUES ( ?, ?, ? );', ( ( hash_id, timestamp_ms, command ) for ( timestamp_ms, command ) in scripted_events ) )
        
    
