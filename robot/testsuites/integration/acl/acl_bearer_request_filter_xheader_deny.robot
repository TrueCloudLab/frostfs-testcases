*** Settings ***
Variables   common.py

Library     acl.py
Library     container.py
Library     neofs_verbs.py
Library     utility_keywords.py

Resource    eacl_tables.robot
Resource    common_steps_acl_bearer.robot
Resource    payment_operations.robot

*** Variables ***
&{USER_HEADER} =        key1=1      key2=abc
&{USER_HEADER_DEL} =    key1=del    key2=del
&{ANOTHER_HEADER} =     key1=oth    key2=oth
${ERROR} =              code = 2048 message = access to object operation denied

*** Test cases ***
BearerToken Operations
    [Documentation]         Testcase to validate NeoFS operations with BearerToken.
    [Tags]                  ACL   BearerToken
    [Timeout]               1 min


    ${WALLET}   ${_}     ${_} =   Prepare Wallet And Deposit

                            Log    Check Bearer token with simple object
    ${FILE_S}    ${_} =     Generate file    ${SIMPLE_OBJ_SIZE}
                            Check eACL Allow All Bearer Filter Requst Equal Deny    ${WALLET}    ${FILE_S}

                            Log    Check Bearer token with complex object
    ${FILE_S}    ${_} =     Generate file    ${COMPLEX_OBJ_SIZE}
                            Check eACL Allow All Bearer Filter Requst Equal Deny    ${WALLET}    ${FILE_S}




*** Keywords ***

Check eACL Allow All Bearer Filter Requst Equal Deny
    [Arguments]    ${WALLET}    ${FILE_S}

    ${CID} =                Create Container           ${WALLET}    basic_acl=eacl-public-read-write
                            Prepare eACL Role rules    ${CID}
    ${S_OID_USER} =         Put object                 ${WALLET}     ${FILE_S}   ${CID}    user_headers=${USER_HEADER}
    ${S_OID_USER_2} =       Put object                 ${WALLET}     ${FILE_S}   ${CID}
    ${D_OID_USER} =         Put object                 ${WALLET}     ${FILE_S}   ${CID}    user_headers=${USER_HEADER_DEL}
    @{S_OBJ_H} =            Create List	               ${S_OID_USER}


    ${filters}=             Create Dictionary    headerType=REQUEST    matchType=STRING_EQUAL    key=a    value=256
    ${rule1}=               Create Dictionary    Operation=GET             Access=DENY    Role=USER    Filters=${filters}
    ${rule2}=               Create Dictionary    Operation=HEAD            Access=DENY    Role=USER    Filters=${filters}
    ${rule3}=               Create Dictionary    Operation=PUT             Access=DENY    Role=USER    Filters=${filters}
    ${rule4}=               Create Dictionary    Operation=DELETE          Access=DENY    Role=USER    Filters=${filters}
    ${rule5}=               Create Dictionary    Operation=SEARCH          Access=DENY    Role=USER    Filters=${filters}
    ${rule6}=               Create Dictionary    Operation=GETRANGE        Access=DENY    Role=USER    Filters=${filters}
    ${rule7}=               Create Dictionary    Operation=GETRANGEHASH    Access=DENY    Role=USER    Filters=${filters}
    ${eACL_gen}=            Create List    ${rule1}    ${rule2}    ${rule3}    ${rule4}    ${rule5}    ${rule6}    ${rule7}

    ${EACL_TOKEN} =         Form BearerToken File       ${WALLET}    ${CID}    ${eACL_gen}

                        Put object      ${WALLET}    ${FILE_S}     ${CID}           bearer=${EACL_TOKEN}    user_headers=${ANOTHER_HEADER}   options=--xhdr a=2
                        Get object      ${WALLET}    ${CID}        ${S_OID_USER}    ${EACL_TOKEN}    local_file_eacl      ${EMPTY}      --xhdr a=2
                        Search object   ${WALLET}    ${CID}        bearer=${EACL_TOKEN}     filters=${USER_HEADER}
                                        ...         expected_objects_list=${S_OBJ_H}        options=--xhdr a=2
                        Head object     ${WALLET}    ${CID}        ${S_OID_USER}    bearer_token=${EACL_TOKEN}    options=--xhdr a=2
                        Get Range       ${WALLET}    ${CID}        ${S_OID_USER}    0:256   bearer=${EACL_TOKEN}         options=--xhdr a=2
                        Get Range Hash  ${WALLET}    ${CID}        ${S_OID_USER}    ${EACL_TOKEN}    0:256            options=--xhdr a=2
                        Delete object   ${WALLET}    ${CID}        ${D_OID_USER}    bearer=${EACL_TOKEN}    options=--xhdr a=2

    ${ERR} =            Run Keyword And Expect Error    *
                        ...  Put object     ${WALLET}    ${FILE_S}    ${CID}    bearer=${EACL_TOKEN}    user_headers=${USER_HEADER}    options=--xhdr a=256
                        Should Contain      ${ERR}      ${ERROR}
    ${ERR} =            Run Keyword And Expect Error    *
                        ...  Get object     ${WALLET}    ${CID}       ${S_OID_USER}    ${EACL_TOKEN}    local_file_eacl      ${EMPTY}   --xhdr a=256
                        Should Contain      ${ERR}      ${ERROR}
    ${ERR} =            Run Keyword And Expect Error    *
                        ...  Search object   ${WALLET}    ${CID}       bearer=${EACL_TOKEN}    filters=${USER_HEADER}   options=--xhdr a=256
                        Should Contain      ${ERR}      ${ERROR}
    ${ERR} =            Run Keyword And Expect Error    *
                        ...  Head object     ${WALLET}    ${CID}       ${S_OID_USER}    bearer_token=${EACL_TOKEN}    options=--xhdr a=256
                        Should Contain      ${ERR}      ${ERROR}
    ${ERR} =            Run Keyword And Expect Error    *
                        ...  Get Range       ${WALLET}    ${CID}       ${S_OID_USER}    0:256      bearer=${EACL_TOKEN}    options=--xhdr a=256
                        Should Contain      ${ERR}      ${ERROR}
    ${ERR} =            Run Keyword And Expect Error    *
                        ...  Get Range Hash  ${WALLET}    ${CID}       ${S_OID_USER}    ${EACL_TOKEN}    0:256    options=--xhdr a=256
                        Should Contain      ${ERR}      ${ERROR}
    ${ERR} =            Run Keyword And Expect Error    *
                        ...  Delete object   ${WALLET}    ${CID}       ${S_OID_USER}    bearer=${EACL_TOKEN}    options=--xhdr a=256
                        Should Contain      ${ERR}      ${ERROR}