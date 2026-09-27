import unittest

from hydrus.core import HydrusSerialisable

from hydrus.client import ClientOptions
from hydrus.client.metadata import ClientTagsHandling
from hydrus.client.search import ClientSearchParseSystemPredicates
from hydrus.client.search import ClientSearchPredicate
from hydrus.client.search import ClientSearchTagPresets

def tag_pred( tag, inclusive = True ):
    
    return ClientSearchPredicate.Predicate( ClientSearchPredicate.PREDICATE_TYPE_TAG, tag, inclusive )
    

def preset_pred( name ):
    
    return ClientSearchPredicate.Predicate( ClientSearchPredicate.PREDICATE_TYPE_SYSTEM_TAG_PRESET, name )
    

class TestTagPresets( unittest.TestCase ):
    
    def test_adding_entries( self ):
        
        tag_presets = []
        
        # a new preset is made
        tag_presets = ClientSearchTagPresets.AddEntriesToTagPreset( tag_presets, 'My  Preset', [ 'Blue Eyes', 'blue eyes', ' ' ] )
        
        self.assertEqual( tag_presets, [ ( 'My Preset', [ 'blue eyes' ] ) ] )
        
        # names are not case-sensitive, and underscores are spaces
        tag_presets = ClientSearchTagPresets.AddEntriesToTagPreset( tag_presets, 'my_preset', [ 'blue eyes', '-red  hair' ] )
        
        self.assertEqual( tag_presets, [ ( 'My Preset', [ 'blue eyes', '-red hair' ] ) ] )
        
        tag_presets = ClientSearchTagPresets.AddEntriesToTagPreset( tag_presets, 'other', [ 'system:inbox' ] )
        
        self.assertEqual( tag_presets, [ ( 'My Preset', [ 'blue eyes', '-red hair' ] ), ( 'other', [ 'system:inbox' ] ) ] )
        
        self.assertEqual( ClientSearchTagPresets.GetTagPreset( tag_presets, 'MY_PRESET' ), ( 'My Preset', [ 'blue eyes', '-red hair' ] ) )
        self.assertIsNone( ClientSearchTagPresets.GetTagPreset( tag_presets, 'nope' ) )
        
    
    def test_entries_to_predicates( self ):
        
        tag_autocomplete_options = ClientTagsHandling.TagAutocompleteOptions()
        
        def convert( entry ):
            
            return ClientSearchTagPresets.ConvertTagPresetEntryToPredicate( entry, tag_autocomplete_options )
            
        
        self.assertEqual( convert( 'blue eyes' ), tag_pred( 'blue eyes' ) )
        self.assertEqual( convert( 'character:samus aran' ), tag_pred( 'character:samus aran' ) )
        self.assertEqual( convert( '-red hair' ), tag_pred( 'red hair', inclusive = False ) )
        
        self.assertEqual( convert( 'blue*' ), ClientSearchPredicate.Predicate( ClientSearchPredicate.PREDICATE_TYPE_WILDCARD, 'blue*' ) )
        self.assertEqual( convert( 'character:*' ), ClientSearchPredicate.Predicate( ClientSearchPredicate.PREDICATE_TYPE_NAMESPACE, 'character' ) )
        
        self.assertEqual( convert( 'system:inbox' ), ClientSearchPredicate.Predicate( ClientSearchPredicate.PREDICATE_TYPE_SYSTEM_INBOX ) )
        
        self.assertIsNone( convert( '' ) )
        
    
    def test_expanding( self ):
        
        tag_autocomplete_options = ClientTagsHandling.TagAutocompleteOptions()
        
        tag_presets = [
            ( 'Colours', [ 'blue eyes', '-red hair' ] ),
            ( 'big', [ 'system:presets colours', 'tall', 'blue eyes' ] ),
            ( 'loop a', [ 'a', 'system:presets loop b' ] ),
            ( 'loop b', [ 'b', 'system:presets loop a' ] )
        ]
        
        def expand( predicates ):
            
            return ClientSearchTagPresets.ExpandTagPresetPredicates( predicates, tag_presets, tag_autocomplete_options )
            
        
        # other predicates are left alone, and a preset becomes its entries
        self.assertEqual( expand( [ tag_pred( 'solo' ), preset_pred( 'colours' ) ] ), ( [ tag_pred( 'solo' ), tag_pred( 'blue eyes' ), tag_pred( 'red hair', inclusive = False ) ] , [] ) )
        
        # a preset can hold another. an entry that turns up twice goes in once
        self.assertEqual( expand( [ preset_pred( 'big' ) ] ), ( [ tag_pred( 'blue eyes' ), tag_pred( 'red hair', inclusive = False ), tag_pred( 'tall' ) ], [] ) )
        
        # but presets that hold each other do not go round forever
        self.assertEqual( expand( [ preset_pred( 'loop_a' ) ] ), ( [ tag_pred( 'a' ), tag_pred( 'b' ) ], [] ) )
        
        # a preset that does not exist is reported
        self.assertEqual( expand( [ preset_pred( 'nope' ), tag_pred( 'solo' ) ] ), ( [ tag_pred( 'solo' ) ], [ 'nope' ] ) )
        
    
    def test_predicate( self ):
        
        for ( text, name ) in [
            ( 'system:presets my_preset', 'my_preset' ),
            ( 'system:preset My Preset', 'my preset' ),
            ( 'system:presets: colours', 'colours' )
        ]:
            
            ( predicate, ) = ClientSearchParseSystemPredicates.ParseSystemPredicateStringsToPredicates( [ text ] )
            
            self.assertEqual( predicate, preset_pred( name ), text )
            
            # it writes back out as something we can read in again
            ( reparsed_predicate, ) = ClientSearchParseSystemPredicates.ParseSystemPredicateStringsToPredicates( [ predicate.ToString() ] )
            
            self.assertEqual( reparsed_predicate, predicate )
            
            # and it survives saving
            self.assertEqual( HydrusSerialisable.CreateFromSerialisableTuple( predicate.GetSerialisableTuple() ), predicate )
            
        
        self.assertEqual( preset_pred( 'my_preset' ).ToString(), 'system:presets my_preset' )
        
    
    def test_options( self ):
        
        new_options = ClientOptions.ClientOptions()
        
        self.assertEqual( new_options.GetTagPresets(), [] )
        
        tag_presets = [ ( 'colours', [ 'blue eyes', '-red hair' ] ), ( 'empty', [] ) ]
        
        new_options.SetTagPresets( tag_presets )
        
        self.assertEqual( new_options.GetTagPresets(), tag_presets )
        
        # it survives saving
        loaded_options = HydrusSerialisable.CreateFromSerialisableTuple( new_options.GetSerialisableTuple() )
        
        self.assertEqual( loaded_options.GetTagPresets(), tag_presets )
        
    
