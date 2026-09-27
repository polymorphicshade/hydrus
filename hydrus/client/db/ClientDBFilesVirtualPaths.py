import collections.abc
import sqlite3

from hydrus.core import HydrusConstants as HC
from hydrus.core import HydrusDBBase

from hydrus.client import ClientThreading
from hydrus.client.db import ClientDBDefinitionsCache
from hydrus.client.db import ClientDBModule
from hydrus.client.metadata import ClientVirtualPaths

class ClientDBFilesVirtualPaths( ClientDBModule.ClientDBModule ):
    
    def __init__(
        self,
        cursor: sqlite3.Cursor,
        modules_hashes_local_cache: ClientDBDefinitionsCache.ClientDBCacheLocalHashes
    ):
        
        self.modules_hashes_local_cache = modules_hashes_local_cache
        
        super().__init__( 'client files virtual paths', cursor )
        
    
    def _GetInitialIndexGenerationDict( self ) -> dict:
        
        index_generation_dict = {}
        
        index_generation_dict[ 'main.file_virtual_paths' ] = [
            ( [ 'path' ], False, 688 )
        ]
        
        return index_generation_dict
        
    
    def _GetInitialTableGenerationDict( self ) -> dict:
        
        # paths are stored normalised, so we can compare them directly
        return {
            'main.file_virtual_paths' : ( 'CREATE TABLE IF NOT EXISTS {} ( hash_id INTEGER, path TEXT, PRIMARY KEY ( hash_id, path ) );', 688 )
        }
        
    
    def GetAllPaths( self ) -> list[ str ]:
        
        return sorted( self._STS( self._Execute( 'SELECT DISTINCT path FROM file_virtual_paths;' ) ) )
        
    
    def GetHashIdsFromPattern( self, pattern: str, hash_ids_table_name: str, job_status: ClientThreading.JobStatus | None = None ) -> set[ int ]:
        
        cancelled_hook = None
        
        if job_status is not None:
            
            cancelled_hook = job_status.IsCancelled
            
        
        # there are far fewer paths than files, so we find the paths that match in python and then fetch their files
        pattern_regex = ClientVirtualPaths.ConvertVirtualPathPatternToRegex( pattern )
        
        matching_paths = [ path for path in self.GetAllPaths() if ClientVirtualPaths.VirtualPathMatchesPattern( path, pattern_regex ) ]
        
        hash_ids = set()
        
        for path in matching_paths:
            
            query = f'SELECT hash_id FROM {hash_ids_table_name} CROSS JOIN file_virtual_paths USING ( hash_id ) WHERE path = ?;'
            
            hash_ids.update( self._STI( self._ExecuteCancellable( query, ( path, ), cancelled_hook ) ) )
            
        
        return hash_ids
        
    
    def GetPaths( self, hashes: collections.abc.Collection[ bytes ] ) -> dict[ bytes, list[ str ] ]:
        
        hashes_to_paths = {}
        
        for hash in hashes:
            
            hash_id = self.modules_hashes_local_cache.GetHashId( hash )
            
            hashes_to_paths[ hash ] = sorted( self._STI( self._Execute( 'SELECT path FROM file_virtual_paths WHERE hash_id = ?;', ( hash_id, ) ) ) )
            
        
        return hashes_to_paths
        
    
    def GetTablesAndColumnsThatUseDefinitions( self, content_type: int ) -> list[ tuple[ str, str ] ]:
        
        tables_and_columns = []
        
        if content_type == HC.CONTENT_TYPE_HASH:
            
            tables_and_columns.append( ( 'file_virtual_paths', 'hash_id' ) )
            
        
        return tables_and_columns
        
    
    def HasPaths( self ) -> bool:
        
        return self._Execute( 'SELECT 1 FROM file_virtual_paths LIMIT 1;' ).fetchone() is not None
        
    
    def Repair( self, current_db_version, cursor_transaction_wrapper: HydrusDBBase.DBCursorTransactionWrapper ):
        
        # this table is not from an official db update, so a db from before it existed would otherwise get a scary 'missing tables' warning. we just quietly make it
        if not self._TableExists( 'main.file_virtual_paths' ):
            
            self.CreateInitialTables()
            self.CreateInitialIndices()
            
            cursor_transaction_wrapper.CommitAndBegin()
            
        
        super().Repair( current_db_version, cursor_transaction_wrapper )
        
    
    def SetPaths( self, hashes_to_paths: dict[ bytes, collections.abc.Collection[ str ] ] ):
        
        for ( hash, paths ) in hashes_to_paths.items():
            
            hash_id = self.modules_hashes_local_cache.GetHashId( hash )
            
            paths = { ClientVirtualPaths.NormaliseVirtualPath( path ) for path in paths }
            
            paths = { path for path in paths if ClientVirtualPaths.GetVirtualPathError( path ) is None }
            
            self._Execute( 'DELETE FROM file_virtual_paths WHERE hash_id = ?;', ( hash_id, ) )
            
            self._ExecuteMany( 'INSERT OR IGNORE INTO file_virtual_paths ( hash_id, path ) VALUES ( ?, ? );', ( ( hash_id, path ) for path in paths ) )
            
        
    
