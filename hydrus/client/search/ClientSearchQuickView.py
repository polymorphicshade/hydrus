from hydrus.core import HydrusExceptions

from hydrus.client.metadata import ClientTagsHandling
from hydrus.client.search import ClientSearchPredicate
from hydrus.client.search import ClientSearchTagPresets

# quick view: enter one tag, or a tag preset, and get a new search page of those files in a random order, with the media viewer open on the first one

def GetQuickViewSearch(
    text: str,
    tag_presets: list[ ClientSearchTagPresets.TagPreset ],
    tag_autocomplete_options: ClientTagsHandling.TagAutocompleteOptions
) -> tuple[ str, list[ ClientSearchPredicate.Predicate ] ]:
    
    # returns ( page name, predicates ). raises VetoException if the text is no good
    text = ' '.join( text.split() )
    
    if text == '':
        
        raise HydrusExceptions.VetoException( 'Please enter a tag or a tag preset!' )
        
    
    # a preset's name wins over a tag that is spelled the same. 'system:presets name' works too, just like in a search box
    tag_preset = ClientSearchTagPresets.GetTagPreset( tag_presets, text )
    
    if tag_preset is not None:
        
        ( preset_name, entries ) = tag_preset
        
        predicate = ClientSearchPredicate.Predicate( ClientSearchPredicate.PREDICATE_TYPE_SYSTEM_TAG_PRESET, preset_name )
        
    else:
        
        predicate = ClientSearchTagPresets.ConvertTagPresetEntryToPredicate( text, tag_autocomplete_options )
        
        if predicate is None:
            
            raise HydrusExceptions.VetoException( f'Sorry, "{text}" is not something that can be searched for!' )
            
        
    
    if predicate.GetType() == ClientSearchPredicate.PREDICATE_TYPE_SYSTEM_TAG_PRESET:
        
        page_name = predicate.GetValue()
        
        tag_preset = ClientSearchTagPresets.GetTagPreset( tag_presets, page_name )
        
        if tag_preset is not None:
            
            page_name = tag_preset[0]
            
        
    else:
        
        page_name = text
        
    
    ( predicates, missing_names ) = ClientSearchTagPresets.ExpandTagPresetPredicates( [ predicate ], tag_presets, tag_autocomplete_options )
    
    if len( missing_names ) > 0:
        
        missing_names_string = ', '.join( f'"{name}"' for name in missing_names )
        
        raise HydrusExceptions.VetoException( f'There is no tag preset called {missing_names_string}! You can make and edit them under options->tag presets.' )
        
    
    if len( predicates ) == 0:
        
        raise HydrusExceptions.VetoException( f'The tag preset "{page_name}" has nothing in it to search for!' )
        
    
    return ( page_name, predicates )
    
