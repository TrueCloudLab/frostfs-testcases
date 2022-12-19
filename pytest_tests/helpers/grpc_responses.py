import re

# Regex patterns of status codes of Container service (https://github.com/nspcc-dev/neofs-spec/blob/98b154848116223e486ce8b43eaa35fec08b4a99/20-api-v2/container.md)
CONTAINER_NOT_FOUND = "code = 3072.*message = container not found"


# Regex patterns of status codes of Object service (https://github.com/nspcc-dev/neofs-spec/blob/98b154848116223e486ce8b43eaa35fec08b4a99/20-api-v2/object.md)
MALFORMED_REQUEST = "code = 1024.*message = malformed request"
OBJECT_ACCESS_DENIED = "code = 2048.*message = access to object operation denied"
OBJECT_NOT_FOUND = "code = 2049.*message = object not found"
OBJECT_ALREADY_REMOVED = "code = 2052.*message = object already removed"
SESSION_NOT_FOUND = "code = 4096.*message = session token not found"
OUT_OF_RANGE = "code = 2053.*message = out of range"
# TODO: Due to https://github.com/nspcc-dev/neofs-node/issues/2092 we have to check only codes until fixed
# OBJECT_IS_LOCKED = "code = 2050.*message = object is locked"
# LOCK_NON_REGULAR_OBJECT = "code = 2051.*message = ..." will be available once 2092 is fixed
OBJECT_IS_LOCKED = "code = 2050"
LOCK_NON_REGULAR_OBJECT = "code = 2051"

LIFETIME_REQUIRED = "either expiration epoch of a lifetime is required"
LOCK_OBJECT_REMOVAL = "lock object removal"
LOCK_OBJECT_EXPIRATION = "lock object expiration: {expiration_epoch}; current: {current_epoch}"
INVALID_RANGE_ZERO_LENGTH = "invalid '{range}' range: zero length"
INVALID_RANGE_OVERFLOW = "invalid '{range}' range: uint64 overflow"
INVALID_OFFSET_SPECIFIER = "invalid '{range}' range offset specifier"
INVALID_LENGTH_SPECIFIER = "invalid '{range}' range length specifier"


def error_matches_status(error: Exception, status_pattern: str) -> bool:
    """
    Determines whether exception matches specified status pattern.

    We use re.search to be consistent with pytest.raises.
    """
    match = re.search(status_pattern, str(error))
    return match is not None
