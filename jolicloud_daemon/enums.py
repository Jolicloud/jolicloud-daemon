TRUSTED_DOMAINS = [
    'jolicloud.com',
    'jolicloud.org',
    'jolicloud.local',
    'localhost'
]

OPERATION_FAILED = {
    'params': {
        'type':    'status',
        'code':    500,
        'details': 'Operation failed.'
    }
}

SYNTAX_ERROR = {
    'params': {
        'type': 'DISPATCHER/SYNTAX_ERROR',
        'code': 501,
        'details': 'Syntax error in parameters or arguments.'
    }
}

NOT_IMPLEMENTED =  {
    'params': {
        'type': 'DISPATCHER/NOT_IMPLEMENTED',
        'code': 502,
        'details': 'Command not implemented. The server does not support this command.'
    }
}

PERMISSION_DENIED =  {
    'params': {
        'type': 'PERMISSION_DENIED',
        'code': 503,
        'details': 'Permission denied to execute this command.'
    }
}

DEVICE_UNAVAILABLE = {
    'params': {
        'type': 'DEVICE_MANAGER/DEVICE_UNAVAILABLE',
        'code': 551,
        'details': 'Device(s) unavailable.'
    }
}

HIBERNATE_UNAVAILABLE = {
    'params': {
        'type': 'SESSION_MANAGER/HIBERNATE_UNAVAILABLE',
        'code': 552,
        'details': 'Hibernate unavailable.'
    }
}

SUSPEND_UNAVAILABLE = {
    'params': {
        'type': 'SESSION_MANAGER/SUSPEND_UNAVAILABLE',
        'code': 553,
        'details': 'Suspend unavailable.'
    }
}

EVENT_UNAVAILABLE = {
    'params': {
        'type': 'DISPATCHER/EVENT_UNAVAILABLE',
        'code': 554,
        'details': 'Event unavailable.'
    }
}

PACKAGE_MANAGER_ERROR = {
    'params': {
        'type': 'PACKAGE_MANAGER/UNKNOWN',
        'code': 557,
        'details': 'Unknown error occurred.'
    }
}

OPERATION_IN_PROGRESS = {
    'params': {
        'type': 'DISPATCHER/OPERATION_IN_PROGRESS',
        'code': 150,
        'details': 'Operation in progress.'
    }
}

OPERATION_SUCCESSFUL = {
    'params': {
        'type': 'DISPATCHER/OPERATION_SUCCESSFUL',
        'code': 200,
        'details': 'Operation successful.'
    }
}
