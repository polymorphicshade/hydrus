import collections.abc
import re

from hydrus.core import HydrusData
from hydrus.core import HydrusExceptions
from hydrus.core import HydrusSerialisable

from hydrus.client import ClientGlobals as CG

# counters are tallies the user keeps for each file, like how many times they have watched it
# the counters themselves, an id and a name each, are in the options. each file's counts are in the db. names are not case-sensitive

def GetCounterNameError( name: str, other_names: collections.abc.Collection[ str ] ) -> str | None:
    
    if name.strip() == '':
        
        return 'Please enter a name!'
        
    
    if name.strip().lower() in { other_name.lower() for other_name in other_names }:
        
        return f'There is already a counter called "{name.strip()}"!'
        
    
    return None
    

def GetCounterIdsForNamespaces( namespaces: collections.abc.Collection[ str ] ) -> dict[ str, bytes ]:
    
    # the counter for each namespace, by name. any that do not exist yet are made, and saved
    new_options = CG.client_controller.new_options
    
    counters = new_options.GetCounters()
    
    names_to_counter_ids = { counter.name.lower() : counter.object_id for counter in counters }
    
    namespaces_to_counter_ids = {}
    
    new_counters_added = False
    
    for namespace in sorted( namespaces ):
        
        if namespace.lower() not in names_to_counter_ids:
            
            counter = HydrusSerialisable.IdAndName( HydrusData.GenerateKey(), namespace )
            
            counters.append( counter )
            
            names_to_counter_ids[ namespace.lower() ] = counter.object_id
            
            new_counters_added = True
            
        
        namespaces_to_counter_ids[ namespace ] = names_to_counter_ids[ namespace.lower() ]
        
    
    if new_counters_added:
        
        new_options.SetCounters( counters )
        
        # the db does jobs in order, so the new counters are saved before any counts that go in after
        CG.client_controller.Write( 'serialisable', new_options )
        
    
    return namespaces_to_counter_ids
    

def ParseTagsToCountersFilter( text: str ) -> tuple[ str, str ]:
    
    # 'items:72' -> ( 'items', '72' ), 'items:*' or 'items' -> ( 'items', '*' ). raises VetoException if it could never match anything
    text = text.strip().lower()
    
    if ':' in text:
        
        ( namespace_wildcard, subtag_wildcard ) = text.split( ':', 1 )
        
    else:
        
        ( namespace_wildcard, subtag_wildcard ) = ( text, '' )
        
    
    namespace_wildcard = namespace_wildcard.strip()
    subtag_wildcard = subtag_wildcard.strip()
    
    if namespace_wildcard == '':
        
        raise HydrusExceptions.VetoException( 'Please enter a namespace, like "items:*". The namespace is the name of the counter, so a tag without one cannot be converted.' )
        
    
    if subtag_wildcard == '':
        
        subtag_wildcard = '*'
        
    
    if re.fullmatch( r'[0-9*]+', subtag_wildcard ) is None:
        
        raise HydrusExceptions.VetoException( f'The part after the colon, "{subtag_wildcard}", can never match a number! Use digits and * only, like "items:72" or "items:*".' )
        
    
    return ( namespace_wildcard, subtag_wildcard )
    
