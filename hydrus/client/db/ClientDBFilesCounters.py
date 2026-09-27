import collections.abc
import sqlite3

from hydrus.core import HydrusConstants as HC
from hydrus.core import HydrusDBBase

from hydrus.client import ClientThreading
from hydrus.client.db import ClientDBDefinitionsCache
from hydrus.client.db import ClientDBModule
from hydrus.client.search import ClientNumberTest

class ClientDBFilesCounters( ClientDBModule.ClientDBModule ):
    
    def __init__(
        self,
        cursor: sqlite3.Cursor,
        modules_hashes_local_cache: ClientDBDefinitionsCache.ClientDBCacheLocalHashes
    ):
        
        self.modules_hashes_local_cache = modules_hashes_local_cache
        
        super().__init__( 'client files counters', cursor )
        
    
    def _GetInitialIndexGenerationDict( self ) -> dict:
        
        index_generation_dict = {}
        
        index_generation_dict[ 'main.file_counters' ] = [
            ( [ 'counter_id', 'count' ], False, 688 )
        ]
        
        return index_generation_dict
        
    
    def _GetInitialTableGenerationDict( self ) -> dict:
        
        # counter_id is the id of a counter in the options. we only keep rows for counts above zero
        return {
            'main.file_counters' : ( 'CREATE TABLE IF NOT EXISTS {} ( hash_id INTEGER, counter_id BLOB, count INTEGER, PRIMARY KEY ( hash_id, counter_id ) );', 688 )
        }
        
    
    def DeleteCounters( self, counter_ids: collections.abc.Collection[ bytes ] ):
        
        self._ExecuteMany( 'DELETE FROM file_counters WHERE counter_id = ?;', ( ( sqlite3.Binary( counter_id ), ) for counter_id in counter_ids ) )
        
    
    def GetCounts( self, hash: bytes ) -> dict[ bytes, int ]:
        
        hash_id = self.modules_hashes_local_cache.GetHashId( hash )
        
        return { bytes( counter_id ) : count for ( counter_id, count ) in self._Execute( 'SELECT counter_id, count FROM file_counters WHERE hash_id = ?;', ( hash_id, ) ) }
        
    
    def GetHashIdsFromCounts( self, counter_id: bytes, number_tests: list[ ClientNumberTest.NumberTest ], hash_ids: collections.abc.Collection[ int ], hash_ids_table_name: str, job_status: ClientThreading.JobStatus | None = None ) -> set[ int ]:
        
        cancelled_hook = None
        
        if job_status is not None:
            
            cancelled_hook = job_status.IsCancelled
            
        
        megalambda = ClientNumberTest.NumberTest.STATICCreateMegaLambda( number_tests )
        
        query = f'SELECT hash_id, count FROM {hash_ids_table_name} CROSS JOIN file_counters USING ( hash_id ) WHERE counter_id = ?;'
        
        hash_ids_to_counts = dict( self._ExecuteCancellable( query, ( sqlite3.Binary( counter_id ), ), cancelled_hook ) )
        
        # a file with no row has not been counted, so it is at zero
        return { hash_id for hash_id in hash_ids if megalambda( hash_ids_to_counts.get( hash_id, 0 ) ) }
        
    
    def GetTablesAndColumnsThatUseDefinitions( self, content_type: int ) -> list[ tuple[ str, str ] ]:
        
        tables_and_columns = []
        
        if content_type == HC.CONTENT_TYPE_HASH:
            
            tables_and_columns.append( ( 'file_counters', 'hash_id' ) )
            
        
        return tables_and_columns
        
    
    def IncrementCount( self, hash: bytes, counter_id: bytes, delta: int ):
        
        hash_id = self.modules_hashes_local_cache.GetHashId( hash )
        
        counter_id = sqlite3.Binary( counter_id )
        
        self._Execute( 'INSERT OR IGNORE INTO file_counters ( hash_id, counter_id, count ) VALUES ( ?, ?, ? );', ( hash_id, counter_id, 0 ) )
        
        self._Execute( 'UPDATE file_counters SET count = MAX( 0, count + ? ) WHERE hash_id = ? AND counter_id = ?;', ( delta, hash_id, counter_id ) )
        
        self._Execute( 'DELETE FROM file_counters WHERE hash_id = ? AND counter_id = ? AND count = 0;', ( hash_id, counter_id ) )
        
    
    def Repair( self, current_db_version, cursor_transaction_wrapper: HydrusDBBase.DBCursorTransactionWrapper ):
        
        # this table is not from an official db update, so a db from before it existed would otherwise get a scary 'missing tables' warning. we just quietly make it
        if not self._TableExists( 'main.file_counters' ):
            
            self.CreateInitialTables()
            self.CreateInitialIndices()
            
            cursor_transaction_wrapper.CommitAndBegin()
            
        
        super().Repair( current_db_version, cursor_transaction_wrapper )
        
    
    def SetCount( self, hash: bytes, counter_id: bytes, count: int ):
        
        hash_id = self.modules_hashes_local_cache.GetHashId( hash )
        
        counter_id = sqlite3.Binary( counter_id )
        
        if count <= 0:
            
            self._Execute( 'DELETE FROM file_counters WHERE hash_id = ? AND counter_id = ?;', ( hash_id, counter_id ) )
            
        else:
            
            self._Execute( 'INSERT OR REPLACE INTO file_counters ( hash_id, counter_id, count ) VALUES ( ?, ?, ? );', ( hash_id, counter_id, count ) )
            
        
    
