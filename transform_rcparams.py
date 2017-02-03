from __future__ import print_function, division, unicode_literals

from numbers import Number
from collections import defaultdict, OrderedDict

import matplotlib as mpl


def get_rcparams_types(rcfile):
    """
    Read and analyse types of rcParams. Lookup and merge with any
    documentation found for each param.

    :returns: {paramname: paramdict}
        paramdict:
            {'type': str,
            'list_type': str,
            'default': str,
            'options': str}
    """
    rc = dict(mpl.rcParams)
    helps = scrape_help_for_param(rcfile)
    for k,v in rc.items():
        if isinstance(v, bool):
            rc[k] = {'type': 'bool', 'default': v}
        elif isinstance(v, Number):
            rc[k] = {'type': 'float', 'default': v}
        elif isinstance(v, str):
            rc[k] = {'type': 'colorstring' if 'color' in k else 'string',
                     'default': v,
                     'options': []}
        elif isinstance(v, list):
            list_type = 'float' if (v and isinstance(v[0], Number)) else 'string'
            rc[k] = {'type': 'list', 'list_type': list_type, 'default': v}
        elif v is None:
            rc[k] = {'type': None, 'default': v}
        else:
            rc[k] = {'type': 'string', 'default': v}
        if k in helps:
            rc[k]['help'] = helps[k]
    return rc


def categorize_rc_params(rc):
    """
    Split by first dot and put first part as key in an ordered dict.
    """
    by_category = defaultdict(OrderedDict)
    for key, val in rc.items():
        by_category[ key.split('.')[0] ][key] = val
    return by_category


def scrape_help_for_param(rcfile):
    """
    Reads a matplotlib rcfile and returns any documentation found
    for them as a dictionary. 

    It uses regex to extract all multiline comments following params
    that starts on the same line as the param. 
    
    :returns: {str: str}
        {paramname: helptext}
    
    """
    discard_falsy = lambda seq: [x for x in seq if x]
    with open(rcfile) as fh:
        contents = fh.read()
    wo_comments = re.sub(r'^#[# \n].*', '', contents, flags=re.MULTILINE)
    wo_lead_hash = re.sub(r'^#', r'\n', wo_comments, flags=re.M)
    raw_param_lines = discard_falsy(wo_lead_hash.split('\n\n'))
    helps = {}
    for line in raw_param_lines:
        parts = discard_falsy(line.split('#'))
        param = parts[0].split(':')[0].strip()
        if not param:
            print('Empty param: %s' %line.replace('\n', '\\n'))
            continue
        helps[param] = ' '.join(map(str.strip, parts[1:]))
    return helps

