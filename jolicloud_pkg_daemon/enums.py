NOT_IMPLEMENTED =  {
    'params': {
        'code':    502,
        'message': 'Command not implemented. The server does not support this command.',
        'type':    'status'
    }
}

SYNTAX_ERROR = {
    'params': {
        'code':    501,
        'message': 'Syntax error in parameters or arguments.',
        'type':    'status'
    }
}

OPERATION_IN_PROGRESS = {
    'params': {
        'code':    150,
        'message': 'Operation in progress.',
        'type':    'status'
    }
}

OPERATION_SUCCESSFUL = {
    'params': {
        'message': 'Operation successful.',
        'code':    200,
        'type':    'status'
    }
}

OPERATION_FAILED = {
    'params': {
        'message': 'Operation failed.',
        'code':    501,
        'type':    'status'  
    }
}

