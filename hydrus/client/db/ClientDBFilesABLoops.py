import sqlite3

from hydrus.core import HydrusConstants as HC
from hydrus.core import HydrusDBBase

from hydrus.client.db import ClientDBDefinitionsCache
from hydrus.client.db import ClientDBModule

class ClientDBFilesABLoops( ClientDBModule.ClientDBModule ):
    
    def __init__(
        self,
        cursor: sqlite3.Cursor,
        modules_hashes_local_cache: ClientDBDefinitionsCache.ClientDBCacheLocalHashes
    ):
        
        self.modules_hashes_local_cache = modules_hashes_local_cache
        
        super().__init__( 'client files ab loops', cursor )
        
    
    def _GetInitialTableGenerationDict( self ) -> dict:
        
        # A-B repeat loops saved on a file, to put back on later. a loop that starts at the start has a_ms 0
        return {
            'main.file_ab_loops' : ( 'CREATE TABLE IF NOT EXISTS {} ( hash_id INTEGER, a_ms INTEGER, b_ms INTEGER, PRIMARY KEY ( hash_id, a_ms, b_ms ) );', 688 )
        }
        
    
    def GetABLoops( self, hash: bytes ) -> list[ tuple[ int, int ] ]:
        
        hash_id = self.modules_hashes_local_cache.GetHashId( hash )
        
        return self._Execute( 'SELECT a_ms, b_ms FROM file_ab_loops WHERE hash_id = ? ORDER BY a_ms, b_ms;', ( hash_id, ) ).fetchall()
        
    
    def GetTablesAndColumnsThatUseDefinitions( self, content_type: int ) -> list[ tuple[ str, str ] ]:
        
        tables_and_columns = []
        
        if content_type == HC.CONTENT_TYPE_HASH:
            
            tables_and_columns.append( ( 'file_ab_loops', 'hash_id' ) )
            
        
        return tables_and_columns
        
    
    def Repair( self, current_db_version, cursor_transaction_wrapper: HydrusDBBase.DBCursorTransactionWrapper ):
        
        # this table is not from an official db update, so a db from before it existed would otherwise get a scary 'missing tables' warning. we just quietly make it
        self.CreateInitialTables()
        
        cursor_transaction_wrapper.CommitAndBegin()
        
        super().Repair( current_db_version, cursor_transaction_wrapper )
        
    
    def SetABLoops( self, hash: bytes, ab_loops: list[ tuple[ int, int ] ] ):
        
        hash_id = self.modules_hashes_local_cache.GetHashId( hash )
        
        self._Execute( 'DELETE FROM file_ab_loops WHERE hash_id = ?;', ( hash_id, ) )
        
        self._ExecuteMany( 'INSERT OR IGNORE INTO file_ab_loops ( hash_id, a_ms, b_ms ) VALUES ( ?, ?, ? );', ( ( hash_id, a_ms, b_ms ) for ( a_ms, b_ms ) in ab_loops ) )
        
        
