*** Settings ***
Variables   ../../../variables/common.py

Library     Collections
Library     neofs.py
Library     acl.py
Library     payment_neogo.py

Resource    ../../../variables/eacl_tables.robot
Resource    common_steps_acl_bearer.robot
Resource    ../${RESOURCES}/payment_operations.robot
Resource    ../${RESOURCES}/setup_teardown.robot


*** Test cases ***
BearerToken Operations
    [Documentation]         Testcase to validate NeoFS operations with BearerToken.
    [Tags]                  ACL  NeoFS  NeoCLI BearerToken
    [Timeout]               20 min

    [Setup]                 Setup

    ${WALLET}   ${ADDR}     ${USER_KEY} =   Prepare Wallet And Deposit 
                            Prepare eACL Role rules

                            Log    Check Bearer token with simple object
    ${FILE_S} =             Generate file    ${SIMPLE_OBJ_SIZE}
                            Check eACL Deny and Allow All Bearer    ${USER_KEY}    ${FILE_S}

                            Log    Check Bearer token with complex object
    ${FILE_S} =             Generate file    ${COMPLEX_OBJ_SIZE}
                            Check eACL Deny and Allow All Bearer    ${USER_KEY}    ${FILE_S}


    [Teardown]              Teardown    acl_bearer_allow



*** Keywords ***

Check eACL Deny and Allow All Bearer
    [Arguments]    ${USER_KEY}    ${FILE_S}

    ${CID} =            Create Container Public    ${USER_KEY}
    ${S_OID_USER} =     Put object        ${USER_KEY}    ${FILE_S}    ${CID}    ${EMPTY}    ${FILE_USR_HEADER}
    ${D_OID_USER} =     Put object        ${USER_KEY}    ${FILE_S}    ${CID}    ${EMPTY}    ${FILE_USR_HEADER_DEL}
    @{S_OBJ_H} =	Create List	      ${S_OID_USER}

                        Put object        ${USER_KEY}    ${FILE_S}     ${CID}           ${EMPTY}       ${FILE_OTH_HEADER}
                        Get object        ${USER_KEY}    ${CID}        ${S_OID_USER}    ${EMPTY}       local_file_eacl
                        Search object     ${USER_KEY}    ${CID}        ${EMPTY}         ${EMPTY}       ${FILE_USR_HEADER}    ${S_OBJ_H}
                        Head object       ${USER_KEY}    ${CID}        ${S_OID_USER}    ${EMPTY}
                        Get Range         ${USER_KEY}    ${CID}        ${S_OID_USER}    s_get_range    ${EMPTY}      0:256
                        Delete object     ${USER_KEY}    ${CID}        ${D_OID_USER}    ${EMPTY}

                        Set eACL          ${USER_KEY}    ${CID}        ${EACL_DENY_ALL_USER}

                        # The current ACL cache lifetime is 30 sec
                        Sleep    ${NEOFS_CONTRACT_CACHE_TIMEOUT}

    ${rule1}=           Create Dictionary    Operation=GET             Access=ALLOW    Role=USER
    ${rule2}=           Create Dictionary    Operation=HEAD            Access=ALLOW    Role=USER
    ${rule3}=           Create Dictionary    Operation=PUT             Access=ALLOW    Role=USER
    ${rule4}=           Create Dictionary    Operation=DELETE          Access=ALLOW    Role=USER
    ${rule5}=           Create Dictionary    Operation=SEARCH          Access=ALLOW    Role=USER
    ${rule6}=           Create Dictionary    Operation=GETRANGE        Access=ALLOW    Role=USER
    ${rule7}=           Create Dictionary    Operation=GETRANGEHASH    Access=ALLOW    Role=USER

    ${eACL_gen}=        Create List    ${rule1}    ${rule2}    ${rule3}    ${rule4}    ${rule5}    ${rule6}    ${rule7}

    ${EACL_TOKEN} =     Form BearerToken File       ${USER_KEY}    ${CID}    ${eACL_gen}

                        Run Keyword And Expect Error    *
                        ...  Put object     ${USER_KEY}    ${FILE_S}    ${CID}           ${EMPTY}       ${FILE_USR_HEADER}
                        Run Keyword And Expect Error    *
                        ...  Get object     ${USER_KEY}    ${CID}       ${S_OID_USER}    ${EMPTY}       local_file_eacl
                        Run Keyword And Expect Error    *
                        ...  Search object  ${USER_KEY}    ${CID}       ${EMPTY}         ${EMPTY}       ${FILE_USR_HEADER}    ${S_OBJ_H}
                        Run Keyword And Expect Error    *
                        ...  Head object    ${USER_KEY}    ${CID}       ${S_OID_USER}    ${EMPTY}
                        Run Keyword And Expect Error    *
                        ...  Get Range      ${USER_KEY}    ${CID}       ${S_OID_USER}    s_get_range    ${EMPTY}      0:256
                        Run Keyword And Expect Error    *
                        ...  Delete object  ${USER_KEY}    ${CID}       ${S_OID_USER}    ${EMPTY}

                        # All operations on object should be passed with bearer token
                        Put object          ${USER_KEY}    ${FILE_S}    ${CID}           ${EACL_TOKEN}    ${FILE_OTH_HEADER}
                        Get object          ${USER_KEY}    ${CID}       ${S_OID_USER}    ${EACL_TOKEN}    local_file_eacl
                        Search object       ${USER_KEY}    ${CID}       ${EMPTY}         ${EACL_TOKEN}    ${FILE_USR_HEADER}       ${S_OBJ_H}
                        Head object         ${USER_KEY}    ${CID}       ${S_OID_USER}    ${EACL_TOKEN}
                        Get Range           ${USER_KEY}    ${CID}       ${S_OID_USER}    s_get_range      ${EACL_TOKEN}    0:256
                        Delete object       ${USER_KEY}    ${CID}       ${S_OID_USER}    ${EACL_TOKEN}
                        