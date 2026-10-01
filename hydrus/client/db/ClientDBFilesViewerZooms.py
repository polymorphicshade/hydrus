import sqlite3

from hydrus.core import HydrusConstants as HC
from hydrus.core import HydrusDBBase

from hydrus.client.db import ClientDBDefinitionsCache
from hydrus.client.db import ClientDBModule

class ClientDBFilesViewerZooms( ClientDBModule.ClientDBModule ):
    
    def __init__(
        self,
        cursor: sqlite3.Cursor,
        modules_hashes_local_cache: ClientDBDefinitionsCache.ClientDBCacheLocalHashes
    ):
        
        self.modules_hashes_local_cache = modules_hashes_local_cache
        
        super().__init__( 'client files viewer zooms', cursor )
        
    
    def _GetInitialTableGenerationDict( self ) -> dict:
        
        # zoom is NULL when the file is at its normal default zoom, but has been panned
        # center_x and center_y are the point of the file in the middle of the window, as a fraction of its width and height, like zoom timestamps. NULL for both means centered
        return {
            'main.file_viewer_zooms' : ( 'CREATE TABLE IF NOT EXISTS {} ( hash_id INTEGER PRIMARY KEY, zoom REAL, center_x REAL, center_y REAL );', 688 )
        }
        
    
    def ClearAllViewerZooms( self ):
        
        # every file goes back to the normal default zoom
        self._Execute( 'DELETE FROM file_viewer_zooms;' )
        
    
    def GetNumViewerZooms( self ) -> int:
        
        ( num_zooms, ) = self._Execute( 'SELECT COUNT( * ) FROM file_viewer_zooms;' ).fetchone()
        
        return num_zooms
        
    
    def GetTablesAndColumnsThatUseDefinitions( self, content_type: int ) -> list[ tuple[ str, str ] ]:
        
        tables_and_columns = []
        
        if content_type == HC.CONTENT_TYPE_HASH:
            
            tables_and_columns.append( ( 'file_viewer_zooms', 'hash_id' ) )
            
        
        return tables_and_columns
        
    
    def GetViewerZoom( self, hash: bytes ) -> tuple[ float | None, tuple[ float, float ] | None ]:
        
        # ( zoom, center ). ( None, None ) for a file that is at its normal default zoom, centered
        hash_id = self.modules_hashes_local_cache.GetHashId( hash )
        
        result = self._Execute( 'SELECT zoom, center_x, center_y FROM file_viewer_zooms WHERE hash_id = ?;', ( hash_id, ) ).fetchone()
        
        if result is None:
            
            return ( None, None )
            
        
        ( zoom, center_x, center_y ) = result
        
        center = None if center_x is None or center_y is None else ( center_x, center_y )
        
        return ( zoom, center )
        
    
    def Repair( self, current_db_version, cursor_transaction_wrapper: HydrusDBBase.DBCursorTransactionWrapper ):
        
        # this table is not from an official db update, so a db from before it existed would otherwise get a scary 'missing tables' warning. we just quietly make it
        self.CreateInitialTables()
        
        column_names = [ name for ( cid, name, column_type, nullability, default_value, pk ) in self._Execute( 'PRAGMA table_info( file_viewer_zooms );' ).fetchall() ]
        
        for column_name in ( 'center_x', 'center_y' ):
            
            if column_name not in column_names:
                
                # the table is from before we saved where the file was panned to. what is in it stays centered
                self._Execute( f'ALTER TABLE file_viewer_zooms ADD COLUMN {column_name} REAL;' )
                
            
        
        cursor_transaction_wrapper.CommitAndBegin()
        
        super().Repair( current_db_version, cursor_transaction_wrapper )
        
    
    def SetViewerZoom( self, hash: bytes, zoom: float | None, center: tuple[ float, float ] | None = None ):
        
        # a None zoom is the normal default zoom, and a None center is centered. both None means the file goes back to normal
        hash_id = self.modules_hashes_local_cache.GetHashId( hash )
        
        if zoom is None and center is None:
            
            self._Execute( 'DELETE FROM file_viewer_zooms WHERE hash_id = ?;', ( hash_id, ) )
            
        else:
            
            ( center_x, center_y ) = ( None, None ) if center is None else center
            
            self._Execute( 'INSERT OR REPLACE INTO file_viewer_zooms ( hash_id, zoom, center_x, center_y ) VALUES ( ?, ?, ?, ? );', ( hash_id, zoom, center_x, center_y ) )
            
        
    
