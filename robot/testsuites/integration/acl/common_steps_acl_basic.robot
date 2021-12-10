*** Settings ***
Variables   ../../../variables/common.py
Variables   ../../../variables/acl.py

*** Keywords ***

Create Private Container
    [Arguments]    ${USER_KEY}
                            Log	                   Create Private Container
    ${PRIV_CID_GEN} =       Create container       ${USER_KEY}        ${PRIVATE_ACL}            ${COMMON_PLACEMENT_RULE}
                            Wait Until Keyword Succeeds               ${MORPH_BLOCK_TIME}       ${CONTAINER_WAIT_INTERVAL}
                            ...     Container Existing     ${USER_KEY}        ${PRIV_CID_GEN}
    [Return]    ${PRIV_CID_GEN}

Create Public Container
    [Arguments]    ${USER_KEY}
                            Log	                   Create Public Container
    ${PUBLIC_CID_GEN} =     Create container       ${USER_KEY}        ${PUBLIC_ACL}             ${COMMON_PLACEMENT_RULE}
                            Wait Until Keyword Succeeds               ${MORPH_BLOCK_TIME}       ${CONTAINER_WAIT_INTERVAL}
                            ...     Container Existing     ${USER_KEY}        ${PUBLIC_CID_GEN}
    [Return]    ${PUBLIC_CID_GEN}                           

Create Read-Only Container
    [Arguments]    ${USER_KEY}
                            Log	                   Create Read-Only Container
    ${READONLY_CID_GEN} =   Create container       ${USER_KEY}        ${READONLY_ACL}           ${COMMON_PLACEMENT_RULE}
                            Wait Until Keyword Succeeds               ${MORPH_BLOCK_TIME}       ${CONTAINER_WAIT_INTERVAL}
                            ...     Container Existing     ${USER_KEY}        ${READONLY_CID_GEN}
    [Return]    ${READONLY_CID_GEN}


Generate file
    [Arguments]             ${SIZE}
    ${FILE_S_GEN} =         Generate file of bytes    ${SIZE}
    ${FILE_S_HASH_GEN} =    Get file hash             ${FILE_S_GEN}
    [Return]     ${FILE_S_GEN}    ${FILE_S_HASH_GEN}