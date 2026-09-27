import unittest

from hydrus.core import HydrusExceptions

from hydrus.client.metadata import ClientTagsHandling
from hydrus.client.search import ClientSearchPredicate
from hydrus.client.search import ClientSearchQuickView

def tag_pred( tag, inclusive = True ):
    
    return ClientSearchPredicate.Predicate( ClientSearchPredicate.PREDICATE_TYPE_TAG, tag, inclusive )
    

class TestQuickView( unittest.TestCase ):
    
    def test_quick_view_search( self ):
        
        tag_autocomplete_options = ClientTagsHandling.TagAutocompleteOptions()
        
        tag_presets = [
            ( 'Colours', [ 'blue eyes', '-red hair' ] ),
            ( 'solo', [ 'solo', 'system:inbox' ] ),
            ( 'broken', [ 'system:presets nope' ] ),
            ( 'empty', [] )
        ]
        
        def search( text ):
            
            return ClientSearchQuickView.GetQuickViewSearch( text, tag_presets, tag_autocomplete_options )
            
        
        # a single tag
        self.assertEqual( search( '  blue   eyes ' ), ( 'blue eyes', [ tag_pred( 'blue eyes' ) ] ) )
        self.assertEqual( search( 'character:samus aran' ), ( 'character:samus aran', [ tag_pred( 'character:samus aran' ) ] ) )
        self.assertEqual( search( '-red hair' ), ( '-red hair', [ tag_pred( 'red hair', inclusive = False ) ] ) )
        
        # a preset, by its name, which is not case-sensitive and counts underscores as spaces
        colours = ( 'Colours', [ tag_pred( 'blue eyes' ), tag_pred( 'red hair', inclusive = False ) ] )
        
        self.assertEqual( search( 'colours' ), colours )
        self.assertEqual( search( 'COLOURS' ), colours )
        
        # or by the system predicate, like in a search box
        self.assertEqual( search( 'system:presets colours' ), colours )
        
        # a preset wins over a tag with the same name
        self.assertEqual( search( 'solo' ), ( 'solo', [ tag_pred( 'solo' ), ClientSearchPredicate.Predicate( ClientSearchPredicate.PREDICATE_TYPE_SYSTEM_INBOX ) ] ) )
        
        # things that cannot be searched
        for text in ( '', '   ', 'system:presets nope', 'broken', 'empty' ):
            
            with self.assertRaises( HydrusExceptions.VetoException, msg = text ):
                
                search( text )
                
            
        
    
