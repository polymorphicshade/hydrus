import sqlite3

from hydrus.core import HydrusConstants as HC
from hydrus.core import HydrusDBBase

from hydrus.client.db import ClientDBDefinitionsCache
from hydrus.client.db import ClientDBModule

class ClientDBFilesImageOverlays( ClientDBModule.ClientDBModule ):
    
    def __init__(
        self,
        cursor: sqlite3.Cursor,
        modules_hashes_local_cache: ClientDBDefinitionsCache.ClientDBCacheLocalHashes
    ):
        
        self.modules_hashes_local_cache = modules_hashes_local_cache
        
        super().__init__( 'client files image overlays', cursor )
        
    
    def _GetInitialTableGenerationDict( self ) -> dict:
        
        # the image a file has drawn over it in the media viewer. a file without one has no row
        # path is an image file on disk. opacity is 0-1. x, y, width, and height are fractions of the media viewer's size
        # locked is 1 when clicks go through it to the media viewer, and stretch is 1 when the image fills its box rather than keeping its shape
        return {
            'main.file_image_overlays' : ( 'CREATE TABLE IF NOT EXISTS {} ( hash_id INTEGER PRIMARY KEY, path TEXT, opacity REAL, x REAL, y REAL, width REAL, height REAL, locked INTEGER NOT NULL DEFAULT 0, stretch INTEGER NOT NULL DEFAULT 0 );', 688 )
        }
        
    
    def GetImageOverlay( self, hash: bytes ) -> tuple[ str, float, tuple[ float, float, float, float ], bool, bool ] | None:
        
        hash_id = self.modules_hashes_local_cache.GetHashId( hash )
        
        result = self._Execute( 'SELECT path, opacity, x, y, width, height, locked, stretch FROM file_image_overlays WHERE hash_id = ?;', ( hash_id, ) ).fetchone()
        
        if result is None:
            
            return None
            
        
        ( path, opacity, x, y, width, height, locked, stretch ) = result
        
        return ( path, opacity, ( x, y, width, height ), bool( locked ), bool( stretch ) )
        
    
    def GetTablesAndColumnsThatUseDefinitions( self, content_type: int ) -> list[ tuple[ str, str ] ]:
        
        tables_and_columns = []
        
        if content_type == HC.CONTENT_TYPE_HASH:
            
            tables_and_columns.append( ( 'file_image_overlays', 'hash_id' ) )
            
        
        return tables_and_columns
        
    
    def Repair( self, current_db_version, cursor_transaction_wrapper: HydrusDBBase.DBCursorTransactionWrapper ):
        
        # this table is not from an official db update, so a db from before it existed would otherwise get a scary 'missing tables' warning. we just quietly make it
        self.CreateInitialTables()
        
        cursor_transaction_wrapper.CommitAndBegin()
        
        super().Repair( current_db_version, cursor_transaction_wrapper )
        
    
    def SetImageOverlay( self, hash: bytes, image_overlay: tuple[ str, float, tuple[ float, float, float, float ], bool, bool ] | None ):
        
        # None takes it away
        hash_id = self.modules_hashes_local_cache.GetHashId( hash )
        
        if image_overlay is None:
            
            self._Execute( 'DELETE FROM file_image_overlays WHERE hash_id = ?;', ( hash_id, ) )
            
        else:
            
            ( path, opacity, ( x, y, width, height ), locked, stretch ) = image_overlay
            
            self._Execute( 'INSERT OR REPLACE INTO file_image_overlays ( hash_id, path, opacity, x, y, width, height, locked, stretch ) VALUES ( ?, ?, ?, ?, ?, ?, ?, ?, ? );', ( hash_id, path, opacity, x, y, width, height, int( locked ), int( stretch ) ) )
            
        
    
